"""Bytearray-backed RAM and Flash memory regions."""

from typing import Union
from boardlens.memory.region import MemoryRegion


class RAM(MemoryRegion):
    """Contiguous block of read-write or read-only memory backed by bytearray."""

    def __init__(
        self,
        base_address: int,
        size: int,
        name: str = "RAM",
        read_only: bool = False,
        executable: bool = True,
        initial_data: Union[bytes, bytearray, None] = None,
    ) -> None:
        super().__init__(base_address, size, name, read_only, executable)
        self._data = bytearray(size)
        if initial_data:
            self.load_bytes(0, initial_data)

    def read8(self, offset: int) -> int:
        if 0 <= offset < self.size:
            return self._data[offset]
        raise IndexError(f"Read out of bounds at offset 0x{offset:X} in {self.name} (size 0x{self.size:X})")

    def read16(self, offset: int) -> int:
        if 0 <= offset <= self.size - 2:
            return self._data[offset] | (self._data[offset + 1] << 8)
        return super().read16(offset)

    def read32(self, offset: int) -> int:
        if 0 <= offset <= self.size - 4:
            return (
                self._data[offset]
                | (self._data[offset + 1] << 8)
                | (self._data[offset + 2] << 16)
                | (self._data[offset + 3] << 24)
            )
        return super().read32(offset)

    def write8(self, offset: int, value: int) -> None:
        if self.read_only:
            raise PermissionError(f"Attempted write to read-only region {self.name} at offset 0x{offset:X}")
        if 0 <= offset < self.size:
            self._data[offset] = value & 0xFF
        else:
            raise IndexError(f"Write out of bounds at offset 0x{offset:X} in {self.name}")

    def write16(self, offset: int, value: int) -> None:
        if self.read_only:
            raise PermissionError(f"Attempted write to read-only region {self.name} at offset 0x{offset:X}")
        if 0 <= offset <= self.size - 2:
            v = value & 0xFFFF
            self._data[offset] = v & 0xFF
            self._data[offset + 1] = (v >> 8) & 0xFF
        else:
            super().write16(offset, value)

    def write32(self, offset: int, value: int) -> None:
        if self.read_only:
            raise PermissionError(f"Attempted write to read-only region {self.name} at offset 0x{offset:X}")
        if 0 <= offset <= self.size - 4:
            v = value & 0xFFFFFFFF
            self._data[offset] = v & 0xFF
            self._data[offset + 1] = (v >> 8) & 0xFF
            self._data[offset + 2] = (v >> 16) & 0xFF
            self._data[offset + 3] = (v >> 24) & 0xFF
        else:
            super().write32(offset, value)

    def load_bytes(self, offset: int, data: Union[bytes, bytearray]) -> None:
        """Directly write raw bytes into memory buffer ignoring read_only flags (e.g. for flashing firmware)."""
        length = len(data)
        if offset + length > self.size:
            raise ValueError(f"Payload length 0x{length:X} exceeds region size 0x{self.size:X} at offset 0x{offset:X}")
        self._data[offset : offset + length] = data

    def read_bytes(self, offset: int, length: int) -> bytes:
        """Read a slice of raw bytes from memory buffer."""
        if offset + length > self.size:
            raise IndexError(f"Slice 0x{offset:X}:0x{offset + length:X} exceeds region size 0x{self.size:X}")
        return bytes(self._data[offset : offset + length])

    def reset(self) -> None:
        """Clear memory buffer to zeroes."""
        self._data = bytearray(self.size)
