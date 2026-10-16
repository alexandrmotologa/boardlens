"""Memory region abstraction for addressable bus space."""

from abc import ABC, abstractmethod


class MemoryRegion(ABC):
    """Abstract base class for any device or memory block mapped onto the bus."""

    def __init__(
        self,
        base_address: int,
        size: int,
        name: str = "MemoryRegion",
        read_only: bool = False,
        executable: bool = True,
    ) -> None:
        self.base_address = base_address & 0xFFFFFFFF
        self.size = size
        self.name = name
        self.read_only = read_only
        self.executable = executable

    @property
    def end_address(self) -> int:
        """Exclusive end address of this region."""
        return self.base_address + self.size

    def contains(self, address: int, length: int = 1) -> bool:
        """Check if an address range fits entirely within this region."""
        addr = address & 0xFFFFFFFF
        return (self.base_address <= addr) and (addr + length <= self.end_address)

    @abstractmethod
    def read8(self, offset: int) -> int:
        """Read 8-bit byte from zero-based offset."""
        pass

    def read16(self, offset: int) -> int:
        """Read 16-bit halfword in little-endian order."""
        b0 = self.read8(offset)
        b1 = self.read8(offset + 1)
        return (b1 << 8) | b0

    def read32(self, offset: int) -> int:
        """Read 32-bit word in little-endian order."""
        b0 = self.read8(offset)
        b1 = self.read8(offset + 1)
        b2 = self.read8(offset + 2)
        b3 = self.read8(offset + 3)
        return (b3 << 24) | (b2 << 16) | (b1 << 8) | b0

    @abstractmethod
    def write8(self, offset: int, value: int) -> None:
        """Write 8-bit byte to zero-based offset."""
        pass

    def write16(self, offset: int, value: int) -> None:
        """Write 16-bit halfword in little-endian order."""
        v = value & 0xFFFF
        self.write8(offset, v & 0xFF)
        self.write8(offset + 1, (v >> 8) & 0xFF)

    def write32(self, offset: int, value: int) -> None:
        """Write 32-bit word in little-endian order."""
        v = value & 0xFFFFFFFF
        self.write8(offset, v & 0xFF)
        self.write8(offset + 1, (v >> 8) & 0xFF)
        self.write8(offset + 2, (v >> 16) & 0xFF)
        self.write8(offset + 3, (v >> 24) & 0xFF)

    def reset(self) -> None:
        """Reset state if applicable."""
        pass
