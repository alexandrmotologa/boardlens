"""Unit tests for the 12-bit ADC peripheral."""

import pytest
from boardlens.board import Board
from boardlens.peripherals.adc import ADCPeripheral


def test_adc_initialization():
    adc = ADCPeripheral(base_address=0x40004000)
    assert adc.base_address == 0x40004000
    assert adc.read_reg(ADCPeripheral.REG_SR) == 0
    assert adc.read_reg(ADCPeripheral.REG_CR1) == 0
    assert adc.read_reg(ADCPeripheral.REG_CR2) == 0
    assert adc.read_reg(ADCPeripheral.REG_DR) == 0


def test_adc_channel_voltage_setting():
    adc = ADCPeripheral()
    adc.set_channel_millivolts(0, 1650)
    adc.set_channel_millivolts(1, 3300)
    adc.set_channel_millivolts(2, 5000)  # Should clamp to 3300
    adc.set_channel_millivolts(3, -100)  # Should clamp to 0

    assert adc.get_channel_millivolts(0) == 1650
    assert adc.get_channel_voltage(0) == 1.65
    assert adc.get_channel_millivolts(1) == 3300
    assert adc.get_channel_voltage(1) == 3.3
    assert adc.get_channel_millivolts(2) == 3300
    assert adc.get_channel_millivolts(3) == 0
    # Out of range channel
    assert adc.get_channel_millivolts(4) == 0


def test_adc_conversion_disabled_when_adon_zero():
    adc = ADCPeripheral()
    adc.set_channel_millivolts(0, 1650)
    # ADON is 0, so conversion must return 0 and not set EOC
    val = adc.trigger_conversion(0)
    assert val == 0
    assert adc.read_reg(ADCPeripheral.REG_DR) == 0
    assert (adc.read_reg(ADCPeripheral.REG_SR) & ADCPeripheral.SR_EOC) == 0


def test_adc_conversion_full_scale():
    adc = ADCPeripheral()
    # Enable ADC
    adc.write_reg(ADCPeripheral.REG_CR2, ADCPeripheral.CR2_ADON)

    # 0V -> 0
    adc.set_channel_millivolts(0, 0)
    val0 = adc.trigger_conversion(0)
    assert val0 == 0
    assert adc.read_reg(ADCPeripheral.REG_DR) == 0

    # 3.3V (3300mV) -> 4095
    adc.set_channel_millivolts(1, 3300)
    val1 = adc.trigger_conversion(1)
    assert val1 == 4095
    assert adc.read_reg(ADCPeripheral.REG_DR) == 4095

    # 1.65V (1650mV) -> ~2048
    adc.set_channel_millivolts(2, 1650)
    val2 = adc.trigger_conversion(2)
    assert 2046 <= val2 <= 2050


def test_adc_eoc_flag_and_read_clearing():
    adc = ADCPeripheral()
    adc.write_reg(ADCPeripheral.REG_CR2, ADCPeripheral.CR2_ADON)
    adc.set_channel_millivolts(0, 1000)

    adc.trigger_conversion(0)
    sr = adc.read_reg(ADCPeripheral.REG_SR)
    assert (sr & ADCPeripheral.SR_EOC) != 0

    # Reading DR must clear EOC flag in SR
    _ = adc.read_reg(ADCPeripheral.REG_DR)
    sr_after = adc.read_reg(ADCPeripheral.REG_SR)
    assert (sr_after & ADCPeripheral.SR_EOC) == 0


def test_adc_swstart_trigger():
    adc = ADCPeripheral()
    adc.set_channel_millivolts(0, 2200)

    # Write ADON + SWSTART
    adc.write_reg(ADCPeripheral.REG_CR2, ADCPeripheral.CR2_ADON | (1 << 30))

    # Should have triggered conversion
    sr = adc.read_reg(ADCPeripheral.REG_SR)
    assert (sr & ADCPeripheral.SR_EOC) != 0
    dr = adc.read_reg(ADCPeripheral.REG_DR)
    expected = int(round((2200 / 3300.0) * 4095))
    assert dr == expected


def test_adc_continuous_mode_and_step():
    adc = ADCPeripheral()
    adc.set_channel_millivolts(0, 825)
    # Enable ADON + CONT
    adc.write_reg(ADCPeripheral.REG_CR2, ADCPeripheral.CR2_ADON | ADCPeripheral.CR2_CONT)

    # Trigger first conversion
    adc.trigger_conversion(0)
    assert (adc.read_reg(ADCPeripheral.REG_SR) & ADCPeripheral.SR_EOC) != 0

    # Reading DR clears EOC, which in continuous mode triggers the next conversion
    dr = adc.read_reg(ADCPeripheral.REG_DR)
    assert dr == int(round((825 / 3300.0) * 4095))

    # In step(), continuous mode checks if conversion needs to run
    adc.step(cycles=10)
    assert (adc.read_reg(ADCPeripheral.REG_SR) & ADCPeripheral.SR_EOC) != 0


def test_adc_conversion_listener():
    adc = ADCPeripheral()
    adc.write_reg(ADCPeripheral.REG_CR2, ADCPeripheral.CR2_ADON)
    adc.set_channel_millivolts(1, 1000)

    events = []
    adc.add_conversion_listener(lambda ch, mv, val: events.append((ch, mv, val)))

    adc.trigger_conversion(1)
    assert len(events) == 1
    ch, mv, val = events[0]
    assert ch == 1
    assert mv == 1000
    assert val == int(round((1000 / 3300.0) * 4095))


def test_adc_board_mmio_integration():
    board = Board()
    assert hasattr(board, "adc")

    # Access ADC registers through MemoryBus
    board.adc.set_channel_millivolts(0, 3300)
    # Write CR2 = ADON via bus
    board.bus.write32(Board.ADC_BASE + ADCPeripheral.REG_CR2, ADCPeripheral.CR2_ADON)

    # Write SWSTART via bus
    board.bus.write32(Board.ADC_BASE + ADCPeripheral.REG_CR2, ADCPeripheral.CR2_ADON | (1 << 30))

    # Read DR via bus
    dr = board.bus.read32(Board.ADC_BASE + ADCPeripheral.REG_DR)
    assert dr == 4095

    # Direct write to CH1 register via bus
    board.bus.write32(Board.ADC_BASE + ADCPeripheral.REG_CH1, 1650)
    assert board.adc.get_channel_millivolts(1) == 1650

    # Reset board resets ADC
    board.reset()
    assert board.adc.read_reg(ADCPeripheral.REG_DR) == 0
