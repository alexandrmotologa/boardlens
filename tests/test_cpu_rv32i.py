"""Comprehensive execution unit tests for the RV32ICore."""

import pytest
from boardlens.cpu.base import CpuTrap, TrapCause
from boardlens.cpu.rv32i.core import RV32ICore
from boardlens.memory.bus import MemoryBus
from boardlens.memory.ram import RAM


@pytest.fixture
def test_setup():
    bus = MemoryBus()
    flash = RAM(base_address=0x00000000, size=0x10000, name="FLASH")
    sram = RAM(base_address=0x20000000, size=0x10000, name="SRAM")
    bus.map_region(flash)
    bus.map_region(sram)
    core = RV32ICore(bus=bus, initial_pc=0x00000000)
    return core, flash, sram


def test_core_reset_and_properties(test_setup):
    core, flash, sram = test_setup
    assert core.pc == 0x00000000
    assert core.cycles == 0
    assert core.instructions_executed == 0

    core.pc = 0x100
    core.reset(initial_pc=0x200)
    assert core.pc == 0x200
    assert core.cycles == 0


def test_core_alu_operations(test_setup):
    core, flash, sram = test_setup
    # Write program:
    # 0x00: addi x1, x0, 10      (0x00A00093)
    # 0x04: addi x2, x0, -3      (0xFFD00113)
    # 0x08: add  x3, x1, x2      (0x002081B3)
    # 0x0C: sub  x4, x1, x2      (0x40208233)
    # 0x10: slt  x5, x2, x1      (0x001122B3)
    # 0x14: sltu x6, x2, x1      (0x00113333)
    # 0x18: xori x7, x1, 15      (0x00F0C393)
    # 0x1C: ori  x8, x1, 5       (0x0050E413)
    # 0x20: andi x9, x1, 2       (0x0020F493)
    program = [
        0x00A00093,
        0xFFD00113,
        0x002081B3,
        0x40208233,
        0x001122B3,
        0x00113333,
        0x00F0C393,
        0x0050E413,
        0x0020F493,
    ]
    for idx, inst in enumerate(program):
        flash.write32(idx * 4, inst)

    for _ in range(len(program)):
        res = core.step()
        assert res.trap is None

    assert core.registers.read(1) == 10
    assert core.registers.read_signed(2) == -3
    assert core.registers.read(3) == 7            # 10 + (-3)
    assert core.registers.read(4) == 13           # 10 - (-3)
    assert core.registers.read(5) == 1            # -3 < 10 signed
    assert core.registers.read(6) == 0            # 0xFFFFFFFD < 10 unsigned is False
    assert core.registers.read(7) == 10 ^ 15      # 5
    assert core.registers.read(8) == 10 | 5       # 15
    assert core.registers.read(9) == 10 & 2       # 2


def test_core_shift_operations(test_setup):
    core, flash, sram = test_setup
    # 0x00: addi x1, x0, 16      (0x01000093)
    # 0x04: slli x2, x1, 2       (0x00209113) -> 64
    # 0x08: srli x3, x2, 3       (0x00315193) -> 8
    # 0x0C: addi x4, x0, -16     (0xFF000213)
    # 0x10: srai x5, x4, 2       (0x40225293) -> -4
    program = [
        0x01000093,
        0x00209113,
        0x00315193,
        0xFF000213,
        0x40225293,
    ]
    for idx, inst in enumerate(program):
        flash.write32(idx * 4, inst)

    for _ in range(len(program)):
        core.step()

    assert core.registers.read(2) == 64
    assert core.registers.read(3) == 8
    assert core.registers.read_signed(5) == -4


def test_core_branches_and_jumps(test_setup):
    core, flash, sram = test_setup
    # 0x00: addi x1, x0, 5       (0x00500093)
    # 0x04: addi x2, x0, 5       (0x00500113)
    # 0x08: beq  x1, x2, 8       (0x00208463) -> jump to 0x10
    # 0x0C: addi x3, x0, 1       (0x00100193) (should be skipped)
    # 0x10: jal  x4, 8           (0x0080026F) -> jump to 0x18, x4 = 0x14
    # 0x14: addi x3, x0, 2       (should be skipped)
    # 0x18: ebreak               (0x00100073)
    flash.write32(0x00, 0x00500093)
    flash.write32(0x04, 0x00500113)
    flash.write32(0x08, 0x00208463)  # beq x1, x2, +8
    flash.write32(0x0C, 0x00100193)
    flash.write32(0x10, 0x0080026F)  # jal x4, +8
    flash.write32(0x14, 0x00200193)
    flash.write32(0x18, 0x00100073)  # ebreak

    # Step 1: addi x1
    core.step()
    assert core.pc == 0x04
    # Step 2: addi x2
    core.step()
    assert core.pc == 0x08
    # Step 3: beq taken
    core.step()
    assert core.pc == 0x10
    assert core.registers.read(3) == 0  # 0x0C skipped!
    # Step 4: jal
    core.step()
    assert core.pc == 0x18
    assert core.registers.read(4) == 0x14  # Link register has return address
    # Step 5: ebreak
    res = core.step()
    assert res.trap == TrapCause.BREAKPOINT
    assert core.halted is True


def test_core_memory_loads_and_stores(test_setup):
    core, flash, sram = test_setup
    # 0x00: lui  x1, 0x20000     (0x200000B7) -> x1 = 0x20000000
    # 0x04: addi x2, x0, 0x123   (0x12300113)
    # 0x08: sw   x2, 16(x1)      (0x0020A823) -> store at 0x20000010
    # 0x0C: lw   x3, 16(x1)      (0x0100A183) -> load back into x3
    # 0x10: addi x4, x0, -5      (0xFFB00213)
    # 0x14: sb   x4, 20(x1)      (store byte 0xFB at 0x20000014)
    # 0x18: lb   x5, 20(x1)      (load signed byte -> should be -5)
    # 0x1C: lbu  x6, 20(x1)      (load unsigned byte -> should be 251)
    flash.write32(0x00, 0x200000B7)
    flash.write32(0x04, 0x12300113)
    flash.write32(0x08, 0x0020A823)
    flash.write32(0x0C, 0x0100A183)
    flash.write32(0x10, 0xFFB00213)
    flash.write32(0x14, 0x00408A23)  # sb x4, 20(x1) -> funct3=0, opcode=0x23
    flash.write32(0x18, 0x01408283)  # lb x5, 20(x1) -> funct3=0, opcode=0x03
    flash.write32(0x1C, 0x0140C303)  # lbu x6, 20(x1) -> funct3=4, opcode=0x03

    for _ in range(8):
        core.step()

    assert sram.read32(0x10) == 0x123
    assert core.registers.read(3) == 0x123
    assert core.registers.read_signed(5) == -5
    assert core.registers.read(6) == 251


def test_core_csrs_and_traps(test_setup):
    core, flash, sram = test_setup
    # Test CSRRW: write x1 to CSR 0x340 (mscratch), read old into x2
    # csrrw x2, 0x340, x1
    core.registers.write(1, 0xAABBCCDD)
    raw_csrrw = (0x340 << 20) | (1 << 15) | (1 << 12) | (2 << 7) | 0x73
    flash.write32(0x00, raw_csrrw)

    core.step()
    assert core.registers.read_csr(0x340) == 0xAABBCCDD
    assert core.registers.read(2) == 0  # old value was 0

    # Misaligned PC trap
    core.pc = 0x03
    with pytest.raises(CpuTrap) as exc_info:
        core.step()
    assert exc_info.value.cause == TrapCause.INSTRUCTION_ADDRESS_MISALIGNED

    # Unmapped instruction fetch trap
    core.pc = 0x80000000
    with pytest.raises(CpuTrap) as exc_info:
        core.step()
    assert exc_info.value.cause == TrapCause.INSTRUCTION_ACCESS_FAULT
