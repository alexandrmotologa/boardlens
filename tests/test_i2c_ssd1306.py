"""Unit tests for I2CController and SSD1306 virtual OLED display."""

import pytest
from boardlens.devices.ssd1306 import SSD1306
from boardlens.peripherals.i2c import I2CController


def test_i2c_ssd1306_transaction():
    i2c = I2CController(base_address=0x40003000)
    oled = SSD1306(address=0x3C)
    i2c.attach_device(oled)

    # 1. Enable I2C peripheral
    i2c.write32(I2CController.REG_CR1, I2CController.CR1_PE)

    # 2. Generate START condition
    i2c.write32(I2CController.REG_CR1, I2CController.CR1_PE | I2CController.CR1_START)
    sr1 = i2c.read32(I2CController.REG_SR1)
    assert bool(sr1 & I2CController.SR1_SB) is True

    # 3. Send 7-bit slave address + Write bit (0x3C << 1 = 0x78)
    i2c.write32(I2CController.REG_DR, 0x78)
    sr1 = i2c.read32(I2CController.REG_SR1)
    sr2 = i2c.read32(I2CController.REG_SR2)  # Reading SR2 clears ADDR
    assert bool(sr1 & I2CController.SR1_ADDR) is True

    # 4. Send Command packet: Co=0, D/C#=0 -> 0x00, followed by Display ON: 0xAF
    i2c.write32(I2CController.REG_DR, 0x00)  # Control byte: command stream
    i2c.write32(I2CController.REG_DR, 0xAF)  # Command: Display ON
    assert oled.display_on is True

    # Set Contrast: 0x81, 0x55
    i2c.write32(I2CController.REG_DR, 0x81)
    i2c.write32(I2CController.REG_DR, 0x55)
    assert oled.contrast == 0x55

    # 5. Generate STOP condition
    i2c.write32(I2CController.REG_CR1, I2CController.CR1_PE | I2CController.CR1_STOP)


def test_ssd1306_pixel_operations_and_rendering():
    oled = SSD1306(address=0x3C)
    oled.display_on = True

    # Initially all pixels dark
    assert oled.get_pixel(0, 0) is False
    assert oled.get_pixel(10, 10) is False

    # Set pixel directly
    oled.set_pixel(10, 10, True)
    assert oled.get_pixel(10, 10) is True

    # Pixel matrix export
    matrix = oled.to_pixel_matrix()
    assert len(matrix) == 64
    assert len(matrix[0]) == 128
    assert matrix[10][10] == 1
    assert matrix[0][0] == 0

    # Invert display
    oled.inverted = True
    assert oled.get_pixel(10, 10) is False
    assert oled.get_pixel(0, 0) is True
    oled.inverted = False

    # Draw a line and verify ASCII render
    for x in range(128):
        oled.set_pixel(x, 0, True)

    ascii_art = oled.render_ascii()
    assert "▀" in ascii_art or "█" in ascii_art

    # Clear
    oled.clear()
    assert oled.get_pixel(10, 10) is False


def test_ssd1306_data_stream_via_i2c():
    i2c = I2CController()
    oled = SSD1306()
    i2c.attach_device(oled)

    # Turn ON display
    oled.display_on = True
    oled.addressing_mode = SSD1306.MODE_PAGE
    oled.current_page = 0
    oled.current_column = 0

    # Send START -> ADDR -> Data Stream (Control byte 0x40, then byte 0x01)
    # Byte 0x01 has bit 0 set, so pixel at (x=0, y=0) should be ON
    i2c.write32(I2CController.REG_CR1, I2CController.CR1_PE | I2CController.CR1_START)
    i2c.write32(I2CController.REG_DR, 0x78)  # ADDR
    i2c.read32(I2CController.REG_SR2)
    i2c.write32(I2CController.REG_DR, 0x40)  # Control byte: Data
    i2c.write32(I2CController.REG_DR, 0x03)  # Bit 0 and Bit 1 set -> (0,0) and (0,1) ON
    i2c.write32(I2CController.REG_CR1, I2CController.CR1_PE | I2CController.CR1_STOP)

    assert oled.get_pixel(0, 0) is True
    assert oled.get_pixel(0, 1) is True
    assert oled.get_pixel(0, 2) is False
