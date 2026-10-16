"""RISC-V RV32I Processor execution core."""

from typing import Optional, Set
from boardlens.cpu.base import CPUCore, CpuTrap, StepResult, TrapCause
from boardlens.cpu.registers import RV32IRegisters
from boardlens.cpu.rv32i.decoder import RV32IDecoder, _sign_extend
from boardlens.cpu.rv32i.instructions import DecodedInstruction, Mnemonic
from boardlens.memory.bus import BusFault, MemoryBus


class RV32ICore(CPUCore):
    """Cycle-accurate RISC-V RV32I processor simulation core."""

    def __init__(self, bus: MemoryBus, initial_pc: int = 0x00000000) -> None:
        self.bus = bus
        self.registers = RV32IRegisters()
        self._pc: int = initial_pc & 0xFFFFFFFF
        self._cycles: int = 0
        self._instructions_executed: int = 0
        self.breakpoints: Set[int] = set()
        self.halted: bool = False

    @property
    def pc(self) -> int:
        return self._pc

    @pc.setter
    def pc(self, value: int) -> None:
        self._pc = value & 0xFFFFFFFF

    @property
    def cycles(self) -> int:
        return self._cycles

    @property
    def instructions_executed(self) -> int:
        return self._instructions_executed

    def reset(self, initial_pc: int = 0x00000000) -> None:
        self.registers.reset()
        self._pc = initial_pc & 0xFFFFFFFF
        self._cycles = 0
        self._instructions_executed = 0
        self.halted = False

    def add_breakpoint(self, address: int) -> None:
        self.breakpoints.add(address & 0xFFFFFFFF)

    def remove_breakpoint(self, address: int) -> None:
        self.breakpoints.discard(address & 0xFFFFFFFF)

    def step(self) -> StepResult:
        """Fetch, decode, and execute a single instruction."""
        if self.halted:
            return StepResult(
                pc=self._pc,
                next_pc=self._pc,
                instruction_raw=0,
                mnemonic="HALTED",
                cycles=0,
                trap=TrapCause.BREAKPOINT,
            )

        current_pc = self._pc

        # Check breakpoint
        if current_pc in self.breakpoints:
            return StepResult(
                pc=current_pc,
                next_pc=current_pc,
                instruction_raw=0,
                mnemonic="BREAKPOINT",
                cycles=0,
                trap=TrapCause.BREAKPOINT,
            )

        # Check instruction alignment
        if current_pc & 3 != 0:
            raise CpuTrap(
                cause=TrapCause.INSTRUCTION_ADDRESS_MISALIGNED,
                pc=current_pc,
                value=current_pc,
            )

        # Fetch instruction
        try:
            raw_inst = self.bus.read32(current_pc)
        except BusFault as exc:
            raise CpuTrap(
                cause=TrapCause.INSTRUCTION_ACCESS_FAULT,
                pc=current_pc,
                value=exc.address,
                message=f"Instruction fetch access fault at 0x{current_pc:08X}",
            )

        # Decode
        inst = RV32IDecoder.decode(raw_inst)
        next_pc = (current_pc + 4) & 0xFFFFFFFF
        step_cycles = 1
        trap: Optional[TrapCause] = None

        # Execute
        mnem = inst.mnemonic
        rd = inst.rd
        rs1 = inst.rs1
        rs2 = inst.rs2
        imm = inst.imm

        # U-Type
        if mnem == Mnemonic.LUI:
            self.registers.write(rd, imm)

        elif mnem == Mnemonic.AUIPC:
            self.registers.write(rd, (current_pc + imm) & 0xFFFFFFFF)

        # J-Type
        elif mnem == Mnemonic.JAL:
            self.registers.write(rd, (current_pc + 4) & 0xFFFFFFFF)
            next_pc = (current_pc + imm) & 0xFFFFFFFF
            step_cycles = 2

        # I-Type JALR
        elif mnem == Mnemonic.JALR:
            target = (self.registers.read(rs1) + imm) & ~1
            self.registers.write(rd, (current_pc + 4) & 0xFFFFFFFF)
            next_pc = target & 0xFFFFFFFF
            step_cycles = 2

        # B-Type Branches
        elif mnem == Mnemonic.BEQ:
            if self.registers.read(rs1) == self.registers.read(rs2):
                next_pc = (current_pc + imm) & 0xFFFFFFFF
                step_cycles = 2

        elif mnem == Mnemonic.BNE:
            if self.registers.read(rs1) != self.registers.read(rs2):
                next_pc = (current_pc + imm) & 0xFFFFFFFF
                step_cycles = 2

        elif mnem == Mnemonic.BLT:
            if self.registers.read_signed(rs1) < self.registers.read_signed(rs2):
                next_pc = (current_pc + imm) & 0xFFFFFFFF
                step_cycles = 2

        elif mnem == Mnemonic.BGE:
            if self.registers.read_signed(rs1) >= self.registers.read_signed(rs2):
                next_pc = (current_pc + imm) & 0xFFFFFFFF
                step_cycles = 2

        elif mnem == Mnemonic.BLTU:
            if self.registers.read(rs1) < self.registers.read(rs2):
                next_pc = (current_pc + imm) & 0xFFFFFFFF
                step_cycles = 2

        elif mnem == Mnemonic.BGEU:
            if self.registers.read(rs1) >= self.registers.read(rs2):
                next_pc = (current_pc + imm) & 0xFFFFFFFF
                step_cycles = 2

        # Loads
        elif mnem in (Mnemonic.LB, Mnemonic.LH, Mnemonic.LW, Mnemonic.LBU, Mnemonic.LHU):
            addr = (self.registers.read(rs1) + imm) & 0xFFFFFFFF
            step_cycles = 2
            try:
                if mnem == Mnemonic.LB:
                    b = self.bus.read8(addr)
                    self.registers.write(rd, _sign_extend(b, 8))
                elif mnem == Mnemonic.LH:
                    h = self.bus.read16(addr)
                    self.registers.write(rd, _sign_extend(h, 16))
                elif mnem == Mnemonic.LW:
                    w = self.bus.read32(addr)
                    self.registers.write(rd, w)
                elif mnem == Mnemonic.LBU:
                    b = self.bus.read8(addr)
                    self.registers.write(rd, b)
                elif mnem == Mnemonic.LHU:
                    h = self.bus.read16(addr)
                    self.registers.write(rd, h)
            except BusFault as exc:
                raise CpuTrap(cause=TrapCause.LOAD_ACCESS_FAULT, pc=current_pc, value=exc.address)

        # Stores
        elif mnem in (Mnemonic.SB, Mnemonic.SH, Mnemonic.SW):
            addr = (self.registers.read(rs1) + imm) & 0xFFFFFFFF
            step_cycles = 2
            try:
                val = self.registers.read(rs2)
                if mnem == Mnemonic.SB:
                    self.bus.write8(addr, val & 0xFF)
                elif mnem == Mnemonic.SH:
                    self.bus.write16(addr, val & 0xFFFF)
                elif mnem == Mnemonic.SW:
                    self.bus.write32(addr, val)
            except BusFault as exc:
                raise CpuTrap(cause=TrapCause.STORE_ACCESS_FAULT, pc=current_pc, value=exc.address)

        # I-Type ALU
        elif mnem == Mnemonic.ADDI:
            self.registers.write(rd, (self.registers.read(rs1) + imm) & 0xFFFFFFFF)

        elif mnem == Mnemonic.SLTI:
            self.registers.write(rd, 1 if self.registers.read_signed(rs1) < imm else 0)

        elif mnem == Mnemonic.SLTIU:
            self.registers.write(rd, 1 if self.registers.read(rs1) < (imm & 0xFFFFFFFF) else 0)

        elif mnem == Mnemonic.XORI:
            self.registers.write(rd, (self.registers.read(rs1) ^ imm) & 0xFFFFFFFF)

        elif mnem == Mnemonic.ORI:
            self.registers.write(rd, (self.registers.read(rs1) | (imm & 0xFFFFFFFF)) & 0xFFFFFFFF)

        elif mnem == Mnemonic.ANDI:
            self.registers.write(rd, (self.registers.read(rs1) & (imm & 0xFFFFFFFF)) & 0xFFFFFFFF)

        elif mnem == Mnemonic.SLLI:
            shamt = imm & 0x1F
            self.registers.write(rd, (self.registers.read(rs1) << shamt) & 0xFFFFFFFF)

        elif mnem == Mnemonic.SRLI:
            shamt = imm & 0x1F
            self.registers.write(rd, (self.registers.read(rs1) >> shamt) & 0xFFFFFFFF)

        elif mnem == Mnemonic.SRAI:
            shamt = imm & 0x1F
            signed_val = self.registers.read_signed(rs1)
            self.registers.write(rd, (signed_val >> shamt) & 0xFFFFFFFF)

        # R-Type ALU
        elif mnem == Mnemonic.ADD:
            res = (self.registers.read(rs1) + self.registers.read(rs2)) & 0xFFFFFFFF
            self.registers.write(rd, res)

        elif mnem == Mnemonic.SUB:
            res = (self.registers.read(rs1) - self.registers.read(rs2)) & 0xFFFFFFFF
            self.registers.write(rd, res)

        elif mnem == Mnemonic.SLL:
            shamt = self.registers.read(rs2) & 0x1F
            self.registers.write(rd, (self.registers.read(rs1) << shamt) & 0xFFFFFFFF)

        elif mnem == Mnemonic.SLT:
            is_less = 1 if self.registers.read_signed(rs1) < self.registers.read_signed(rs2) else 0
            self.registers.write(rd, is_less)

        elif mnem == Mnemonic.SLTU:
            is_less = 1 if self.registers.read(rs1) < self.registers.read(rs2) else 0
            self.registers.write(rd, is_less)

        elif mnem == Mnemonic.XOR:
            self.registers.write(rd, (self.registers.read(rs1) ^ self.registers.read(rs2)) & 0xFFFFFFFF)

        elif mnem == Mnemonic.SRL:
            shamt = self.registers.read(rs2) & 0x1F
            self.registers.write(rd, (self.registers.read(rs1) >> shamt) & 0xFFFFFFFF)

        elif mnem == Mnemonic.SRA:
            shamt = self.registers.read(rs2) & 0x1F
            signed_val = self.registers.read_signed(rs1)
            self.registers.write(rd, (signed_val >> shamt) & 0xFFFFFFFF)

        elif mnem == Mnemonic.OR:
            self.registers.write(rd, (self.registers.read(rs1) | self.registers.read(rs2)) & 0xFFFFFFFF)

        elif mnem == Mnemonic.AND:
            self.registers.write(rd, (self.registers.read(rs1) & self.registers.read(rs2)) & 0xFFFFFFFF)

        # System instructions
        elif mnem == Mnemonic.ECALL:
            trap = TrapCause.ENVIRONMENT_CALL
            self.halted = True

        elif mnem == Mnemonic.EBREAK:
            trap = TrapCause.BREAKPOINT
            self.halted = True

        elif mnem in (Mnemonic.CSRRW, Mnemonic.CSRRS, Mnemonic.CSRRC):
            csr_addr = imm & 0xFFF
            old_val = self.registers.read_csr(csr_addr)
            rs1_val = self.registers.read(rs1)

            if mnem == Mnemonic.CSRRW:
                self.registers.write_csr(csr_addr, rs1_val)
            elif mnem == Mnemonic.CSRRS:
                if rs1 != 0:
                    self.registers.write_csr(csr_addr, old_val | rs1_val)
            elif mnem == Mnemonic.CSRRC:
                if rs1 != 0:
                    self.registers.write_csr(csr_addr, old_val & ~rs1_val)

            self.registers.write(rd, old_val)

        elif mnem in (Mnemonic.CSRRWI, Mnemonic.CSRRSI, Mnemonic.CSRRCI):
            csr_addr = imm & 0xFFF
            old_val = self.registers.read_csr(csr_addr)
            zimm = rs1  # 5-bit unsigned immediate is encoded in rs1 field

            if mnem == Mnemonic.CSRRWI:
                self.registers.write_csr(csr_addr, zimm)
            elif mnem == Mnemonic.CSRRSI:
                if zimm != 0:
                    self.registers.write_csr(csr_addr, old_val | zimm)
            elif mnem == Mnemonic.CSRRCI:
                if zimm != 0:
                    self.registers.write_csr(csr_addr, old_val & ~zimm)

            self.registers.write(rd, old_val)

        elif mnem == Mnemonic.FENCE:
            pass  # NOP in single-threaded software simulation

        else:
            raise CpuTrap(cause=TrapCause.ILLEGAL_INSTRUCTION, pc=current_pc, value=raw_inst)

        # Advance state
        self._pc = next_pc
        self._cycles += step_cycles
        self._instructions_executed += 1
        self.bus.cycle_count = self._cycles
        self.registers.increment_cycle_counters(cycles=step_cycles, instructions=1)

        return StepResult(
            pc=current_pc,
            next_pc=next_pc,
            instruction_raw=raw_inst,
            mnemonic=str(inst),
            cycles=step_cycles,
            trap=trap,
        )
