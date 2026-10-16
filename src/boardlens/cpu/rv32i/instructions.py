"""Instruction formats, opcode enums, and decoded instruction models for RV32I."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InstructionType(Enum):
    """RV32I Instruction encoding types."""
    R_TYPE = "R"
    I_TYPE = "I"
    S_TYPE = "S"
    B_TYPE = "B"
    U_TYPE = "U"
    J_TYPE = "J"
    UNKNOWN = "?"


class Opcode(Enum):
    """Major 7-bit RV32I opcodes."""
    LUI = 0x37       # 0b0110111
    AUIPC = 0x17     # 0b0010111
    JAL = 0x6F       # 0b1101111
    JALR = 0x67      # 0b1100111
    BRANCH = 0x63    # 0b1100011
    LOAD = 0x03      # 0b0000011
    STORE = 0x23     # 0b0100011
    OP_IMM = 0x13    # 0b0010011
    OP = 0x33        # 0b0110011
    MISC_MEM = 0x0F  # 0b0001111 (FENCE)
    SYSTEM = 0x73    # 0b1110011


class Mnemonic(Enum):
    """All standard RV32I instructions."""
    # U-type
    LUI = "lui"
    AUIPC = "auipc"
    # J-type
    JAL = "jal"
    # I-type Jumps & Loads
    JALR = "jalr"
    LB = "lb"
    LH = "lh"
    LW = "lw"
    LBU = "lbu"
    LHU = "lhu"
    # B-type
    BEQ = "beq"
    BNE = "bne"
    BLT = "blt"
    BGE = "bge"
    BLTU = "bltu"
    BGEU = "bgeu"
    # S-type
    SB = "sb"
    SH = "sh"
    SW = "sw"
    # I-type ALU
    ADDI = "addi"
    SLTI = "slti"
    SLTIU = "sltiu"
    XORI = "xori"
    ORI = "ori"
    ANDI = "andi"
    SLLI = "slli"
    SRLI = "srli"
    SRAI = "srai"
    # R-type ALU
    ADD = "add"
    SUB = "sub"
    SLL = "sll"
    SLT = "slt"
    SLTU = "sltu"
    XOR = "xor"
    SRL = "srl"
    SRA = "sra"
    OR = "or"
    AND = "and"
    # System & Fence
    FENCE = "fence"
    ECALL = "ecall"
    EBREAK = "ebreak"
    CSRRW = "csrrw"
    CSRRS = "csrrs"
    CSRRC = "csrrc"
    CSRRWI = "csrrwi"
    CSRRSI = "csrrsi"
    CSRRCI = "csrrci"
    ILLEGAL = "illegal"


@dataclass(frozen=True)
class DecodedInstruction:
    """Authentic parsed RV32I instruction with extracted bitfields."""
    raw: int
    opcode: int
    rd: int
    rs1: int
    rs2: int
    funct3: int
    funct7: int
    imm: int
    instruction_type: InstructionType
    mnemonic: Mnemonic

    @property
    def hex_code(self) -> str:
        return f"0x{self.raw:08X}"

    def __str__(self) -> str:
        mnem = self.mnemonic.value
        itype = self.instruction_type

        if self.mnemonic in (Mnemonic.ECALL, Mnemonic.EBREAK, Mnemonic.FENCE):
            return mnem

        if itype == InstructionType.U_TYPE or itype == InstructionType.J_TYPE:
            return f"{mnem} x{self.rd}, {self.imm}"

        if self.mnemonic == Mnemonic.JALR:
            return f"{mnem} x{self.rd}, {self.imm}(x{self.rs1})"

        if itype == InstructionType.I_TYPE:
            if self.mnemonic in (Mnemonic.LB, Mnemonic.LH, Mnemonic.LW, Mnemonic.LBU, Mnemonic.LHU):
                return f"{mnem} x{self.rd}, {self.imm}(x{self.rs1})"
            if self.mnemonic in (Mnemonic.CSRRW, Mnemonic.CSRRS, Mnemonic.CSRRC):
                return f"{mnem} x{self.rd}, 0x{self.imm & 0xFFF:X}, x{self.rs1}"
            if self.mnemonic in (Mnemonic.CSRRWI, Mnemonic.CSRRSI, Mnemonic.CSRRCI):
                return f"{mnem} x{self.rd}, 0x{self.imm & 0xFFF:X}, {self.rs1}"
            return f"{mnem} x{self.rd}, x{self.rs1}, {self.imm}"

        if itype == InstructionType.S_TYPE:
            return f"{mnem} x{self.rs2}, {self.imm}(x{self.rs1})"

        if itype == InstructionType.B_TYPE:
            return f"{mnem} x{self.rs1}, x{self.rs2}, {self.imm}"

        if itype == InstructionType.R_TYPE:
            return f"{mnem} x{self.rd}, x{self.rs1}, x{self.rs2}"

        return f"{mnem} (raw={self.hex_code})"
