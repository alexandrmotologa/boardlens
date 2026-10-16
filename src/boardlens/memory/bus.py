"""Memory bus routing requests to memory regions and MMIO peripherals."""

from dataclasses import dataclass
from typing import Callable, List, Optional
from boardlens.memory.region import MemoryRegion


class BusFault(Exception):
    """Raised when an invalid memory access or unmapped address is encountered."""

    def __init__(self, address: int, is_write: bool, size: int, message: Optional[str] = None):
        self.address = address & 0xFFFFFFFF
        self.is_write = is_write
        self.size = size
        op = "WRITE" if is_write else "READ"
        self.message = message or f"BusFault: {op} error at 0x{self.address:08X} (size={size} bytes)"
        super().__init__(self.message)


@dataclass(frozen=True)
class BusTransaction:
    """Record of a bus transaction for logic analysis and VCD tracing."""
    cycle: int
    address: int
    data: int
    is_write: bool
    size: int  # 1, 2, or 4 bytes


class MemoryBus:
    """Interconnect bus providing address decoding, memory protection, and telemetry."""

    def __init__(self, allow_unaligned: bool = True) -> None:
        self.regions: List[MemoryRegion] = []
        self.allow_unaligned = allow_unaligned
        self.cycle_count: int = 0
        self._listeners: List[Callable[[BusTransaction], None]] = []

    def map_region(self, region: MemoryRegion) -> None:
        """Map a memory region into the bus address space, verifying no overlapping ranges."""
        new_start = region.base_address
        new_end = region.end_address

        for existing in self.regions:
            ex_start = existing.base_address
            ex_end = existing.end_address
            if max(new_start, ex_start) < min(new_end, ex_end):
                raise ValueError(
                    f"Address collision: '{region.name}' [0x{new_start:08X}, 0x{new_end:08X}) "
                    f"overlaps with '{existing.name}' [0x{ex_start:08X}, 0x{ex_end:08X})"
                )

        self.regions.append(region)
        # Keep regions sorted by base address for clean binary search / iteration
        self.regions.sort(key=lambda r: r.base_address)

    def unmap_region(self, name: str) -> bool:
        """Unmap a region by name. Returns True if removed, False otherwise."""
        for i, reg in enumerate(self.regions):
            if reg.name == name:
                del self.regions[i]
                return True
        return False

    def find_region(self, address: int, size: int = 1) -> Optional[MemoryRegion]:
        """Find the memory region that contains the specified address range."""
        addr = address & 0xFFFFFFFF
        for region in self.regions:
            if region.contains(addr, size):
                return region
        return None

    def add_listener(self, listener: Callable[[BusTransaction], None]) -> None:
        """Register a callback for all bus transactions."""
        self._listeners.append(listener)

    def _record_transaction(self, address: int, data: int, is_write: bool, size: int) -> None:
        """Notify registered listeners and VCD tracers of a bus cycle."""
        tx = BusTransaction(
            cycle=self.cycle_count,
            address=address & 0xFFFFFFFF,
            data=data & 0xFFFFFFFF,
            is_write=is_write,
            size=size,
        )
        for listener in self._listeners:
            listener(tx)

    # Byte access
    def read8(self, address: int) -> int:
        addr = address & 0xFFFFFFFF
        region = self.find_region(addr, 1)
        if region is None:
            raise BusFault(addr, is_write=False, size=1, message=f"Read from unmapped address 0x{addr:08X}")
        val = region.read8(addr - region.base_address) & 0xFF
        self._record_transaction(addr, val, is_write=False, size=1)
        return val

    def write8(self, address: int, value: int) -> None:
        addr = address & 0xFFFFFFFF
        val = value & 0xFF
        region = self.find_region(addr, 1)
        if region is None:
            raise BusFault(addr, is_write=True, size=1, message=f"Write to unmapped address 0x{addr:08X}")
        try:
            region.write8(addr - region.base_address, val)
        except PermissionError as exc:
            raise BusFault(addr, is_write=True, size=1, message=str(exc))
        self._record_transaction(addr, val, is_write=True, size=1)

    # Halfword access
    def read16(self, address: int) -> int:
        addr = address & 0xFFFFFFFF
        if not self.allow_unaligned and (addr & 1):
            raise BusFault(addr, is_write=False, size=2, message=f"Unaligned 16-bit read at 0x{addr:08X}")
        region = self.find_region(addr, 2)
        if region is not None:
            val = region.read16(addr - region.base_address) & 0xFFFF
        else:
            # Handle split access across regions or unmapped
            b0 = self.read8(addr)
            b1 = self.read8(addr + 1)
            val = (b1 << 8) | b0
        self._record_transaction(addr, val, is_write=False, size=2)
        return val

    def write16(self, address: int, value: int) -> None:
        addr = address & 0xFFFFFFFF
        val = value & 0xFFFF
        if not self.allow_unaligned and (addr & 1):
            raise BusFault(addr, is_write=True, size=2, message=f"Unaligned 16-bit write at 0x{addr:08X}")
        region = self.find_region(addr, 2)
        if region is not None:
            try:
                region.write16(addr - region.base_address, val)
            except PermissionError as exc:
                raise BusFault(addr, is_write=True, size=2, message=str(exc))
        else:
            self.write8(addr, val & 0xFF)
            self.write8(addr + 1, (val >> 8) & 0xFF)
        self._record_transaction(addr, val, is_write=True, size=2)

    # Word access
    def read32(self, address: int) -> int:
        addr = address & 0xFFFFFFFF
        if not self.allow_unaligned and (addr & 3):
            raise BusFault(addr, is_write=False, size=4, message=f"Unaligned 32-bit read at 0x{addr:08X}")
        region = self.find_region(addr, 4)
        if region is not None:
            val = region.read32(addr - region.base_address) & 0xFFFFFFFF
        else:
            b0 = self.read8(addr)
            b1 = self.read8(addr + 1)
            b2 = self.read8(addr + 2)
            b3 = self.read8(addr + 3)
            val = (b3 << 24) | (b2 << 16) | (b1 << 8) | b0
        self._record_transaction(addr, val, is_write=False, size=4)
        return val

    def write32(self, address: int, value: int) -> None:
        addr = address & 0xFFFFFFFF
        val = value & 0xFFFFFFFF
        if not self.allow_unaligned and (addr & 3):
            raise BusFault(addr, is_write=True, size=4, message=f"Unaligned 32-bit write at 0x{addr:08X}")
        region = self.find_region(addr, 4)
        if region is not None:
            try:
                region.write32(addr - region.base_address, val)
            except PermissionError as exc:
                raise BusFault(addr, is_write=True, size=4, message=str(exc))
        else:
            self.write8(addr, val & 0xFF)
            self.write8(addr + 1, (val >> 8) & 0xFF)
            self.write8(addr + 2, (val >> 16) & 0xFF)
            self.write8(addr + 3, (val >> 24) & 0xFF)
        self._record_transaction(addr, val, is_write=True, size=4)

    def reset(self) -> None:
        """Reset all mapped memory regions and cycle count."""
        self.cycle_count = 0
        for region in self.regions:
            region.reset()
