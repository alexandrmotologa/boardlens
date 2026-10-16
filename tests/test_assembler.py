"""Unit tests for the RV32I assembler and disassembler."""

import pytest
from boardlens.tooling.assembler import Assembler, AssemblerError, assemble
from boardlens.tooling.disassembler import disassemble_bytes, format_disassembly


def test_assembler_basic_instructions():
    source = """
    # Simple addition
    addi x1, x0, 42
    addi x2, x0, 10
    add  x3, x1, x2
    sub  x4, x3, x1
    """
    binary = assemble(source)
    assert len(binary) == 16

    # Test round trip via disassembler
    records = disassemble_bytes(binary)
    assert len(records) == 4
    assert "addi x1, x0, 42" in records[0][2]
    assert "addi x2, x0, 10" in records[1][2]
    assert "add x3, x1, x2" in records[2][2]
    assert "sub x4, x3, x1" in records[3][2]


def test_assembler_pseudo_instructions():
    source = """
    nop
    mv   t0, a0
    not  t1, t0
    neg  t2, t1
    j    target
    ret
    target:
    ebreak
    """
    binary = assemble(source)
    records = disassemble_bytes(binary)
    assert len(records) >= 7


def test_assembler_large_li():
    # Immediate requiring lui + addi
    source = """
    li a0, 0x12345678
    """
    binary = assemble(source)
    assert len(binary) == 8
    records = disassemble_bytes(binary)
    assert len(records) == 2


def test_assembler_labels_and_branches():
    source = """
    start:
        addi t0, zero, 10
    loop:
        addi t0, t0, -1
        bnez t0, loop
        ebreak
    """
    binary = assemble(source)
    records = disassemble_bytes(binary)
    assert len(records) == 4
    assert "bne x5, x0, -4" in records[2][2]


def test_assembler_memory_operations():
    source = """
    lui t0, 0x20000
    sw  t1, 16(t0)
    lw  t2, 16(t0)
    """
    binary = assemble(source)
    assert len(binary) == 12


def test_assembler_errors():
    with pytest.raises(AssemblerError):
        assemble("invalid_inst x1, x2")

    with pytest.raises(AssemblerError):
        assemble("addi x99, x0, 1")


def test_format_disassembly():
    binary = assemble("addi x1, x0, 42\nadd x2, x1, x1")
    formatted = format_disassembly(binary, base_address=0x1000)
    assert "00001000:" in formatted
    assert "00001004:" in formatted
    assert "addi x1, x0, 42" in formatted
