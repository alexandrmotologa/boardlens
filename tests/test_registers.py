"""Unit tests for RV32I and ARM register banks."""

import pytest
from boardlens.cpu.registers import RV32IRegisters, ARMRegisters


def test_rv32i_zero_register_invariant():
    regs = RV32IRegisters()
    assert regs.read(0) == 0
    assert regs.read("zero") == 0
    assert regs.read("x0") == 0

    # Writes to x0 must be silently discarded
    regs.write(0, 0xDEADBEEF)
    assert regs.read(0) == 0
    regs.write("zero", 0xCAFEBABE)
    assert regs.read("zero") == 0
    regs["x0"] = 0x12345678
    assert regs["x0"] == 0


def test_rv32i_general_purpose_registers():
    regs = RV32IRegisters()
    regs.write(1, 0x12345678)
    assert regs.read(1) == 0x12345678
    assert regs.read("ra") == 0x12345678
    assert regs.read("x1") == 0x12345678

    # Masking to 32-bit unsigned
    regs.write(2, -1)
    assert regs.read(2) == 0xFFFFFFFF
    assert regs.read_signed(2) == -1

    regs.write("sp", 0x20004000)
    assert regs.read("sp") == 0x20004000
    assert regs["x2"] == 0x20004000

    # Read signed with negative value
    regs.write(3, 0x80000000)
    assert regs.read_signed(3) == -2147483648

    # Frame pointer alias
    regs.write("fp", 0x1000)
    assert regs.read("s0") == 0x1000
    assert regs.read(8) == 0x1000


def test_rv32i_invalid_register():
    regs = RV32IRegisters()
    with pytest.raises(IndexError):
        regs.read(32)
    with pytest.raises(IndexError):
        regs.write(-1, 0)
    with pytest.raises(KeyError):
        regs.read("nonexistent_reg")


def test_rv32i_csrs_and_counters():
    regs = RV32IRegisters()
    assert regs.read_csr(RV32IRegisters.CSR_MISA) == 0x40000100

    regs.write_csr(RV32IRegisters.CSR_MEPC, 0x80000100)
    assert regs.read_csr(RV32IRegisters.CSR_MEPC) == 0x80000100

    regs.increment_cycle_counters(cycles=10, instructions=5)
    assert regs.read_csr(RV32IRegisters.CSR_MCYCLE) == 10
    assert regs.read_csr(RV32IRegisters.CSR_MINSTRET) == 5

    snapshot = regs.to_dict()
    assert "gpr" in snapshot
    assert "csrs" in snapshot
    assert snapshot["gpr"]["x1"]["abi"] == "ra"


def test_arm_registers():
    arm = ARMRegisters()
    assert arm.read(0) == 0
    arm.write(0, 0xABCDEF01)
    assert arm.read(0) == 0xABCDEF01

    arm.sp = 0x20001000
    assert arm.read(13) == 0x20001000
    assert arm.sp == 0x20001000

    arm.lr = 0x08000201
    assert arm.read(14) == 0x08000201
    assert arm.lr == 0x08000201

    arm.pc = 0x08000200
    assert arm.read(15) == 0x08000200
    assert arm.pc == 0x08000200

    # Flags
    arm.update_flags_nz(0)
    assert arm.z is True
    assert arm.n is False

    arm.update_flags_nz(0x80000000)
    assert arm.z is False
    assert arm.n is True

    # xPSR test
    arm.n = True
    arm.z = False
    arm.c = True
    arm.v = False
    arm.t = True
    xpsr_val = arm.xpsr
    assert (xpsr_val & (1 << 31)) != 0
    assert (xpsr_val & (1 << 30)) == 0
    assert (xpsr_val & (1 << 29)) != 0
    assert (xpsr_val & (1 << 24)) != 0

    # Test signed read with negative value
    arm.write(1, 0xFFFFFFFF)
    assert arm.read_signed(1) == -1

    # Test out of bounds access
    with pytest.raises(IndexError):
        arm.read(16)
    with pytest.raises(IndexError):
        arm.read(-1)
    with pytest.raises(IndexError):
        arm.write(16, 0)
    with pytest.raises(IndexError):
        arm.write(-1, 0)

    # Test xPSR setter
    arm.xpsr = 0xF1000000
    assert arm.n is True
    assert arm.z is True
    assert arm.c is True
    assert arm.v is True
    assert arm.t is True

    # Test negative in RV32I to_dict
    regs = RV32IRegisters()
    regs.write(1, 0x80000000)
    d = regs.to_dict()
    assert d["gpr"]["x1"]["signed"] == -2147483648

    snapshot = arm.to_dict()
    assert "registers" in snapshot
    assert "flags" in snapshot
    assert snapshot["flags"]["N"] is True
