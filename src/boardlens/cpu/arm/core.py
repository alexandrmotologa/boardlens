"""ARM Cortex-M Thumb execution core simulation."""

from typing import Optional, Set
from boardlens.cpu.base import CPUCore, CpuTrap, StepResult, TrapCause
from boardlens.cpu.arm.decoder import DecodedThumbInstruction, ThumbDecoder, ThumbMnemonic
from boardlens.cpu.registers import ARMRegisters
from boardlens.memory.bus import BusFault, MemoryBus


class ARMCortexMCore(CPUCore):
    """ARM Cortex-M processor core simulating Thumb-1 instructions."""

    def __init__(self, bus: MemoryBus, initial_pc: int = 0x00000000) -> None:
        self.bus = bus
        self.registers = ARMRegisters()
        self.registers.pc = initial_pc & 0xFFFFFFFF
        self._cycles: int = 0
        self._instructions_executed: int = 0
        self.breakpoints: Set[int] = set()
        self.halted: bool = False

    @property
    def pc(self) -> int:
        return self.registers.pc

    @pc.setter
    def pc(self, value: int) -> None:
        self.registers.pc = value & 0xFFFFFFFF

    @property
    def cycles(self) -> int:
        return self._cycles

    @property
    def instructions_executed(self) -> int:
        return self._instructions_executed

    def reset(self, initial_pc: int = 0x00000000) -> None:
        self.registers.reset()
        self.registers.pc = initial_pc & 0xFFFFFFFF
        self._cycles = 0
        self._instructions_executed = 0
        self.halted = False

    def add_breakpoint(self, address: int) -> None:
        self.breakpoints.add(address & 0xFFFFFFFF)

    def remove_breakpoint(self, address: int) -> None:
        self.breakpoints.discard(address & 0xFFFFFFFF)

    def _eval_cond(self, cond: int) -> bool:
        """Evaluate ARM condition code against xPSR flags."""
        r = self.registers
        if cond == 0:   return r.z                    # EQ
        if cond == 1:   return not r.z                # NE
        if cond == 2:   return r.c                    # CS / HS
        if cond == 3:   return not r.c                # CC / LO
        if cond == 4:   return r.n                    # MI
        if cond == 5:   return not r.n                # PL
        if cond == 6:   return r.v                    # VS
        if cond == 7:   return not r.v                # VC
        if cond == 8:   return r.c and not r.z        # HI
        if cond == 9:   return not r.c or r.z         # LS
        if cond == 10:  return r.n == r.v             # GE
        if cond == 11:  return r.n != r.v             # LT
        if cond == 12:  return not r.z and (r.n == r.v) # GT
        if cond == 13:  return r.z or (r.n != r.v)     # LE
        if cond == 14:  return True                   # AL
        return False

    def step(self) -> StepResult:
        """Execute one 16-bit Thumb instruction."""
        if self.halted:
            return StepResult(self.pc, self.pc, 0, "HALTED", 0, TrapCause.BREAKPOINT)

        current_pc = self.registers.pc

        if current_pc in self.breakpoints:
            return StepResult(current_pc, current_pc, 0, "BREAKPOINT", 0, TrapCause.BREAKPOINT)

        if current_pc & 1 != 0:
            raise CpuTrap(cause=TrapCause.INSTRUCTION_ADDRESS_MISALIGNED, pc=current_pc, value=current_pc)

        try:
            raw_inst = self.bus.read16(current_pc)
        except BusFault as exc:
            raise CpuTrap(cause=TrapCause.INSTRUCTION_ACCESS_FAULT, pc=current_pc, value=exc.address)

        inst = ThumbDecoder.decode(raw_inst)
        # ARM pipeline semantics: PC is fetched at PC+4 in Thumb mode
        next_pc = (current_pc + 2) & 0xFFFFFFFF
        step_cycles = 1
        trap: Optional[TrapCause] = None

        m = inst.mnemonic

        if m == ThumbMnemonic.MOVS:
            self.registers.write(inst.rd, inst.imm)
            self.registers.update_flags_nz(inst.imm)

        elif m == ThumbMnemonic.ADDS:
            op1 = self.registers.read(inst.rn)
            op2 = self.registers.read(inst.rm) if inst.rm != -1 else inst.imm
            res = op1 + op2
            self.registers.write(inst.rd, res & 0xFFFFFFFF)
            self.registers.update_flags_nz(res)
            self.registers.c = res > 0xFFFFFFFF
            # Overflow
            s_op1 = self.registers.read_signed(inst.rn)
            s_op2 = self.registers.read_signed(inst.rm) if inst.rm != -1 else inst.imm
            s_res = s_op1 + s_op2
            self.registers.v = not (-0x80000000 <= s_res <= 0x7FFFFFFF)

        elif m == ThumbMnemonic.SUBS or m == ThumbMnemonic.CMP:
            op1 = self.registers.read(inst.rn)
            op2 = self.registers.read(inst.rm) if inst.rm != -1 else inst.imm
            res = op1 - op2
            if m == ThumbMnemonic.SUBS:
                self.registers.write(inst.rd, res & 0xFFFFFFFF)
            self.registers.update_flags_nz(res)
            self.registers.c = op1 >= op2  # In ARM, C=1 if no borrow
            s_op1 = self.registers.read_signed(inst.rn)
            s_op2 = self.registers.read_signed(inst.rm) if inst.rm != -1 else inst.imm
            s_res = s_op1 - s_op2
            self.registers.v = not (-0x80000000 <= s_res <= 0x7FFFFFFF)

        elif m == ThumbMnemonic.ANDS:
            res = self.registers.read(inst.rd) & self.registers.read(inst.rm)
            self.registers.write(inst.rd, res)
            self.registers.update_flags_nz(res)

        elif m == ThumbMnemonic.EORS:
            res = self.registers.read(inst.rd) ^ self.registers.read(inst.rm)
            self.registers.write(inst.rd, res)
            self.registers.update_flags_nz(res)

        elif m == ThumbMnemonic.ORRS:
            res = self.registers.read(inst.rd) | self.registers.read(inst.rm)
            self.registers.write(inst.rd, res)
            self.registers.update_flags_nz(res)

        elif m == ThumbMnemonic.LSLS:
            val = self.registers.read(inst.rn)
            shamt = inst.imm
            if shamt > 0:
                self.registers.c = bool((val >> (32 - shamt)) & 1)
                res = (val << shamt) & 0xFFFFFFFF
            else:
                res = val
            self.registers.write(inst.rd, res)
            self.registers.update_flags_nz(res)

        elif m == ThumbMnemonic.LSRS:
            val = self.registers.read(inst.rn)
            shamt = inst.imm
            if shamt > 0:
                self.registers.c = bool((val >> (shamt - 1)) & 1)
                res = (val >> shamt) & 0xFFFFFFFF
            else:
                res = val
            self.registers.write(inst.rd, res)
            self.registers.update_flags_nz(res)

        elif m == ThumbMnemonic.LDR:
            addr = (self.registers.read(inst.rn) + inst.imm) & 0xFFFFFFFF
            val = self.bus.read32(addr)
            self.registers.write(inst.rd, val)
            step_cycles = 2

        elif m == ThumbMnemonic.STR:
            addr = (self.registers.read(inst.rn) + inst.imm) & 0xFFFFFFFF
            self.bus.write32(addr, self.registers.read(inst.rd))
            step_cycles = 2

        elif m == ThumbMnemonic.LDRB:
            addr = (self.registers.read(inst.rn) + inst.imm) & 0xFFFFFFFF
            val = self.bus.read8(addr)
            self.registers.write(inst.rd, val)
            step_cycles = 2

        elif m == ThumbMnemonic.STRB:
            addr = (self.registers.read(inst.rn) + inst.imm) & 0xFFFFFFFF
            self.bus.write8(addr, self.registers.read(inst.rd) & 0xFF)
            step_cycles = 2

        elif m == ThumbMnemonic.B:
            # PC is current_pc + 4 in architectural branch calculation
            next_pc = (current_pc + 4 + inst.imm) & 0xFFFFFFFF
            step_cycles = 2

        elif m == ThumbMnemonic.B_COND:
            if inst.cond is not None and self._eval_cond(inst.cond):
                next_pc = (current_pc + 4 + inst.imm) & 0xFFFFFFFF
                step_cycles = 2

        elif m == ThumbMnemonic.BX:
            target = self.registers.read(inst.rm)
            self.registers.t = bool(target & 1)
            next_pc = target & ~1
            step_cycles = 2

        elif m == ThumbMnemonic.BKPT:
            trap = TrapCause.BREAKPOINT
            self.halted = True

        else:
            raise CpuTrap(cause=TrapCause.ILLEGAL_INSTRUCTION, pc=current_pc, value=raw_inst)

        self.registers.pc = next_pc
        self._cycles += step_cycles
        self._instructions_executed += 1
        self.bus.cycle_count = self._cycles

        return StepResult(
            pc=current_pc,
            next_pc=next_pc,
            instruction_raw=raw_inst,
            mnemonic=str(inst),
            cycles=step_cycles,
            trap=trap,
        )
