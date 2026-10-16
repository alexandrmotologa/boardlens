"""Authentic bit-level instruction decoder for RISC-V RV32I."""

from boardlens.cpu.rv32i.instructions import (
    DecodedInstruction,
    InstructionType,
    Mnemonic,
    Opcode,
)


def _sign_extend(val: int, bits: int) -> int:
    """Sign-extend a two's complement integer of given bit width."""
    sign_bit = 1 << (bits - 1)
    if val & sign_bit:
        return val - (1 << bits)
    return val


class RV32IDecoder:
    """Bit-level instruction decoder for 32-bit RV32I instructions."""

    @staticmethod
    def decode(raw: int) -> DecodedInstruction:
        raw = raw & 0xFFFFFFFF
        opcode_val = raw & 0x7F
        rd = (raw >> 7) & 0x1F
        funct3 = (raw >> 12) & 0x07
        rs1 = (raw >> 15) & 0x1F
        rs2 = (raw >> 20) & 0x1F
        funct7 = (raw >> 25) & 0x7F

        # Default values
        itype = InstructionType.UNKNOWN
        mnemonic = Mnemonic.ILLEGAL
        imm = 0

        if opcode_val == Opcode.LUI.value:
            itype = InstructionType.U_TYPE
            mnemonic = Mnemonic.LUI
            imm = raw & 0xFFFFF000

        elif opcode_val == Opcode.AUIPC.value:
            itype = InstructionType.U_TYPE
            mnemonic = Mnemonic.AUIPC
            imm = raw & 0xFFFFF000

        elif opcode_val == Opcode.JAL.value:
            itype = InstructionType.J_TYPE
            mnemonic = Mnemonic.JAL
            j20 = (raw >> 31) & 0x1
            j19_12 = (raw >> 12) & 0xFF
            j11 = (raw >> 20) & 0x1
            j10_1 = (raw >> 21) & 0x3FF
            raw_imm = (j20 << 20) | (j19_12 << 12) | (j11 << 11) | (j10_1 << 1)
            imm = _sign_extend(raw_imm, 21)

        elif opcode_val == Opcode.JALR.value:
            itype = InstructionType.I_TYPE
            mnemonic = Mnemonic.JALR
            imm = _sign_extend((raw >> 20) & 0xFFF, 12)

        elif opcode_val == Opcode.BRANCH.value:
            itype = InstructionType.B_TYPE
            b12 = (raw >> 31) & 0x1
            b11 = (raw >> 7) & 0x1
            b10_5 = (raw >> 25) & 0x3F
            b4_1 = (raw >> 8) & 0xF
            raw_imm = (b12 << 12) | (b11 << 11) | (b10_5 << 5) | (b4_1 << 1)
            imm = _sign_extend(raw_imm, 13)

            branch_map = {
                0x0: Mnemonic.BEQ,
                0x1: Mnemonic.BNE,
                0x4: Mnemonic.BLT,
                0x5: Mnemonic.BGE,
                0x6: Mnemonic.BLTU,
                0x7: Mnemonic.BGEU,
            }
            mnemonic = branch_map.get(funct3, Mnemonic.ILLEGAL)

        elif opcode_val == Opcode.LOAD.value:
            itype = InstructionType.I_TYPE
            imm = _sign_extend((raw >> 20) & 0xFFF, 12)
            load_map = {
                0x0: Mnemonic.LB,
                0x1: Mnemonic.LH,
                0x2: Mnemonic.LW,
                0x4: Mnemonic.LBU,
                0x5: Mnemonic.LHU,
            }
            mnemonic = load_map.get(funct3, Mnemonic.ILLEGAL)

        elif opcode_val == Opcode.STORE.value:
            itype = InstructionType.S_TYPE
            raw_imm = ((raw >> 25) << 5) | ((raw >> 7) & 0x1F)
            imm = _sign_extend(raw_imm, 12)
            store_map = {
                0x0: Mnemonic.SB,
                0x1: Mnemonic.SH,
                0x2: Mnemonic.SW,
            }
            mnemonic = store_map.get(funct3, Mnemonic.ILLEGAL)

        elif opcode_val == Opcode.OP_IMM.value:
            itype = InstructionType.I_TYPE
            raw_imm = (raw >> 20) & 0xFFF
            imm = _sign_extend(raw_imm, 12)

            if funct3 == 0x0:
                mnemonic = Mnemonic.ADDI
            elif funct3 == 0x1:
                # SLLI (shamt is imm[4:0], funct7 should be 0x00)
                mnemonic = Mnemonic.SLLI
                imm = raw_imm & 0x1F
            elif funct3 == 0x2:
                mnemonic = Mnemonic.SLTI
            elif funct3 == 0x3:
                mnemonic = Mnemonic.SLTIU
            elif funct3 == 0x4:
                mnemonic = Mnemonic.XORI
            elif funct3 == 0x5:
                # SRLI or SRAI
                shamt = raw_imm & 0x1F
                imm = shamt
                if funct7 == 0x00:
                    mnemonic = Mnemonic.SRLI
                elif funct7 == 0x20:
                    mnemonic = Mnemonic.SRAI
                else:
                    mnemonic = Mnemonic.ILLEGAL
            elif funct3 == 0x6:
                mnemonic = Mnemonic.ORI
            elif funct3 == 0x7:
                mnemonic = Mnemonic.ANDI

        elif opcode_val == Opcode.OP.value:
            itype = InstructionType.R_TYPE
            imm = 0
            if funct7 == 0x00:
                op_map = {
                    0x0: Mnemonic.ADD,
                    0x1: Mnemonic.SLL,
                    0x2: Mnemonic.SLT,
                    0x3: Mnemonic.SLTU,
                    0x4: Mnemonic.XOR,
                    0x5: Mnemonic.SRL,
                    0x6: Mnemonic.OR,
                    0x7: Mnemonic.AND,
                }
                mnemonic = op_map.get(funct3, Mnemonic.ILLEGAL)
            elif funct7 == 0x20:
                if funct3 == 0x0:
                    mnemonic = Mnemonic.SUB
                elif funct3 == 0x5:
                    mnemonic = Mnemonic.SRA
                else:
                    mnemonic = Mnemonic.ILLEGAL
            else:
                mnemonic = Mnemonic.ILLEGAL

        elif opcode_val == Opcode.MISC_MEM.value:
            itype = InstructionType.I_TYPE
            mnemonic = Mnemonic.FENCE

        elif opcode_val == Opcode.SYSTEM.value:
            itype = InstructionType.I_TYPE
            raw_imm = (raw >> 20) & 0xFFF
            imm = raw_imm

            if funct3 == 0x0:
                if raw_imm == 0x0:
                    mnemonic = Mnemonic.ECALL
                elif raw_imm == 0x1:
                    mnemonic = Mnemonic.EBREAK
                else:
                    mnemonic = Mnemonic.ILLEGAL
            elif funct3 == 0x1:
                mnemonic = Mnemonic.CSRRW
            elif funct3 == 0x2:
                mnemonic = Mnemonic.CSRRS
            elif funct3 == 0x3:
                mnemonic = Mnemonic.CSRRC
            elif funct3 == 0x5:
                mnemonic = Mnemonic.CSRRWI
            elif funct3 == 0x6:
                mnemonic = Mnemonic.CSRRSI
            elif funct3 == 0x7:
                mnemonic = Mnemonic.CSRRCI

        return DecodedInstruction(
            raw=raw,
            opcode=opcode_val,
            rd=rd,
            rs1=rs1,
            rs2=rs2,
            funct3=funct3,
            funct7=funct7,
            imm=imm,
            instruction_type=itype,
            mnemonic=mnemonic,
        )
