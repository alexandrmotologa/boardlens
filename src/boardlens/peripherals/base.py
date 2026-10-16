"""Base Peripheral class for memory-mapped I/O (MMIO)."""

from typing import Any, Dict, Optional, Tuple
from boardlens.memory.region import MemoryRegion


class Peripheral(MemoryRegion):
    """Memory-mapped peripheral base with structured register offset handling."""

    def __init__(
        self,
        base_address: int,
        size: int,
        name: str = "Peripheral",
    ) -> None:
        super().__init__(base_address, size, name=name, read_only=False, executable=False)
        # Register definitions: offset -> [name, current_val, reset_val, read_mask, write_mask]
        self._regs: Dict[int, int] = {}
        self._reg_meta: Dict[int, Tuple[str, int, int, int]] = {}

    def register_def(
        self,
        offset: int,
        name: str,
        reset_val: int = 0,
        read_mask: int = 0xFFFFFFFF,
        write_mask: int = 0xFFFFFFFF,
    ) -> None:
        """Define an MMIO 32-bit register."""
        aligned_offset = offset & ~3
        self._reg_meta[aligned_offset] = (name, reset_val, read_mask, write_mask)
        self._regs[aligned_offset] = reset_val & 0xFFFFFFFF

    def reset(self) -> None:
        """Reset all registers to their configured reset values."""
        for offset, (_, reset_val, _, _) in self._reg_meta.items():
            self._regs[offset] = reset_val & 0xFFFFFFFF

    def read_reg(self, offset: int) -> int:
        """Read 32-bit register value."""
        aligned = offset & ~3
        meta = self._reg_meta.get(aligned)
        if meta:
            name, _, read_mask, _ = meta
            val = self._regs.get(aligned, 0) & read_mask
            return self.on_register_read(aligned, val)
        return self._regs.get(aligned, 0)

    def write_reg(self, offset: int, value: int) -> None:
        """Write 32-bit register value respecting write mask."""
        aligned = offset & ~3
        meta = self._reg_meta.get(aligned)
        if meta:
            name, _, _, write_mask = meta
            old_val = self._regs.get(aligned, 0)
            new_val = (old_val & ~write_mask) | (value & write_mask)
            self._regs[aligned] = new_val & 0xFFFFFFFF
            self.on_register_write(aligned, old_val, new_val)
        else:
            self._regs[aligned] = value & 0xFFFFFFFF

    def on_register_read(self, offset: int, value: int) -> int:
        """Subclass hook invoked when a register is read."""
        return value

    def on_register_write(self, offset: int, old_value: int, new_value: int) -> None:
        """Subclass hook invoked when a register is written."""
        pass

    def step(self, cycles: int = 1) -> None:
        """Simulate hardware actions on clock tick."""
        pass

    # MemoryRegion protocol implementation
    def read8(self, offset: int) -> int:
        aligned = offset & ~3
        byte_idx = offset & 3
        reg_val = self.read_reg(aligned)
        return (reg_val >> (byte_idx * 8)) & 0xFF

    def read16(self, offset: int) -> int:
        aligned = offset & ~3
        half_idx = (offset >> 1) & 1
        reg_val = self.read_reg(aligned)
        return (reg_val >> (half_idx * 16)) & 0xFFFF

    def read32(self, offset: int) -> int:
        return self.read_reg(offset)

    def write8(self, offset: int, value: int) -> None:
        aligned = offset & ~3
        byte_idx = offset & 3
        current = self.read_reg(aligned)
        shift = byte_idx * 8
        mask = 0xFF << shift
        new_val = (current & ~mask) | ((value & 0xFF) << shift)
        self.write_reg(aligned, new_val)

    def write16(self, offset: int, value: int) -> None:
        aligned = offset & ~3
        half_idx = (offset >> 1) & 1
        current = self.read_reg(aligned)
        shift = half_idx * 16
        mask = 0xFFFF << shift
        new_val = (current & ~mask) | ((value & 0xFFFF) << shift)
        self.write_reg(aligned, new_val)

    def write32(self, offset: int, value: int) -> None:
        self.write_reg(offset, value)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize register values for telemetry."""
        result: Dict[str, Any] = {}
        for offset, (name, _, _, _) in sorted(self._reg_meta.items()):
            val = self._regs.get(offset, 0)
            result[name] = {
                "offset": f"0x{offset:02X}",
                "value": val,
                "hex": f"0x{val:08X}",
            }
        return result
