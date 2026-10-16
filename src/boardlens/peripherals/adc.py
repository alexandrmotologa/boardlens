"""12-bit Analog-to-Digital Converter (ADC) peripheral."""

from typing import Callable, List, Optional
from boardlens.peripherals.base import Peripheral


class ADCPeripheral(Peripheral):
    """12-bit Successive Approximation ADC with multiple input channels.

    Simulates a hardware ADC with standard status and control registers,
    sampling 0-3300 mV analog inputs into 12-bit digital values (0-4095).
    """

    REG_SR = 0x00     # Status Register
    REG_CR1 = 0x04    # Control Register 1
    REG_CR2 = 0x08    # Control Register 2
    REG_SMPR = 0x0C   # Sample Time Register
    REG_DR = 0x10     # Regular Data Register (12-bit right-aligned)
    REG_SQR = 0x14    # Regular Sequence Register (channel selection)
    REG_CH0 = 0x20    # Channel 0 Millivolts (simulation / direct access)
    REG_CH1 = 0x24    # Channel 1 Millivolts
    REG_CH2 = 0x28    # Channel 2 Millivolts
    REG_CH3 = 0x2C    # Channel 3 Millivolts

    # SR status bits
    SR_EOC = 1 << 1    # End of conversion
    SR_AWD = 1 << 0    # Analog watchdog flag
    SR_STRT = 1 << 4   # Regular channel start flag

    # CR1 control bits
    CR1_EOCIE = 1 << 5 # EOC interrupt enable
    CR1_SCAN = 1 << 8  # Scan mode enable

    # CR2 control bits
    CR2_ADON = 1 << 0      # A/D converter ON / OFF
    CR2_CONT = 1 << 1      # Continuous conversion
    CR2_SWSTART = (1 << 30) | (1 << 22)  # Start conversion of regular channels

    VREF_MV = 3300
    RESOLUTION_BITS = 12
    MAX_ADC_VAL = (1 << RESOLUTION_BITS) - 1  # 4095

    def __init__(self, base_address: int = 0x40004000, name: str = "ADC0") -> None:
        super().__init__(base_address, size=0x400, name=name)
        # Register definitions
        self.register_def(self.REG_SR, "SR", reset_val=0, write_mask=0x1F)
        self.register_def(self.REG_CR1, "CR1", reset_val=0, write_mask=0xFFFFFFFF)
        self.register_def(self.REG_CR2, "CR2", reset_val=0, write_mask=0xFFFFFFFF)
        self.register_def(self.REG_SMPR, "SMPR", reset_val=0, write_mask=0xFFFFFFFF)
        self.register_def(self.REG_DR, "DR", reset_val=0, write_mask=0x00000000)  # Read-only
        self.register_def(self.REG_SQR, "SQR", reset_val=0, write_mask=0xFFFFFFFF)
        self.register_def(self.REG_CH0, "CH0", reset_val=0, write_mask=0xFFFFFFFF)
        self.register_def(self.REG_CH1, "CH1", reset_val=0, write_mask=0xFFFFFFFF)
        self.register_def(self.REG_CH2, "CH2", reset_val=0, write_mask=0xFFFFFFFF)
        self.register_def(self.REG_CH3, "CH3", reset_val=0, write_mask=0xFFFFFFFF)

        self._channel_mv: List[int] = [0, 0, 0, 0]
        self._conversion_listeners: List[Callable[[int, int, int], None]] = []

    def set_channel_millivolts(self, channel: int, mv: int) -> None:
        """Set analog input voltage on specified channel (0-3) in millivolts."""
        if 0 <= channel < len(self._channel_mv):
            clamped = max(0, min(mv, self.VREF_MV))
            self._channel_mv[channel] = clamped
            reg_offset = self.REG_CH0 + (channel * 4)
            self._regs[reg_offset] = clamped

    def get_channel_millivolts(self, channel: int) -> int:
        """Get analog input voltage on specified channel in millivolts."""
        if 0 <= channel < len(self._channel_mv):
            return self._channel_mv[channel]
        return 0

    def get_channel_voltage(self, channel: int) -> float:
        """Get analog input voltage on specified channel in Volts."""
        return self.get_channel_millivolts(channel) / 1000.0

    def add_conversion_listener(self, listener: Callable[[int, int, int], None]) -> None:
        """Add callback (channel, millivolts, digital_val) triggered when conversion finishes."""
        self._conversion_listeners.append(listener)

    def trigger_conversion(self, channel: Optional[int] = None) -> int:
        """Execute an authentic A/D conversion step."""
        cr2 = self._regs.get(self.REG_CR2, 0)
        # If ADC is disabled (ADON = 0), conversion doesn't run
        if not (cr2 & self.CR2_ADON):
            return 0

        if channel is None:
            sqr = self._regs.get(self.REG_SQR, 0)
            channel = sqr & 0x03  # Select channel 0..3

        mv = self.get_channel_millivolts(channel)
        # 12-bit conversion formula: (Vin / Vref) * 4095
        digital_val = int(round((mv / float(self.VREF_MV)) * self.MAX_ADC_VAL))
        digital_val = max(0, min(digital_val, self.MAX_ADC_VAL))

        # Store in DR
        self._regs[self.REG_DR] = digital_val

        # Update SR: set EOC (End of Conversion) and STRT
        sr = self._regs.get(self.REG_SR, 0)
        sr |= self.SR_EOC | self.SR_STRT
        self._regs[self.REG_SR] = sr

        # Clear SWSTART bit in CR2 if not continuous mode
        if not (cr2 & self.CR2_CONT):
            self._regs[self.REG_CR2] = cr2 & ~self.CR2_SWSTART

        for listener in self._conversion_listeners:
            listener(channel, mv, digital_val)

        return digital_val

    def step(self, cycles: int = 1) -> None:
        """Advance ADC internal clock and run continuous conversions if enabled."""
        cr2 = self._regs.get(self.REG_CR2, 0)
        if (cr2 & self.CR2_ADON) and (cr2 & self.CR2_CONT):
            sr = self._regs.get(self.REG_SR, 0)
            if not (sr & self.SR_EOC):
                self.trigger_conversion()

    def on_register_write(self, offset: int, old_val: int, new_val: int) -> None:
        if offset == self.REG_CR2:
            # Check if SWSTART was written as 1 and ADON is 1
            if (new_val & self.CR2_SWSTART) and (new_val & self.CR2_ADON):
                self.trigger_conversion()
        elif offset in (self.REG_CH0, self.REG_CH1, self.REG_CH2, self.REG_CH3):
            ch = (offset - self.REG_CH0) // 4
            self.set_channel_millivolts(ch, new_val)

    def on_register_read(self, offset: int, value: int) -> int:
        if offset == self.REG_DR:
            # Reading DR clears EOC in SR
            sr = self._regs.get(self.REG_SR, 0)
            self._regs[self.REG_SR] = sr & ~self.SR_EOC
            # In continuous mode, trigger next conversion automatically
            cr2 = self._regs.get(self.REG_CR2, 0)
            if (cr2 & self.CR2_ADON) and (cr2 & self.CR2_CONT):
                self.trigger_conversion()
        return value
