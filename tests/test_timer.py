"""Unit tests for SysTickTimer peripheral."""

import pytest
from boardlens.peripherals.timer import SysTickTimer


def test_systick_timer():
    timer = SysTickTimer()

    # Configure reload register to 10 cycles
    timer.write32(SysTickTimer.REG_RVR, 10)
    # Enable timer
    timer.write32(SysTickTimer.REG_CSR, SysTickTimer.CSR_ENABLE | SysTickTimer.CSR_CLKSOURCE)

    ticks = 0
    timer.add_tick_listener(lambda: setattr(timer, "_ticks_fired", getattr(timer, "_ticks_fired", 0) + 1))
    timer._ticks_fired = 0

    # Step 5 cycles -> no tick yet
    timer.step(5)
    assert timer._ticks_fired == 0
    csr = timer.read32(SysTickTimer.REG_CSR)
    assert bool(csr & SysTickTimer.CSR_COUNTFLAG) is False

    # Step 6 cycles -> tick should fire
    timer.step(6)
    assert timer._ticks_fired == 1
    # Countflag asserted
    csr = timer.read32(SysTickTimer.REG_CSR)
    assert bool(csr & SysTickTimer.CSR_COUNTFLAG) is True
    # Reading CSR clears COUNTFLAG
    csr2 = timer.read32(SysTickTimer.REG_CSR)
    assert bool(csr2 & SysTickTimer.CSR_COUNTFLAG) is False
