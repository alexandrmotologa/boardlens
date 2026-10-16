"""Authentic ELF32 binary and symbol table parser for RISC-V and ARM firmware."""

import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from boardlens.memory.bus import MemoryBus


class ELFError(Exception):
    """Raised when an ELF binary is invalid or corrupt."""
    pass


@dataclass(frozen=True)
class ELFSegment:
    """Represents a PT_LOAD segment from the ELF Program Header table."""
    p_type: int
    offset: int
    vaddr: int
    paddr: int
    filesz: int
    memsz: int
    flags: int
    data: bytes


@dataclass(frozen=True)
class ELFSymbol:
    """Represents a function or variable symbol from .symtab."""
    name: str
    value: int
    size: int
    sym_type: int  # 0=NOTYPE, 1=OBJECT, 2=FUNC, 3=SECTION, 4=FILE

    @property
    def is_function(self) -> bool:
        return self.sym_type == 2


class ELF32:
    """Parser for 32-bit ELF binaries supporting RISC-V and ARM architectures."""

    EM_ARM = 0x28      # 40
    EM_RISCV = 0xF3    # 243

    PT_LOAD = 1

    def __init__(self, raw_bytes: bytes) -> None:
        self.raw = raw_bytes
        if len(self.raw) < 52:
            raise ELFError("File too small to be a valid ELF32 binary (< 52 bytes)")

        # Verify magic: 0x7F 'E' 'L' 'F'
        if self.raw[:4] != b"\x7fELF":
            raise ELFError("Invalid ELF magic header")

        # Class (1 = 32-bit, 2 = 64-bit)
        self.ei_class = self.raw[4]
        if self.ei_class != 1:
            raise ELFError(f"Unsupported ELF class {self.ei_class}. Only 32-bit ELF32 is supported.")

        # Endianness (1 = Little-endian, 2 = Big-endian)
        self.ei_data = self.raw[5]
        if self.ei_data != 1:
            raise ELFError("Unsupported endianness. Only little-endian ELF is supported.")

        # Parse ELF Header (52 bytes)
        # Format: < (little-endian), 16s (e_ident), H (type), H (machine), I (version), I (entry),
        # I (phoff), I (shoff), I (flags), H (ehsize), H (phentsize), H (phnum), H (shentsize), H (shnum), H (shstrndx)
        (
            ident,
            self.e_type,
            self.e_machine,
            self.e_version,
            self.e_entry,
            self.e_phoff,
            self.e_shoff,
            self.e_flags,
            self.e_ehsize,
            self.e_phentsize,
            self.e_phnum,
            self.e_shentsize,
            self.e_shnum,
            self.e_shstrndx,
        ) = struct.unpack("<16sHHIIIIIHHHHHH", self.raw[:52])

        self.segments: List[ELFSegment] = []
        self.symbols: Dict[int, ELFSymbol] = {}
        self.symbol_names: Dict[str, int] = {}

        self._parse_program_headers()
        self._parse_sections_and_symbols()

    @property
    def architecture(self) -> str:
        if self.e_machine == self.EM_RISCV:
            return "rv32i"
        elif self.e_machine == self.EM_ARM:
            return "arm"
        return f"unknown (0x{self.e_machine:X})"

    def _parse_program_headers(self) -> None:
        """Parse program header table and extract PT_LOAD segments."""
        if self.e_phoff == 0 or self.e_phnum == 0:
            return

        for i in range(self.e_phnum):
            offset = self.e_phoff + (i * self.e_phentsize)
            if offset + 32 > len(self.raw):
                break
            (
                p_type,
                p_offset,
                p_vaddr,
                p_paddr,
                p_filesz,
                p_memsz,
                p_flags,
                p_align,
            ) = struct.unpack("<IIIIIIII", self.raw[offset : offset + 32])

            segment_data = self.raw[p_offset : p_offset + p_filesz]
            self.segments.append(
                ELFSegment(
                    p_type=p_type,
                    offset=p_offset,
                    vaddr=p_vaddr,
                    paddr=p_paddr,
                    filesz=p_filesz,
                    memsz=p_memsz,
                    flags=p_flags,
                    data=segment_data,
                )
            )

    def _parse_sections_and_symbols(self) -> None:
        """Parse section headers to locate .symtab and .strtab."""
        if self.e_shoff == 0 or self.e_shnum == 0:
            return

        sections = []
        for i in range(self.e_shnum):
            sh_off = self.e_shoff + (i * self.e_shentsize)
            if sh_off + 40 > len(self.raw):
                break
            (
                sh_name,
                sh_type,
                sh_flags,
                sh_addr,
                sh_offset,
                sh_size,
                sh_link,
                sh_info,
                sh_addralign,
                sh_entsize,
            ) = struct.unpack("<IIIIIIIIII", self.raw[sh_off : sh_off + 40])
            sections.append({
                "name_idx": sh_name,
                "type": sh_type,
                "flags": sh_flags,
                "addr": sh_addr,
                "offset": sh_offset,
                "size": sh_size,
                "link": sh_link,
                "info": sh_info,
                "entsize": sh_entsize,
            })

        # Locate string table (.shstrtab) to get section names
        shstrtab = b""
        if 0 <= self.e_shstrndx < len(sections):
            shstr_meta = sections[self.e_shstrndx]
            shstrtab = self.raw[shstr_meta["offset"] : shstr_meta["offset"] + shstr_meta["size"]]

        def get_sh_name(idx: int) -> str:
            if idx >= len(shstrtab):
                return ""
            end = shstrtab.find(b"\x00", idx)
            return shstrtab[idx:end].decode("utf-8", errors="replace") if end != -1 else ""

        # Find .symtab and associated .strtab
        for sec in sections:
            sec["name"] = get_sh_name(sec["name_idx"])

        symtab_sec = next((s for s in sections if s["type"] == 2 or s["name"] == ".symtab"), None)
        if not symtab_sec:
            return

        strtab_sec_idx = symtab_sec["link"]
        if not (0 <= strtab_sec_idx < len(sections)):
            return
        strtab_data = self.raw[sections[strtab_sec_idx]["offset"] : sections[strtab_sec_idx]["offset"] + sections[strtab_sec_idx]["size"]]

        def get_sym_name(idx: int) -> str:
            if idx >= len(strtab_data):
                return ""
            end = strtab_data.find(b"\x00", idx)
            return strtab_data[idx:end].decode("utf-8", errors="replace") if end != -1 else ""

        # Parse 16-byte symbols in .symtab
        sym_data = self.raw[symtab_sec["offset"] : symtab_sec["offset"] + symtab_sec["size"]]
        ent_size = symtab_sec["entsize"] if symtab_sec["entsize"] > 0 else 16

        for off in range(0, len(sym_data) - ent_size + 1, ent_size):
            st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack("<IIIBBH", sym_data[off : off + 16])
            name = get_sym_name(st_name)
            sym_type = st_info & 0x0F
            if name:
                sym_obj = ELFSymbol(name=name, value=st_value, size=st_size, sym_type=sym_type)
                self.symbols[st_value] = sym_obj
                self.symbol_names[name] = st_value

    def load_into_bus(self, bus: MemoryBus) -> int:
        """Write all PT_LOAD segments into the MemoryBus. Returns entry point address."""
        for seg in self.segments:
            if seg.p_type != self.PT_LOAD:
                continue

            target_addr = seg.paddr if seg.paddr != 0 else seg.vaddr
            # Write file payload bytes
            for i, b in enumerate(seg.data):
                bus.write8(target_addr + i, b)

            # Zero-initialize BSS remainder if memsz > filesz
            if seg.memsz > seg.filesz:
                for j in range(seg.filesz, seg.memsz):
                    bus.write8(target_addr + j, 0)

        return self.e_entry


def create_minimal_elf32(
    code: bytes,
    entry_addr: int = 0x00000000,
    machine: int = ELF32.EM_RISCV,
    symbols: Optional[Dict[str, int]] = None,
) -> bytes:
    """Helper to synthesize a compliant ELF32 executable binary for tests and serialization."""
    # Header sizes
    ehdr_size = 52
    phdr_size = 32

    # String table for section names: "\0.text\0.shstrtab\0.symtab\0.strtab\0"
    shstrtab = b"\x00.text\x00.shstrtab\x00.symtab\x00.strtab\x00"
    text_name_idx = 1
    shstrtab_name_idx = 7
    symtab_name_idx = 17
    strtab_name_idx = 25

    # Symbol strings table: "\0" + symbols concatenated
    strtab = b"\x00"
    sym_records = []
    if symbols:
        for sname, saddr in symbols.items():
            s_idx = len(strtab)
            strtab += sname.encode("utf-8") + b"\x00"
            sym_records.append((s_idx, saddr, 4, 0x12, 0, 1))  # STT_FUNC, STB_GLOBAL

    # Construct symtab bytes: first symbol is dummy null
    symtab = struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0)
    for s_idx, saddr, size, info, other, shndx in sym_records:
        symtab += struct.pack("<IIIBBH", s_idx, saddr, size, info, other, shndx)

    # Offsets layout
    ph_offset = ehdr_size
    text_offset = ehdr_size + phdr_size
    text_size = len(code)
    shstrtab_offset = text_offset + text_size
    symtab_offset = shstrtab_offset + len(shstrtab)
    strtab_offset = symtab_offset + len(symtab)
    sh_offset = strtab_offset + len(strtab)

    # 4 Sections: NULL (0), .text (1), .shstrtab (2), .symtab (3), .strtab (4)
    shnum = 5
    shdr_size = 40

    # Build ELF header
    # e_ident: 16 bytes
    e_ident = b"\x7fELF\x01\x01\x01\x00" + (b"\x00" * 8)
    ehdr = struct.pack(
        "<16sHHIIIIIHHHHHH",
        e_ident,
        2,              # e_type: ET_EXEC
        machine,        # e_machine
        1,              # e_version
        entry_addr,     # e_entry
        ph_offset,      # e_phoff
        sh_offset,      # e_shoff
        0,              # e_flags
        ehdr_size,      # e_ehsize
        phdr_size,      # e_phentsize
        1,              # e_phnum
        shdr_size,      # e_shentsize
        shnum,          # e_shnum
        2,              # e_shstrndx (.shstrtab is index 2)
    )

    # Program header (PT_LOAD covering .text)
    phdr = struct.pack(
        "<IIIIIIII",
        1,              # p_type: PT_LOAD
        text_offset,    # p_offset
        entry_addr,     # p_vaddr
        entry_addr,     # p_paddr
        text_size,      # p_filesz
        text_size,      # p_memsz
        0x5,            # p_flags: PF_R | PF_X
        4,              # p_align
    )

    # Section headers
    sh_null = struct.pack("<IIIIIIIIII", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    sh_text = struct.pack("<IIIIIIIIII", text_name_idx, 1, 0x6, entry_addr, text_offset, text_size, 0, 0, 4, 0)
    sh_shstrtab = struct.pack("<IIIIIIIIII", shstrtab_name_idx, 3, 0, 0, shstrtab_offset, len(shstrtab), 0, 0, 1, 0)
    sh_symtab = struct.pack("<IIIIIIIIII", symtab_name_idx, 2, 0, 0, symtab_offset, len(symtab), 4, 1, 4, 16)
    sh_strtab = struct.pack("<IIIIIIIIII", strtab_name_idx, 3, 0, 0, strtab_offset, len(strtab), 0, 0, 1, 0)

    return (
        ehdr
        + phdr
        + code
        + shstrtab
        + symtab
        + strtab
        + sh_null
        + sh_text
        + sh_shstrtab
        + sh_symtab
        + sh_strtab
    )
