"""Unit tests for the ELF32 binary and symbol table parser."""

import pytest
from boardlens.memory.bus import MemoryBus
from boardlens.memory.ram import RAM
from boardlens.tooling.assembler import assemble
from boardlens.tooling.elf_loader import ELF32, ELFError, create_minimal_elf32


def test_elf_loader_valid_binary():
    # Assemble small RV32I code
    code = assemble("addi x1, x0, 42\nebreak\n")
    elf_bytes = create_minimal_elf32(
        code=code,
        entry_addr=0x00000000,
        machine=ELF32.EM_RISCV,
        symbols={"main": 0x00000000, "exit_trap": 0x00000004},
    )

    elf = ELF32(elf_bytes)
    assert elf.architecture == "rv32i"
    assert elf.e_entry == 0x00000000
    assert len(elf.segments) == 1
    assert elf.segments[0].filesz == len(code)

    # Verify symbol table extraction
    assert "main" in elf.symbol_names
    assert elf.symbol_names["main"] == 0x00000000
    assert elf.symbols[0x00000000].name == "main"
    assert elf.symbols[0x00000004].name == "exit_trap"

    # Test loading into MemoryBus
    bus = MemoryBus()
    flash = RAM(base_address=0x00000000, size=0x1000, name="FLASH")
    bus.map_region(flash)

    entry = elf.load_into_bus(bus)
    assert entry == 0x00000000
    assert bus.read32(0x00000000) == int.from_bytes(code[:4], byteorder="little")


def test_elf_loader_errors():
    with pytest.raises(ELFError, match="File too small"):
        ELF32(b"too_short")

    with pytest.raises(ELFError, match="Invalid ELF magic"):
        ELF32(b"x" * 60)

    # 64-bit ELF (class 2) rejection
    bad_class = b"\x7fELF\x02\x01\x01\x00" + (b"\x00" * 44)
    with pytest.raises(ELFError, match="Unsupported ELF class"):
        ELF32(bad_class)
