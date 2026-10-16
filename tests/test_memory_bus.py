"""Unit tests for MemoryBus and RAM regions."""

import pytest
from boardlens.memory.bus import BusFault, BusTransaction, MemoryBus
from boardlens.memory.ram import RAM


def test_ram_read_write_operations():
    ram = RAM(base_address=0x20000000, size=0x1000, name="SRAM")
    assert ram.base_address == 0x20000000
    assert ram.size == 0x1000
    assert ram.end_address == 0x20001000
    assert ram.contains(0x20000000, 4)
    assert not ram.contains(0x20001000, 1)

    # 8-bit read/write
    ram.write8(0, 0xAB)
    assert ram.read8(0) == 0xAB

    # 16-bit read/write (little-endian)
    ram.write16(2, 0x1234)
    assert ram.read16(2) == 0x1234
    assert ram.read8(2) == 0x34
    assert ram.read8(3) == 0x12

    # 32-bit read/write (little-endian)
    ram.write32(4, 0xDEADBEEF)
    assert ram.read32(4) == 0xDEADBEEF
    assert ram.read8(4) == 0xEF
    assert ram.read8(5) == 0xBE
    assert ram.read8(6) == 0xAD
    assert ram.read8(7) == 0xDE


def test_ram_read_only_protection():
    rom = RAM(base_address=0x00000000, size=0x1000, name="FLASH", read_only=True)
    rom.load_bytes(0, b"\x01\x02\x03\x04")
    assert rom.read32(0) == 0x04030201

    with pytest.raises(PermissionError):
        rom.write8(0, 0xFF)
    with pytest.raises(PermissionError):
        rom.write16(0, 0xFFFF)
    with pytest.raises(PermissionError):
        rom.write32(0, 0xFFFFFFFF)


def test_ram_bounds_checks():
    ram = RAM(base_address=0x1000, size=16, name="SmallRAM")
    with pytest.raises(IndexError):
        ram.read8(16)
    with pytest.raises(IndexError):
        ram.write8(16, 0)
    with pytest.raises(ValueError):
        ram.load_bytes(10, b"12345678")
    with pytest.raises(IndexError):
        ram.read_bytes(10, 10)


def test_memory_bus_mapping_and_collisions():
    bus = MemoryBus()
    flash = RAM(base_address=0x00000000, size=0x10000, name="FLASH")
    sram = RAM(base_address=0x20000000, size=0x10000, name="SRAM")
    bus.map_region(flash)
    bus.map_region(sram)

    # Collision check
    overlap = RAM(base_address=0x00008000, size=0x10000, name="OVERLAP")
    with pytest.raises(ValueError, match="Address collision"):
        bus.map_region(overlap)

    # Unmap check
    assert bus.unmap_region("OVERLAP") is False
    assert bus.unmap_region("SRAM") is True
    assert bus.find_region(0x20000000) is None


def test_memory_bus_read_write_routing():
    bus = MemoryBus()
    flash = RAM(base_address=0x00000000, size=0x1000, name="FLASH", read_only=True)
    sram = RAM(base_address=0x20000000, size=0x1000, name="SRAM")
    bus.map_region(flash)
    bus.map_region(sram)

    # Transactions recording
    txs = []
    bus.add_listener(lambda tx: txs.append(tx))

    # SRAM writes and reads
    bus.write32(0x20000010, 0x12345678)
    assert bus.read32(0x20000010) == 0x12345678
    assert bus.read16(0x20000010) == 0x5678
    assert bus.read8(0x20000010) == 0x78

    assert len(txs) >= 4
    last_tx = txs[-1]
    assert isinstance(last_tx, BusTransaction)
    assert last_tx.address == 0x20000010
    assert last_tx.is_write is False
    assert last_tx.size == 1

    # Bus fault on unmapped address
    with pytest.raises(BusFault, match="unmapped address"):
        bus.read32(0x50000000)

    with pytest.raises(BusFault, match="unmapped address"):
        bus.write32(0x50000000, 0x42)

    # Bus fault on write to read-only region
    with pytest.raises(BusFault):
        bus.write32(0x00000000, 0x12345678)


def test_memory_bus_unaligned_access():
    strict_bus = MemoryBus(allow_unaligned=False)
    ram = RAM(base_address=0x20000000, size=0x1000, name="SRAM")
    strict_bus.map_region(ram)

    # 16-bit unaligned read/write
    with pytest.raises(BusFault, match="Unaligned 16-bit read"):
        strict_bus.read16(0x20000001)

    with pytest.raises(BusFault, match="Unaligned 16-bit write"):
        strict_bus.write16(0x20000001, 0x1234)

    # 32-bit unaligned read/write
    with pytest.raises(BusFault, match="Unaligned 32-bit read"):
        strict_bus.read32(0x20000002)

    with pytest.raises(BusFault, match="Unaligned 32-bit write"):
        strict_bus.write32(0x20000003, 0x12345678)
