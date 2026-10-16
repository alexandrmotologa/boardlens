"""Authentic GPIO Port peripheral implementation."""

from typing import Callable, List
from boardlens.peripherals.base import Peripheral


class GPIOPort(Peripheral):
    """General Purpose Input/Output controller with 16 configurable I/O pins."""

    REG_MODER = 0x00
    REG_OTYPER = 0x04
    REG_OSPEEDR = 0x08
    REG_PUPDR = 0x0C
    REG_IDR = 0x10
    REG_ODR = 0x14
    REG_BSRR = 0x18

    # Pin Modes
    MODE_INPUT = 0
    MODE_OUTPUT = 1
    MODE_ALTERNATE = 2
    MODE_ANALOG = 3

    def __init__(self, base_address: int = 0x40000000, name: str = "GPIOA") -> None:
        super().__init__(base_address, size=0x400, name=name)
        # Register definitions
        self.register_def(self.REG_MODER, "MODER", reset_val=0x00000000)
        self.register_def(self.REG_OTYPER, "OTYPER", reset_val=0x00000000, write_mask=0x0000FFFF)
        self.register_def(self.REG_OSPEEDR, "OSPEEDR", reset_val=0x00000000)
        self.register_def(self.REG_PUPDR, "PUPDR", reset_val=0x00000000)
        self.register_def(self.REG_IDR, "IDR", reset_val=0x00000000, write_mask=0x00000000)  # Read-only
        self.register_def(self.REG_ODR, "ODR", reset_val=0x00000000, write_mask=0x0000FFFF)
        self.register_def(self.REG_BSRR, "BSRR", reset_val=0x00000000, read_mask=0x00000000)  # Write-only

        self._external_inputs: int = 0  # 16-bit external line levels
        self._listeners: List[Callable[[int, bool], None]] = []

    def add_pin_listener(self, listener: Callable[[int, bool], None]) -> None:
        """Register a callback for pin output state changes (pin: int, state: bool)."""
        self._listeners.append(listener)

    def _notify_pin(self, pin: int, high: bool) -> None:
        for listener in self._listeners:
            listener(pin, high)

    def set_pin_input(self, pin: int, high: bool) -> None:
        """Externally drive a pin input level (e.g. from a virtual button or sensor)."""
        if not 0 <= pin < 16:
            raise IndexError("Pin must be between 0 and 15")
        if high:
            self._external_inputs |= (1 << pin)
        else:
            self._external_inputs &= ~(1 << pin)

    def get_pin_mode(self, pin: int) -> int:
        """Get 2-bit mode for specified pin."""
        moder = self._regs.get(self.REG_MODER, 0)
        return (moder >> (pin * 2)) & 0x3

    def get_pin_output(self, pin: int) -> bool:
        """Get current output level driven by ODR."""
        odr = self._regs.get(self.REG_ODR, 0)
        return bool((odr >> pin) & 1)

    def get_pin_state(self, pin: int) -> bool:
        """Get effective pin level (from external input if input mode, else from ODR)."""
        mode = self.get_pin_mode(pin)
        if mode == self.MODE_INPUT:
            # Check pull-up / pull-down if not driven
            return bool((self._external_inputs >> pin) & 1)
        elif mode == self.MODE_OUTPUT:
            return self.get_pin_output(pin)
        return False

    def on_register_read(self, offset: int, value: int) -> int:
        if offset == self.REG_IDR:
            # Calculate IDR dynamically based on current pin states
            idr_val = 0
            for pin in range(16):
                if self.get_pin_state(pin):
                    idr_val |= (1 << pin)
            return idr_val
        return value

    def on_register_write(self, offset: int, old_value: int, new_value: int) -> None:
        if offset == self.REG_ODR:
            diff = (old_value ^ new_value) & 0xFFFF
            for pin in range(16):
                if (diff >> pin) & 1:
                    is_high = bool((new_value >> pin) & 1)
                    self._notify_pin(pin, is_high)

        elif offset == self.REG_BSRR:
            # Lower 16 bits: atomic set
            set_bits = new_value & 0xFFFF
            # Upper 16 bits: atomic reset
            reset_bits = (new_value >> 16) & 0xFFFF

            current_odr = self._regs.get(self.REG_ODR, 0)
            next_odr = (current_odr | set_bits) & ~reset_bits
            self._regs[self.REG_ODR] = next_odr & 0xFFFF

            diff = (current_odr ^ next_odr) & 0xFFFF
            for pin in range(16):
                if (diff >> pin) & 1:
                    is_high = bool((next_odr >> pin) & 1)
                    self._notify_pin(pin, is_high)
