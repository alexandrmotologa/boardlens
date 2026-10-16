"""Authentic RISC-V RV32I two-pass assembler."""

import re
from typing import Dict, List, Optional, Tuple, Union
from boardlens.cpu.registers import RV32IRegisters
from boardlens.cpu.rv32i.instructions import Opcode


class AssemblerError(Exception):
    """Raised when assembly syntax or symbol resolution fails."""
    pass


class Assembler:
    """Two-pass assembler for RISC-V RV32I source code."""

    def __init__(self, base_address: int = 0x00000000) -> None:
        self.base_address = base_address
        self.labels: Dict[str, int] = {}
        self.constants: Dict[str, int] = {}

    @property
    def symbols(self) -> Dict[str, int]:
        """Dictionary of resolved label symbols to memory addresses."""
        return self.labels


    def _parse_reg(self, token: str) -> int:
        clean = token.strip().rstrip(",")
        try:
            return RV32IRegisters.NAME_TO_INDEX[clean.lower()]
        except KeyError:
            raise AssemblerError(f"Unknown register name '{token}'")

    def _parse_imm(self, token: str) -> int:
        clean = token.strip().rstrip(",")
        if clean in self.constants:
            return self.constants[clean]
        if clean in self.labels:
            return self.labels[clean]
        try:
            if clean.startswith("0x") or clean.startswith("0X"):
                return int(clean, 16)
            if clean.startswith("0b") or clean.startswith("0B"):
                return int(clean, 2)
            return int(clean)
        except ValueError:
            raise AssemblerError(f"Cannot parse immediate or symbol '{token}'")

    def _parse_mem_operand(self, token: str) -> Tuple[int, int]:
        """Parse 'offset(base)' e.g. '12(x6)' or '0x10(sp)'."""
        clean = token.strip().rstrip(",")
        m = re.match(r"^([^\(]+)\(([^)]+)\)$", clean)
        if not m:
            raise AssemblerError(f"Malformed memory operand: '{token}'. Expected 'offset(reg)'")
        imm_str = m.group(1).strip()
        reg_str = m.group(2).strip()
        imm = self._parse_imm(imm_str)
        reg = self._parse_reg(reg_str)
        return imm, reg

    # Instruction Encoders
    @staticmethod
    def _encode_r(opcode: int, funct3: int, funct7: int, rd: int, rs1: int, rs2: int) -> int:
        return (
            ((funct7 & 0x7F) << 25)
            | ((rs2 & 0x1F) << 20)
            | ((rs1 & 0x1F) << 15)
            | ((funct3 & 0x7) << 12)
            | ((rd & 0x1F) << 7)
            | (opcode & 0x7F)
        )

    @staticmethod
    def _encode_i(opcode: int, funct3: int, rd: int, rs1: int, imm: int) -> int:
        return (
            ((imm & 0xFFF) << 20)
            | ((rs1 & 0x1F) << 15)
            | ((funct3 & 0x7) << 12)
            | ((rd & 0x1F) << 7)
            | (opcode & 0x7F)
        )

    @staticmethod
    def _encode_s(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
        imm11_5 = (imm >> 5) & 0x7F
        imm4_0 = imm & 0x1F
        return (
            (imm11_5 << 25)
            | ((rs2 & 0x1F) << 20)
            | ((rs1 & 0x1F) << 15)
            | ((funct3 & 0x7) << 12)
            | (imm4_0 << 7)
            | (opcode & 0x7F)
        )

    @staticmethod
    def _encode_b(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
        b12 = (imm >> 12) & 1
        b11 = (imm >> 11) & 1
        b10_5 = (imm >> 5) & 0x3F
        b4_1 = (imm >> 1) & 0xF
        return (
            (b12 << 31)
            | (b10_5 << 25)
            | ((rs2 & 0x1F) << 20)
            | ((rs1 & 0x1F) << 15)
            | ((funct3 & 0x7) << 12)
            | (b4_1 << 8)
            | (b11 << 7)
            | (opcode & 0x7F)
        )

    @staticmethod
    def _encode_u(opcode: int, rd: int, imm: int) -> int:
        if 0 <= imm < 0x100000:
            u_imm = (imm << 12) & 0xFFFFF000
        else:
            u_imm = imm & 0xFFFFF000
        return u_imm | ((rd & 0x1F) << 7) | (opcode & 0x7F)

    @staticmethod
    def _encode_j(opcode: int, rd: int, imm: int) -> int:
        j20 = (imm >> 20) & 1
        j19_12 = (imm >> 12) & 0xFF
        j11 = (imm >> 11) & 1
        j10_1 = (imm >> 1) & 0x3FF
        return (
            (j20 << 31)
            | (j10_1 << 21)
            | (j11 << 20)
            | (j19_12 << 12)
            | ((rd & 0x1F) << 7)
            | (opcode & 0x7F)
        )

    def assemble(self, source: str) -> bytes:
        """Assemble multi-line RV32I source code into binary bytes."""
        lines = source.splitlines()
        output_words: List[int] = []

        # Pass 1: Collect labels and clean instructions
        current_pc = self.base_address
        cleaned_statements: List[Tuple[int, str, List[str]]] = []

        for line_num, raw_line in enumerate(lines, 1):
            # Strip comments and whitespace
            line = re.sub(r"[#;].*$", "", raw_line).strip()
            if not line:
                continue

            # Check for label
            while ":" in line:
                label_part, rest = line.split(":", 1)
                label_name = label_part.strip()
                if label_name:
                    self.labels[label_name] = current_pc
                line = rest.strip()

            if not line:
                continue

            tokens = re.split(r"[\s,]+", line)
            mnem = tokens[0].lower()
            args = tokens[1:]

            # Directives
            if mnem == ".equ":
                self.constants[args[0]] = self._parse_imm(args[1])
                continue
            elif mnem in (".text", ".data"):
                continue
            elif mnem == ".word":
                current_pc += 4 * len(args)
                cleaned_statements.append((current_pc - 4 * len(args), mnem, args))
                continue
            elif mnem == ".byte":
                current_pc += len(args)
                cleaned_statements.append((current_pc - len(args), mnem, args))
                continue

            # Pseudo-instructions expansion size
            if mnem == "li":
                # Check if fits in 12-bit signed (-2048 to 2047)
                imm_token = args[1]
                try:
                    imm_val = self._parse_imm(imm_token)
                    if -2048 <= imm_val <= 2047:
                        inst_size = 4
                    else:
                        inst_size = 8  # lui + addi
                except AssemblerError:
                    inst_size = 8  # assume 8 if label/symbol
                cleaned_statements.append((current_pc, mnem, args))
                current_pc += inst_size
            else:
                cleaned_statements.append((current_pc, mnem, args))
                current_pc += 4

        # Pass 2: Instruction encoding
        bin_data = bytearray()

        for stmt_pc, mnem, args in cleaned_statements:
            if mnem == ".word":
                for a in args:
                    val = self._parse_imm(a) & 0xFFFFFFFF
                    bin_data.extend(val.to_bytes(4, byteorder="little"))
                continue
            if mnem == ".byte":
                for a in args:
                    val = self._parse_imm(a) & 0xFF
                    bin_data.append(val)
                continue

            words = self._encode_instruction(stmt_pc, mnem, args)
            for w in words:
                bin_data.extend((w & 0xFFFFFFFF).to_bytes(4, byteorder="little"))

        return bytes(bin_data)

    def _encode_instruction(self, pc: int, mnem: str, args: List[str]) -> List[int]:
        """Encode a single statement into one or more 32-bit machine code words."""
        # Pseudo-instructions
        if mnem == "nop":
            return [self._encode_i(Opcode.OP_IMM.value, 0, 0, 0, 0)]  # addi x0, x0, 0

        if mnem == "mv":
            rd = self._parse_reg(args[0])
            rs = self._parse_reg(args[1])
            return [self._encode_i(Opcode.OP_IMM.value, 0, rd, rs, 0)]  # addi rd, rs, 0

        if mnem == "not":
            rd = self._parse_reg(args[0])
            rs = self._parse_reg(args[1])
            return [self._encode_i(Opcode.OP_IMM.value, 4, rd, rs, -1)]  # xori rd, rs, -1

        if mnem == "neg":
            rd = self._parse_reg(args[0])
            rs = self._parse_reg(args[1])
            return [self._encode_r(Opcode.OP.value, 0, 0x20, rd, 0, rs)]  # sub rd, x0, rs

        if mnem == "j":
            target = self._parse_imm(args[0])
            offset = target - pc
            return [self._encode_j(Opcode.JAL.value, 0, offset)]

        if mnem == "jr":
            rs = self._parse_reg(args[0])
            return [self._encode_i(Opcode.JALR.value, 0, 0, rs, 0)]

        if mnem == "ret":
            return [self._encode_i(Opcode.JALR.value, 0, 0, 1, 0)]  # jalr x0, ra, 0

        if mnem == "call":
            target = self._parse_imm(args[0])
            offset = target - pc
            return [self._encode_j(Opcode.JAL.value, 1, offset)]  # jal ra, offset

        if mnem == "beqz":
            rs = self._parse_reg(args[0])
            target = self._parse_imm(args[1])
            return [self._encode_b(Opcode.BRANCH.value, 0, rs, 0, target - pc)]

        if mnem == "bnez":
            rs = self._parse_reg(args[0])
            target = self._parse_imm(args[1])
            return [self._encode_b(Opcode.BRANCH.value, 1, rs, 0, target - pc)]

        if mnem == "li":
            rd = self._parse_reg(args[0])
            imm = self._parse_imm(args[1])
            if -2048 <= imm <= 2047:
                return [self._encode_i(Opcode.OP_IMM.value, 0, rd, 0, imm)]
            else:
                upper = (imm + 0x800) >> 12
                lower = imm - (upper << 12)
                lui_w = self._encode_u(Opcode.LUI.value, rd, upper)
                addi_w = self._encode_i(Opcode.OP_IMM.value, 0, rd, rd, lower)
                return [lui_w, addi_w]

        # U-Type
        if mnem == "lui":
            rd = self._parse_reg(args[0])
            imm = self._parse_imm(args[1])
            return [self._encode_u(Opcode.LUI.value, rd, imm)]

        if mnem == "auipc":
            rd = self._parse_reg(args[0])
            imm = self._parse_imm(args[1])
            return [self._encode_u(Opcode.AUIPC.value, rd, imm)]

        # J-Type
        if mnem == "jal":
            if len(args) == 1:
                rd = 1
                target = self._parse_imm(args[0])
            else:
                rd = self._parse_reg(args[0])
                target = self._parse_imm(args[1])
            offset = target - pc
            return [self._encode_j(Opcode.JAL.value, rd, offset)]

        # I-Type Jumps
        if mnem == "jalr":
            rd = self._parse_reg(args[0])
            if len(args) == 2:
                imm, rs1 = self._parse_mem_operand(args[1])
            else:
                rs1 = self._parse_reg(args[1])
                imm = self._parse_imm(args[2]) if len(args) > 2 else 0
            return [self._encode_i(Opcode.JALR.value, 0, rd, rs1, imm)]

        # B-Type Branches
        branch_funct3 = {
            "beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7
        }
        if mnem in branch_funct3:
            rs1 = self._parse_reg(args[0])
            rs2 = self._parse_reg(args[1])
            target = self._parse_imm(args[2])
            offset = target - pc
            return [self._encode_b(Opcode.BRANCH.value, branch_funct3[mnem], rs1, rs2, offset)]

        # Loads
        load_funct3 = {
            "lb": 0, "lh": 1, "lw": 2, "lbu": 4, "lhu": 5
        }
        if mnem in load_funct3:
            rd = self._parse_reg(args[0])
            imm, rs1 = self._parse_mem_operand(args[1])
            return [self._encode_i(Opcode.LOAD.value, load_funct3[mnem], rd, rs1, imm)]

        # Stores
        store_funct3 = {
            "sb": 0, "sh": 1, "sw": 2
        }
        if mnem in store_funct3:
            rs2 = self._parse_reg(args[0])
            imm, rs1 = self._parse_mem_operand(args[1])
            return [self._encode_s(Opcode.STORE.value, store_funct3[mnem], rs1, rs2, imm)]

        # I-Type ALU
        op_imm_map = {
            "addi": (0, 0),
            "slli": (1, 0),
            "slti": (2, 0),
            "sltiu": (3, 0),
            "xori": (4, 0),
            "srli": (5, 0),
            "srai": (5, 0x20),
            "ori": (6, 0),
            "andi": (7, 0),
        }
        if mnem in op_imm_map:
            rd = self._parse_reg(args[0])
            rs1 = self._parse_reg(args[1])
            imm = self._parse_imm(args[2])
            f3, f7 = op_imm_map[mnem]
            if mnem in ("slli", "srli", "srai"):
                imm_encoded = ((f7 & 0x7F) << 5) | (imm & 0x1F)
            else:
                imm_encoded = imm & 0xFFF
            return [self._encode_i(Opcode.OP_IMM.value, f3, rd, rs1, imm_encoded)]

        # R-Type ALU
        r_type_map = {
            "add": (0, 0x00),
            "sub": (0, 0x20),
            "sll": (1, 0x00),
            "slt": (2, 0x00),
            "sltu": (3, 0x00),
            "xor": (4, 0x00),
            "srl": (5, 0x00),
            "sra": (5, 0x20),
            "or": (6, 0x00),
            "and": (7, 0x00),
        }
        if mnem in r_type_map:
            rd = self._parse_reg(args[0])
            rs1 = self._parse_reg(args[1])
            rs2 = self._parse_reg(args[2])
            f3, f7 = r_type_map[mnem]
            return [self._encode_r(Opcode.OP.value, f3, f7, rd, rs1, rs2)]

        # System
        if mnem == "ecall":
            return [0x00000073]
        if mnem == "ebreak":
            return [0x00100073]
        if mnem in ("csrrw", "csrrs", "csrrc"):
            f3_map = {"csrrw": 1, "csrrs": 2, "csrrc": 3}
            rd = self._parse_reg(args[0])
            csr = self._parse_imm(args[1])
            rs1 = self._parse_reg(args[2])
            return [self._encode_i(Opcode.SYSTEM.value, f3_map[mnem], rd, rs1, csr & 0xFFF)]

        raise AssemblerError(f"Unsupported instruction or directive: '{mnem}'")


def assemble(source: str, base_address: int = 0x00000000) -> bytes:
    """Convenience helper to assemble RV32I source code directly."""
    return Assembler(base_address=base_address).assemble(source)
