"""Unit tests for GPIOPort peripheral."""

import pytest
from boardlens.peripherals.gpio import GPIOPort


def test_gpio_pin_modes_and_output():
    gpio = GPIOPort(base_address=0x40000000)

    # Set Pin 0 and Pin 5 as outputs (01 in MODER: pin0 bits 1:0 = 01, pin5 bits 11:10 = 01)
    # MODER: (1 << 0) | (1 << 10) = 0x00000401
    gpio.write32(GPIOPort.REG_MODER, 0x00000401)
    assert gpio.get_pin_mode(0) == GPIOPort.MODE_OUTPUT
    assert gpio.get_pin_mode(5) == GPIOPort.MODE_OUTPUT
    assert gpio.get_pin_mode(1) == GPIOPort.MODE_INPUT

    # Track output pin toggles via listener
    toggles = []
    gpio.add_pin_listener(lambda pin, high: toggles.append((pin, high)))

    # Drive Pin 0 HIGH via ODR
    gpio.write32(GPIOPort.REG_ODR, 0x0001)
    assert gpio.get_pin_output(0) is True
    assert gpio.get_pin_state(0) is True
    assert (0, True) in toggles

    # Atomic set/reset via BSRR: Set Pin 5, Reset Pin 0
    # bits 0-15: set (bit 5 = 1 << 5 = 32), bits 16-31: reset (bit 16 = 1 << 16)
    gpio.write32(GPIOPort.REG_BSRR, (1 << 5) | (1 << 16))
    assert gpio.get_pin_output(5) is True
    assert gpio.get_pin_output(0) is False
    assert (5, True) in toggles
    assert (0, False) in toggles


def test_gpio_external_input():
    gpio = GPIOPort(base_address=0x40000000)
    # Pin 2 is input by default
    assert gpio.get_pin_mode(2) == GPIOPort.MODE_INPUT

    # External button presses Pin 2
    gpio.set_pin_input(2, True)
    assert gpio.get_pin_state(2) is True
    # IDR register should reflect the pin state
    idr = gpio.read32(GPIOPort.REG_IDR)
    assert bool(idr & (1 << 2)) is True

    # Release button
    gpio.set_pin_input(2, False)
    assert gpio.get_pin_state(2) is False
    idr = gpio.read32(GPIOPort.REG_IDR)
    assert bool(idr & (1 << 2)) is False

    with pytest.raises(IndexError):
        gpio.set_pin_input(16, True)
