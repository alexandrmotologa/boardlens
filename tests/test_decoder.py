"""Unit tests for the authentic RV32I instruction decoder."""

import pytest
from boardlens.cpu.rv32i.decoder import RV32IDecoder
from boardlens.cpu.rv32i.instructions import (
    DecodedInstruction,
    InstructionType,
    Mnemonic,
    Opcode,
)


def test_decode_lui_and_auipc():
    # lui x5, 0x12345000 (0x12345 << 12 | 5 << 7 | 0x37) = 0x123452B7
    raw = 0x123452B7
    inst = RV32IDecoder.decode(raw)
    assert inst.mnemonic == Mnemonic.LUI
    assert inst.instruction_type == InstructionType.U_TYPE
    assert inst.rd == 5
    assert inst.imm == 0x12345000
    assert "lui x5, 305418240" in str(inst)

    # auipc x10, 0x00001000 = 0x00001517
    raw_auipc = 0x00001517
    inst_auipc = RV32IDecoder.decode(raw_auipc)
    assert inst_auipc.mnemonic == Mnemonic.AUIPC
    assert inst_auipc.rd == 10
    assert inst_auipc.imm == 0x00001000


def test_decode_jal_and_jalr():
    # jal x1, 16 -> imm = 16 (0x010000EF)
    # jal x1, target: offset 16 -> bits: j20=0, j19_12=0, j11=0, j10_1=8 (16>>1=8) -> raw: (8<<21) | (1<<7) | 0x6F
    raw_jal = (8 << 21) | (1 << 7) | 0x6F
    inst_jal = RV32IDecoder.decode(raw_jal)
    assert inst_jal.mnemonic == Mnemonic.JAL
    assert inst_jal.instruction_type == InstructionType.J_TYPE
    assert inst_jal.rd == 1
    assert inst_jal.imm == 16

    # jalr x1, 4(x2) -> imm=4, rs1=2, rd=1, funct3=0, opcode=0x67
    raw_jalr = (4 << 20) | (2 << 15) | (0 << 12) | (1 << 7) | 0x67
    inst_jalr = RV32IDecoder.decode(raw_jalr)
    assert inst_jalr.mnemonic == Mnemonic.JALR
    assert inst_jalr.rd == 1
    assert inst_jalr.rs1 == 2
    assert inst_jalr.imm == 4
    assert str(inst_jalr) == "jalr x1, 4(x2)"


def test_decode_branch_instructions():
    # beq x1, x2, 16
    # imm=16 -> b12=0, b11=0, b10_5=0, b4_1=8
    raw_beq = (0 << 31) | (0 << 25) | (2 << 20) | (1 << 15) | (0 << 12) | (8 << 8) | (0 << 7) | 0x63
    inst = RV32IDecoder.decode(raw_beq)
    assert inst.mnemonic == Mnemonic.BEQ
    assert inst.instruction_type == InstructionType.B_TYPE
    assert inst.rs1 == 1
    assert inst.rs2 == 2
    assert inst.imm == 16

    # bne x1, x2, -4 (imm = -4 = 0x1FFC in 13-bit)
    # b12 = 1, b11 = 1, b10_5 = 0x3F, b4_1 = 0xE (14)
    raw_bne = (1 << 31) | (0x3F << 25) | (2 << 20) | (1 << 15) | (1 << 12) | (0xE << 8) | (1 << 7) | 0x63
    inst_bne = RV32IDecoder.decode(raw_bne)
    assert inst_bne.mnemonic == Mnemonic.BNE
    assert inst_bne.imm == -4


def test_decode_load_store():
    # lw x5, 12(x6)
    raw_lw = (12 << 20) | (6 << 15) | (2 << 12) | (5 << 7) | 0x03
    inst_lw = RV32IDecoder.decode(raw_lw)
    assert inst_lw.mnemonic == Mnemonic.LW
    assert inst_lw.rd == 5
    assert inst_lw.rs1 == 6
    assert inst_lw.imm == 12
    assert str(inst_lw) == "lw x5, 12(x6)"

    # sw x5, 12(x6)
    # imm[11:5] = 0, imm[4:0] = 12
    raw_sw = (0 << 25) | (5 << 20) | (6 << 15) | (2 << 12) | (12 << 7) | 0x23
    inst_sw = RV32IDecoder.decode(raw_sw)
    assert inst_sw.mnemonic == Mnemonic.SW
    assert inst_sw.rs2 == 5
    assert inst_sw.rs1 == 6
    assert inst_sw.imm == 12
    assert str(inst_sw) == "sw x5, 12(x6)"


def test_decode_op_imm():
    # addi x1, x0, 42
    raw_addi = (42 << 20) | (0 << 15) | (0 << 12) | (1 << 7) | 0x13
    inst = RV32IDecoder.decode(raw_addi)
    assert inst.mnemonic == Mnemonic.ADDI
    assert inst.rd == 1
    assert inst.rs1 == 0
    assert inst.imm == 42
    assert str(inst) == "addi x1, x0, 42"

    # slli x1, x2, 5
    raw_slli = (0 << 25) | (5 << 20) | (2 << 15) | (1 << 12) | (1 << 7) | 0x13
    inst_slli = RV32IDecoder.decode(raw_slli)
    assert inst_slli.mnemonic == Mnemonic.SLLI
    assert inst_slli.imm == 5

    # srai x1, x2, 5
    raw_srai = (0x20 << 25) | (5 << 20) | (2 << 15) | (5 << 12) | (1 << 7) | 0x13
    inst_srai = RV32IDecoder.decode(raw_srai)
    assert inst_srai.mnemonic == Mnemonic.SRAI
    assert inst_srai.imm == 5


def test_decode_op_r_type():
    # add x3, x1, x2
    raw_add = (0 << 25) | (2 << 20) | (1 << 15) | (0 << 12) | (3 << 7) | 0x33
    inst_add = RV32IDecoder.decode(raw_add)
    assert inst_add.mnemonic == Mnemonic.ADD
    assert inst_add.rd == 3
    assert inst_add.rs1 == 1
    assert inst_add.rs2 == 2
    assert str(inst_add) == "add x3, x1, x2"

    # sub x4, x1, x2
    raw_sub = (0x20 << 25) | (2 << 20) | (1 << 15) | (0 << 12) | (4 << 7) | 0x33
    inst_sub = RV32IDecoder.decode(raw_sub)
    assert inst_sub.mnemonic == Mnemonic.SUB
    assert inst_sub.rd == 4


def test_decode_system_ecall_ebreak():
    # ecall = 0x00000073
    inst_ecall = RV32IDecoder.decode(0x00000073)
    assert inst_ecall.mnemonic == Mnemonic.ECALL
    assert str(inst_ecall) == "ecall"

    # ebreak = 0x00100073
    inst_ebreak = RV32IDecoder.decode(0x00100073)
    assert inst_ebreak.mnemonic == Mnemonic.EBREAK
    assert str(inst_ebreak) == "ebreak"

    # csrrw x1, 0x300, x2
    raw_csrrw = (0x300 << 20) | (2 << 15) | (1 << 12) | (1 << 7) | 0x73
    inst_csrrw = RV32IDecoder.decode(raw_csrrw)
    assert inst_csrrw.mnemonic == Mnemonic.CSRRW
    assert inst_csrrw.imm == 0x300
    assert inst_csrrw.rd == 1
    assert inst_csrrw.rs1 == 2
