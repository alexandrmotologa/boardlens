"""Base interfaces and exceptions for CPU cores."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional



class TrapCause(Enum):
    """Trap and exception causes."""
    INSTRUCTION_ADDRESS_MISALIGNED = 0
    INSTRUCTION_ACCESS_FAULT = 1
    ILLEGAL_INSTRUCTION = 2
    BREAKPOINT = 3
    LOAD_ADDRESS_MISALIGNED = 4
    LOAD_ACCESS_FAULT = 5
    STORE_ADDRESS_MISALIGNED = 6
    STORE_ACCESS_FAULT = 7
    ENVIRONMENT_CALL = 8
    HARDWARE_INTERRUPT = 16


class CpuTrap(Exception):
    """Exception raised when a CPU core encounters an unhandled trap or breakpoint."""

    def __init__(self, cause: TrapCause, pc: int, value: int = 0, message: Optional[str] = None):
        self.cause = cause
        self.pc = pc
        self.value = value
        self.message = message or f"CPU Trap {cause.name} at PC=0x{pc:08X} (val=0x{value:08X})"
        super().__init__(self.message)


@dataclass
class StepResult:
    """Result of executing a single CPU instruction step."""
    pc: int
    next_pc: int
    instruction_raw: int
    mnemonic: str
    cycles: int
    trap: Optional[TrapCause] = None


class CPUCore(ABC):
    """Abstract base class for simulated CPU cores."""

    @abstractmethod
    def reset(self, initial_pc: int = 0x00000000) -> None:
        """Reset the CPU core registers and program counter to initial state."""
        pass

    @abstractmethod
    def step(self) -> StepResult:
        """Execute one instruction and advance the program counter."""
        pass

    @property
    @abstractmethod
    def pc(self) -> int:
        """Current program counter."""
        pass

    @pc.setter
    @abstractmethod
    def pc(self, value: int) -> None:
        pass

    @property
    @abstractmethod
    def cycles(self) -> int:
        """Cumulative executed clock cycles."""
        pass

    @property
    def regs(self) -> Any:
        """Convenience alias for cpu.registers."""
        return getattr(self, "registers", None)

