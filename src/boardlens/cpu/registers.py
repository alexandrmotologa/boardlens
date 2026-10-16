"""Processor register bank definitions for RISC-V RV32I and ARM Cortex-M."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union


class RegisterBank(ABC):
    """Abstract base class for processor register banks."""

    @abstractmethod
    def reset(self) -> None:
        """Reset all registers to initial reset state."""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize current register state to a dictionary for inspection."""
        pass


class RV32IRegisters(RegisterBank):
    """RISC-V RV32I general purpose register file and control/status registers (CSRs).

    Invariant:
        Register x0 is hardwired to constant zero.
        All registers are 32-bit unsigned integers [0, 0xFFFFFFFF].
    """

    ABI_NAMES: List[str] = [
        "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
        "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
        "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
        "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6",
    ]

    NAME_TO_INDEX: Dict[str, int] = {
        name: idx for idx, name in enumerate(ABI_NAMES)
    }
    # Add common aliases
    NAME_TO_INDEX["fp"] = 8  # Frame pointer alias for s0
    for i in range(32):
        NAME_TO_INDEX[f"x{i}"] = i

    # Common Machine-mode CSR Addresses
    CSR_MSTATUS = 0x300
    CSR_MISA = 0x301
    CSR_MIE = 0x304
    CSR_MTVEC = 0x305
    CSR_MSCRATCH = 0x340
    CSR_MEPC = 0x341
    CSR_MCAUSE = 0x342
    CSR_MTVAL = 0x343
    CSR_MIP = 0x344
    CSR_MCYCLE = 0xC00
    CSR_MCYCLEH = 0xC80
    CSR_MINSTRET = 0xC02
    CSR_MINSTRETH = 0xC82

    def __init__(self) -> None:
        self._regs: List[int] = [0] * 32
        self._csrs: Dict[int, int] = {}
        self.reset()

    def reset(self) -> None:
        """Reset all registers to zero and initialize default CSR values."""
        self._regs = [0] * 32
        self._csrs = {
            self.CSR_MSTATUS: 0x00000000,
            self.CSR_MISA: 0x40000100,     # RV32I base ISA (bit 30: 32-bit, bit 8: I extension)
            self.CSR_MIE: 0x00000000,
            self.CSR_MTVEC: 0x00000000,
            self.CSR_MSCRATCH: 0x00000000,
            self.CSR_MEPC: 0x00000000,
            self.CSR_MCAUSE: 0x00000000,
            self.CSR_MTVAL: 0x00000000,
            self.CSR_MIP: 0x00000000,
            self.CSR_MCYCLE: 0x00000000,
            self.CSR_MCYCLEH: 0x00000000,
            self.CSR_MINSTRET: 0x00000000,
            self.CSR_MINSTRETH: 0x00000000,
        }

    def _resolve_index(self, reg: Union[int, str]) -> int:
        """Resolve a register name or integer index to register index [0, 31]."""
        if isinstance(reg, int):
            if 0 <= reg < 32:
                return reg
            raise IndexError(f"Register index out of range: {reg}. Must be 0-31.")
        reg_clean = reg.strip().lower()
        if reg_clean in self.NAME_TO_INDEX:
            return self.NAME_TO_INDEX[reg_clean]
        raise KeyError(f"Unknown register name '{reg}'")

    def read(self, reg: Union[int, str]) -> int:
        """Read 32-bit unsigned value from register."""
        idx = self._resolve_index(reg)
        if idx == 0:
            return 0
        return self._regs[idx]

    def read_signed(self, reg: Union[int, str]) -> int:
        """Read sign-extended 32-bit integer (-2^31 to 2^31 - 1)."""
        val = self.read(reg)
        if val & 0x80000000:
            return val - 0x100000000
        return val

    def write(self, reg: Union[int, str], value: int) -> None:
        """Write 32-bit value to register. Writes to x0 are silently discarded."""
        idx = self._resolve_index(reg)
        if idx == 0:
            return
        self._regs[idx] = value & 0xFFFFFFFF

    def read_csr(self, address: int) -> int:
        """Read 32-bit CSR value."""
        return self._csrs.get(address & 0xFFF, 0) & 0xFFFFFFFF

    def write_csr(self, address: int, value: int) -> None:
        """Write 32-bit CSR value."""
        addr = address & 0xFFF
        self._csrs[addr] = value & 0xFFFFFFFF

    def increment_cycle_counters(self, cycles: int = 1, instructions: int = 1) -> None:
        """Advance mcycle and minstret 64-bit performance counters."""
        current_cycle = (self.read_csr(self.CSR_MCYCLEH) << 32) | self.read_csr(self.CSR_MCYCLE)
        new_cycle = (current_cycle + cycles) & 0xFFFFFFFFFFFFFFFF
        self.write_csr(self.CSR_MCYCLE, new_cycle & 0xFFFFFFFF)
        self.write_csr(self.CSR_MCYCLEH, (new_cycle >> 32) & 0xFFFFFFFF)

        current_inst = (self.read_csr(self.CSR_MINSTRETH) << 32) | self.read_csr(self.CSR_MINSTRET)
        new_inst = (current_inst + instructions) & 0xFFFFFFFFFFFFFFFF
        self.write_csr(self.CSR_MINSTRET, new_inst & 0xFFFFFFFF)
        self.write_csr(self.CSR_MINSTRETH, (new_inst >> 32) & 0xFFFFFFFF)

    def to_dict(self) -> Dict[str, Any]:
        """Return human-readable register mapping."""
        gpr: Dict[str, Dict[str, Any]] = {}
        for idx in range(32):
            val = self._regs[idx]
            abi = self.ABI_NAMES[idx]
            gpr[f"x{idx}"] = {
                "abi": abi,
                "value": val,
                "hex": f"0x{val:08X}",
                "signed": val if val < 0x80000000 else val - 0x100000000,
            }
        return {
            "gpr": gpr,
            "csrs": {f"0x{k:03X}": f"0x{v:08X}" for k, v in sorted(self._csrs.items())},
        }

    def __getitem__(self, item: Union[int, str]) -> int:
        return self.read(item)

    def __setitem__(self, item: Union[int, str], value: int) -> None:
        self.write(item, value)


class ARMRegisters(RegisterBank):
    """ARM Cortex-M register file containing R0-R15 and xPSR flags.

    Registers:
        R0-R12: General purpose
        R13: Stack Pointer (SP / MSP / PSP)
        R14: Link Register (LR)
        R15: Program Counter (PC)
    xPSR Flags:
        N: Negative
        Z: Zero
        C: Carry
        V: Overflow
        T: Thumb state bit (always 1 for Cortex-M)
    """

    def __init__(self) -> None:
        self._regs: List[int] = [0] * 16
        self.n: bool = False
        self.z: bool = True
        self.c: bool = False
        self.v: bool = False
        self.t: bool = True  # Thumb mode
        self.reset()

    def reset(self) -> None:
        """Reset ARM registers and flags."""
        self._regs = [0] * 16
        self.n = False
        self.z = True
        self.c = False
        self.v = False
        self.t = True

    def read(self, reg: int) -> int:
        """Read 32-bit unsigned register R0-R15."""
        if 0 <= reg < 16:
            return self._regs[reg]
        raise IndexError(f"ARM register index out of range: {reg}. Must be 0-15.")

    def read_signed(self, reg: int) -> int:
        """Read sign-extended 32-bit integer."""
        val = self.read(reg)
        if val & 0x80000000:
            return val - 0x100000000
        return val

    def write(self, reg: int, value: int) -> None:
        """Write 32-bit value to register R0-R15."""
        if 0 <= reg < 16:
            self._regs[reg] = value & 0xFFFFFFFF
        else:
            raise IndexError(f"ARM register index out of range: {reg}. Must be 0-15.")

    @property
    def sp(self) -> int:
        return self._regs[13]

    @sp.setter
    def sp(self, value: int) -> None:
        self.write(13, value)

    @property
    def lr(self) -> int:
        return self._regs[14]

    @lr.setter
    def lr(self, value: int) -> None:
        self.write(14, value)

    @property
    def pc(self) -> int:
        return self._regs[15]

    @pc.setter
    def pc(self, value: int) -> None:
        self.write(15, value)

    @property
    def xpsr(self) -> int:
        """Encode xPSR register from individual flag booleans."""
        val = 0
        if self.n: val |= (1 << 31)
        if self.z: val |= (1 << 30)
        if self.c: val |= (1 << 29)
        if self.v: val |= (1 << 28)
        if self.t: val |= (1 << 24)
        return val

    @xpsr.setter
    def xpsr(self, value: int) -> None:
        """Decode xPSR register bits into flags."""
        self.n = bool(value & (1 << 31))
        self.z = bool(value & (1 << 30))
        self.c = bool(value & (1 << 29))
        self.v = bool(value & (1 << 28))
        self.t = bool(value & (1 << 24))

    def update_flags_nz(self, result: int) -> None:
        """Update N and Z flags based on 32-bit arithmetic result."""
        res_32 = result & 0xFFFFFFFF
        self.z = (res_32 == 0)
        self.n = bool(res_32 & 0x80000000)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ARM register state."""
        regs_dict: Dict[str, Any] = {}
        for i in range(13):
            val = self._regs[i]
            regs_dict[f"r{i}"] = {"value": val, "hex": f"0x{val:08X}"}
        regs_dict["sp"] = {"value": self.sp, "hex": f"0x{self.sp:08X}"}
        regs_dict["lr"] = {"value": self.lr, "hex": f"0x{self.lr:08X}"}
        regs_dict["pc"] = {"value": self.pc, "hex": f"0x{self.pc:08X}"}
        return {
            "registers": regs_dict,
            "flags": {
                "N": self.n,
                "Z": self.z,
                "C": self.c,
                "V": self.v,
                "T": self.t,
            },
            "xpsr": f"0x{self.xpsr:08X}",
        }
