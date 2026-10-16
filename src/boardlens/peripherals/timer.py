"""Authentic hardware SysTick timer peripheral."""

from typing import Callable, List
from boardlens.peripherals.base import Peripheral


class SysTickTimer(Peripheral):
    """24-bit system down-counter timer with auto-reload and interrupt flag generation."""

    REG_CSR = 0x00
    REG_RVR = 0x04
    REG_CVR = 0x08

    CSR_ENABLE = 1 << 0
    CSR_TICKINT = 1 << 1
    CSR_CLKSOURCE = 1 << 2
    CSR_COUNTFLAG = 1 << 16

    def __init__(self, base_address: int = 0x40002000, name: str = "SysTick") -> None:
        super().__init__(base_address, size=0x400, name=name)
        self.register_def(self.REG_CSR, "CSR", reset_val=0x00000000, write_mask=0x00010007)
        self.register_def(self.REG_RVR, "RVR", reset_val=0x00FFFFFF, write_mask=0x00FFFFFF)
        self.register_def(self.REG_CVR, "CVR", reset_val=0x00000000, write_mask=0x00FFFFFF)

        self._tick_listeners: List[Callable[[], None]] = []

    def add_tick_listener(self, listener: Callable[[], None]) -> None:
        """Register a callback invoked when the timer expires and reloads."""
        self._tick_listeners.append(listener)

    def on_register_write(self, offset: int, old_value: int, new_value: int) -> None:
        if offset == self.REG_CSR:
            # When enabling the counter (ENABLE goes 0 -> 1), load CVR from RVR if CVR is 0
            if (new_value & self.CSR_ENABLE) and not (old_value & self.CSR_ENABLE):
                if self._regs.get(self.REG_CVR, 0) == 0:
                    self._regs[self.REG_CVR] = self._regs.get(self.REG_RVR, 0) & 0x00FFFFFF

        elif offset == self.REG_CVR:
            # Writing any value to CVR reloads it from RVR and clears COUNTFLAG
            rvr = self._regs.get(self.REG_RVR, 0) & 0x00FFFFFF
            self._regs[self.REG_CVR] = rvr
            self._regs[self.REG_CSR] &= ~self.CSR_COUNTFLAG

    def on_register_read(self, offset: int, value: int) -> int:
        if offset == self.REG_CSR:
            # Reading CSR clears COUNTFLAG
            val = self._regs.get(self.REG_CSR, 0)
            self._regs[self.REG_CSR] &= ~self.CSR_COUNTFLAG
            return val
        return value

    def step(self, cycles: int = 1) -> None:
        """Simulate timer step on processor clock cycles."""
        csr = self._regs.get(self.REG_CSR, 0)
        if not (csr & self.CSR_ENABLE):
            return

        cvr = self._regs.get(self.REG_CVR, 0)
        rvr = self._regs.get(self.REG_RVR, 0) & 0x00FFFFFF

        cvr -= cycles
        if cvr <= 0:
            self._regs[self.REG_CSR] |= self.CSR_COUNTFLAG
            # Reload
            if rvr > 0:
                cvr = rvr - (abs(cvr) % rvr)
            else:
                cvr = 0
            for listener in self._tick_listeners:
                listener()

        self._regs[self.REG_CVR] = max(0, cvr) & 0x00FFFFFF
