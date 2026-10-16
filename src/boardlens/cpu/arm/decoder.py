"""Authentic 16-bit Thumb instruction decoder for ARM Cortex-M."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ThumbMnemonic(Enum):
    LSLS = "lsls"
    LSRS = "lsrs"
    ASRS = "asrs"
    ADDS = "adds"
    SUBS = "subs"
    MOVS = "movs"
    CMP = "cmp"
    ANDS = "ands"
    EORS = "eors"
    ORRS = "orrs"
    BICS = "bics"
    MVNS = "mvns"
    BX = "bx"
    BL = "bl"
    B = "b"
    B_COND = "b.cond"
    LDR = "ldr"
    STR = "str"
    LDRB = "ldrb"
    STRB = "strb"
    LDRH = "ldrh"
    STRH = "strh"
    BKPT = "bkpt"
    NOP = "nop"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DecodedThumbInstruction:
    raw: int
    mnemonic: ThumbMnemonic
    rd: int
    rn: int
    rm: int
    imm: int
    cond: Optional[int] = None

    def __str__(self) -> str:
        mnem = self.mnemonic.value
        if self.mnemonic == ThumbMnemonic.MOVS:
            return f"{mnem} r{self.rd}, #{self.imm}"
        if self.mnemonic in (ThumbMnemonic.ADDS, ThumbMnemonic.SUBS):
            if self.rm != -1:
                return f"{mnem} r{self.rd}, r{self.rn}, r{self.rm}"
            return f"{mnem} r{self.rd}, r{self.rn}, #{self.imm}"
        if self.mnemonic in (ThumbMnemonic.LDR, ThumbMnemonic.STR):
            return f"{mnem} r{self.rd}, [r{self.rn}, #{self.imm}]"
        if self.mnemonic == ThumbMnemonic.B:
            return f"b #{self.imm}"
        if self.mnemonic == ThumbMnemonic.B_COND:
            return f"b<cond:{self.cond}> #{self.imm}"
        if self.mnemonic == ThumbMnemonic.BX:
            return f"bx r{self.rm}"
        if self.mnemonic == ThumbMnemonic.BKPT:
            return f"bkpt #{self.imm}"
        return f"{mnem} (raw=0x{self.raw:04X})"


class ThumbDecoder:
    """16-bit Thumb instruction decoder."""

    @staticmethod
    def decode(raw: int) -> DecodedThumbInstruction:
        raw = raw & 0xFFFF
        top5 = (raw >> 11) & 0x1F

        # Format 1: Move shifted register
        # 000xx: LSLS, LSRS, ASRS
        if (raw >> 13) == 0:
            op = (raw >> 11) & 0x3
            offset5 = (raw >> 6) & 0x1F
            rm = (raw >> 3) & 0x7
            rd = raw & 0x7
            if op == 0:
                return DecodedThumbInstruction(raw, ThumbMnemonic.LSLS, rd=rd, rn=rm, rm=-1, imm=offset5)
            elif op == 1:
                return DecodedThumbInstruction(raw, ThumbMnemonic.LSRS, rd=rd, rn=rm, rm=-1, imm=offset5)
            elif op == 2:
                return DecodedThumbInstruction(raw, ThumbMnemonic.ASRS, rd=rd, rn=rm, rm=-1, imm=offset5)
            else:
                # Format 2: Add/subtract (00011xx)
                # op: 00=ADD reg, 01=SUB reg, 10=ADD 3-bit imm, 11=SUB 3-bit imm
                sub_op = (raw >> 9) & 0x3
                rn = (raw >> 3) & 0x7
                if sub_op == 0:
                    rm_reg = (raw >> 6) & 0x7
                    return DecodedThumbInstruction(raw, ThumbMnemonic.ADDS, rd=rd, rn=rn, rm=rm_reg, imm=0)
                elif sub_op == 1:
                    rm_reg = (raw >> 6) & 0x7
                    return DecodedThumbInstruction(raw, ThumbMnemonic.SUBS, rd=rd, rn=rn, rm=rm_reg, imm=0)
                elif sub_op == 2:
                    imm3 = (raw >> 6) & 0x7
                    return DecodedThumbInstruction(raw, ThumbMnemonic.ADDS, rd=rd, rn=rn, rm=-1, imm=imm3)
                else:
                    imm3 = (raw >> 6) & 0x7
                    return DecodedThumbInstruction(raw, ThumbMnemonic.SUBS, rd=rd, rn=rn, rm=-1, imm=imm3)

        # Format 3: Move/compare/add/subtract immediate (001xx)
        if (raw >> 13) == 1:
            op = (raw >> 11) & 0x3
            rd = (raw >> 8) & 0x7
            imm8 = raw & 0xFF
            if op == 0:
                return DecodedThumbInstruction(raw, ThumbMnemonic.MOVS, rd=rd, rn=-1, rm=-1, imm=imm8)
            elif op == 1:
                return DecodedThumbInstruction(raw, ThumbMnemonic.CMP, rd=-1, rn=rd, rm=-1, imm=imm8)
            elif op == 2:
                return DecodedThumbInstruction(raw, ThumbMnemonic.ADDS, rd=rd, rn=rd, rm=-1, imm=imm8)
            else:
                return DecodedThumbInstruction(raw, ThumbMnemonic.SUBS, rd=rd, rn=rd, rm=-1, imm=imm8)

        # Format 4: ALU operations (010000xxxx)
        if (raw >> 10) == 0x10:
            alu_op = (raw >> 6) & 0xF
            rm = (raw >> 3) & 0x7
            rd = raw & 0x7
            alu_map = {
                0x0: ThumbMnemonic.ANDS,
                0x1: ThumbMnemonic.EORS,
                0xC: ThumbMnemonic.ORRS,
                0xE: ThumbMnemonic.BICS,
                0xF: ThumbMnemonic.MVNS,
            }
            mnem = alu_map.get(alu_op, ThumbMnemonic.UNKNOWN)
            return DecodedThumbInstruction(raw, mnem, rd=rd, rn=rd, rm=rm, imm=0)

        # Format 5: Hi register ops / branch exchange (010001xxxx)
        if (raw >> 10) == 0x11:
            h_op = (raw >> 8) & 0x3
            rm = (raw >> 3) & 0xF
            rd = (raw & 0x7) | ((raw >> 4) & 0x8)
            if h_op == 3:  # BX
                return DecodedThumbInstruction(raw, ThumbMnemonic.BX, rd=-1, rn=-1, rm=rm, imm=0)

        # Format 9: Load/store with immediate offset (0110xxxxxx)
        # STR: 01100, LDR: 01101, STRB: 01110, LDRB: 01111
        if (raw >> 12) == 0x6:
            l_bit = (raw >> 11) & 1
            imm5 = ((raw >> 6) & 0x1F) << 2
            rn = (raw >> 3) & 0x7
            rd = raw & 0x7
            mnem = ThumbMnemonic.LDR if l_bit else ThumbMnemonic.STR
            return DecodedThumbInstruction(raw, mnem, rd=rd, rn=rn, rm=-1, imm=imm5)

        if (raw >> 12) == 0x7:
            l_bit = (raw >> 11) & 1
            imm5 = (raw >> 6) & 0x1F
            rn = (raw >> 3) & 0x7
            rd = raw & 0x7
            mnem = ThumbMnemonic.LDRB if l_bit else ThumbMnemonic.STRB
            return DecodedThumbInstruction(raw, mnem, rd=rd, rn=rn, rm=-1, imm=imm5)

        # Format 16: Conditional branch (1101xxxx)
        if (raw >> 12) == 0xD:
            cond = (raw >> 8) & 0xF
            soffset8 = raw & 0xFF
            if soffset8 & 0x80:
                soffset8 -= 0x100
            offset = soffset8 << 1
            if cond == 0xE:
                return DecodedThumbInstruction(raw, ThumbMnemonic.UNKNOWN, rd=-1, rn=-1, rm=-1, imm=0)
            return DecodedThumbInstruction(raw, ThumbMnemonic.B_COND, rd=-1, rn=-1, rm=-1, imm=offset, cond=cond)

        # Format 17: Software breakpoint (10111110xxxxxxxx)
        if (raw >> 8) == 0xBE:
            imm8 = raw & 0xFF
            return DecodedThumbInstruction(raw, ThumbMnemonic.BKPT, rd=-1, rn=-1, rm=-1, imm=imm8)

        # Format 18: Unconditional branch (11100xxxxxxxxxxx)
        if (raw >> 11) == 0x1C:
            soffset11 = raw & 0x7FF
            if soffset11 & 0x400:
                soffset11 -= 0x800
            offset = soffset11 << 1
            return DecodedThumbInstruction(raw, ThumbMnemonic.B, rd=-1, rn=-1, rm=-1, imm=offset)

        return DecodedThumbInstruction(raw, ThumbMnemonic.UNKNOWN, rd=-1, rn=-1, rm=-1, imm=0)
