"""RV32I disassembler producing clean instruction listings."""

from typing import List, Tuple
from boardlens.cpu.rv32i.decoder import RV32IDecoder


def disassemble_instruction(raw: int, pc: int = 0) -> str:
    """Decode and format a single 32-bit machine word into assembly text."""
    inst = RV32IDecoder.decode(raw)
    return str(inst)


def disassemble_bytes(code: bytes, base_address: int = 0x00000000) -> List[Tuple[int, int, str]]:
    """Disassemble raw byte stream into (address, raw_word, mnemonic) records."""
    records: List[Tuple[int, int, str]] = []
    length = len(code)
    for offset in range(0, length - 3, 4):
        raw_word = int.from_bytes(code[offset : offset + 4], byteorder="little")
        addr = (base_address + offset) & 0xFFFFFFFF
        text = disassemble_instruction(raw_word, pc=addr)
        records.append((addr, raw_word, text))
    return records


def format_disassembly(code: bytes, base_address: int = 0x00000000) -> str:
    """Generate aligned disassembly listing table."""
    records = disassemble_bytes(code, base_address=base_address)
    lines: List[str] = []
    for addr, raw, text in records:
        lines.append(f"{addr:08X}: {raw:08X}    {text}")
    return "\n".join(lines)
