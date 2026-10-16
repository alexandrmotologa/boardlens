"""Unit tests for ARM Cortex-M Thumb execution core and decoder."""

import pytest
from boardlens.cpu.arm.core import ARMCortexMCore
from boardlens.cpu.arm.decoder import ThumbDecoder, ThumbMnemonic
from boardlens.cpu.base import CpuTrap, TrapCause
from boardlens.memory.bus import MemoryBus
from boardlens.memory.ram import RAM


@pytest.fixture
def arm_setup():
    bus = MemoryBus()
    flash = RAM(base_address=0x08000000, size=0x10000, name="FLASH")
    sram = RAM(base_address=0x20000000, size=0x10000, name="SRAM")
    bus.map_region(flash)
    bus.map_region(sram)
    core = ARMCortexMCore(bus=bus, initial_pc=0x08000000)
    return core, flash, sram


def test_thumb_decoder():
    # movs r1, #42 -> 0x212A
    inst_mov = ThumbDecoder.decode(0x212A)
    assert inst_mov.mnemonic == ThumbMnemonic.MOVS
    assert inst_mov.rd == 1
    assert inst_mov.imm == 42
    assert "movs r1, #42" in str(inst_mov)

    # adds r2, r1, #5 -> 0x1D4A
    inst_add = ThumbDecoder.decode(0x1D4A)
    assert inst_add.mnemonic == ThumbMnemonic.ADDS
    assert inst_add.rd == 2
    assert inst_add.rn == 1
    assert inst_add.imm == 5

    # bkpt #0 -> 0xBE00
    inst_bkpt = ThumbDecoder.decode(0xBE00)
    assert inst_bkpt.mnemonic == ThumbMnemonic.BKPT
    assert str(inst_bkpt) == "bkpt #0"


def test_arm_core_execution(arm_setup):
    core, flash, sram = arm_setup
    # 0x00: movs r0, #10     (0x200A)
    # 0x02: movs r1, #25     (0x2119)
    # 0x04: adds r2, r0, r1  (0x1842)
    # 0x06: cmp  r2, #35     (0x2A23)
    # 0x08: b.eq +4          (0xD002) -> jump to 0x10 (0x08 + 4 + 4 = 0x10)
    # 0x0A: movs r3, #99     (0x2363) (skipped)
    # 0x0C: movs r3, #99     (0x2363) (skipped)
    # 0x0E: bkpt #0          (0xBE00) (skipped)
    # 0x10: movs r3, #1      (0x2301)
    # 0x12: bkpt #1          (0xBE01)
    flash.write16(0x00, 0x200A)
    flash.write16(0x02, 0x2119)
    flash.write16(0x04, 0x1842)  # adds r2, r0, r1 (rm=1, rn=0, rd=2)
    flash.write16(0x06, 0x2A23)  # cmp r2, #35
    flash.write16(0x08, 0xD002)  # beq offset=2 words (4 bytes)
    flash.write16(0x0A, 0x2363)
    flash.write16(0x0C, 0x2363)
    flash.write16(0x0E, 0xBE00)
    flash.write16(0x10, 0x2301)  # movs r3, #1
    flash.write16(0x12, 0xBE01)  # bkpt #1

    # Step 1: movs r0, #10
    core.step()
    assert core.registers.read(0) == 10

    # Step 2: movs r1, #25
    core.step()
    assert core.registers.read(1) == 25

    # Step 3: adds r2, r0, r1
    core.step()
    assert core.registers.read(2) == 35

    # Step 4: cmp r2, #35
    core.step()
    assert core.registers.z is True

    # Step 5: b.eq taken -> PC = 0x08000010
    core.step()
    assert core.pc == 0x08000010
    assert core.registers.read(3) == 0  # skipped!

    # Step 6: movs r3, #1
    core.step()
    assert core.registers.read(3) == 1

    # Step 7: bkpt
    res = core.step()
    assert res.trap == TrapCause.BREAKPOINT
    assert core.halted is True
