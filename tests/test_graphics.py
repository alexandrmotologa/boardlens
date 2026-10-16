"""Unit tests for SSD1306 graphics primitives and 5x7 font engine."""

import pytest
from boardlens.devices.graphics import FONT_5X7, SSD1306GFX
from boardlens.devices.ssd1306 import SSD1306


def test_font_table_completeness():
    # 95 printable ASCII characters: 32 (space) to 126 (tilde)
    assert len(FONT_5X7) == 95
    for glyph in FONT_5X7:
        assert len(glyph) == 5
        for col in glyph:
            assert 0 <= col <= 0xFF


def test_pixel_and_line_primitives():
    oled = SSD1306()
    gfx = SSD1306GFX(oled)

    # Pixel set and get
    gfx.draw_pixel(10, 10, 1)
    assert gfx.get_pixel(10, 10) == 1
    assert gfx.get_pixel(11, 10) == 0

    # Bounds clipping
    gfx.draw_pixel(-1, 0, 1)
    gfx.draw_pixel(200, 200, 1)
    assert gfx.get_pixel(-1, 0) == 0

    # Fast horizontal and vertical lines
    gfx.draw_fast_h_line(20, 30, 10, 1)
    for x in range(20, 30):
        assert gfx.get_pixel(x, 30) == 1
    assert gfx.get_pixel(19, 30) == 0
    assert gfx.get_pixel(30, 30) == 0

    gfx.draw_fast_v_line(40, 10, 8, 1)
    for y in range(10, 18):
        assert gfx.get_pixel(40, y) == 1
    assert gfx.get_pixel(40, 9) == 0
    assert gfx.get_pixel(40, 18) == 0

    # Bresenham diagonal line
    gfx.draw_line(0, 0, 5, 5, 1)
    for i in range(6):
        assert gfx.get_pixel(i, i) == 1


def test_rectangles_and_circles():
    oled = SSD1306()
    gfx = SSD1306GFX(oled)

    # Outline rectangle
    gfx.draw_rect(5, 5, 10, 8, 1)
    assert gfx.get_pixel(5, 5) == 1
    assert gfx.get_pixel(14, 5) == 1
    assert gfx.get_pixel(5, 12) == 1
    assert gfx.get_pixel(14, 12) == 1
    # Interior must be empty
    assert gfx.get_pixel(8, 8) == 0

    # Filled rectangle
    gfx.fill_rect(30, 20, 6, 6, 1)
    for y in range(20, 26):
        for x in range(30, 36):
            assert gfx.get_pixel(x, y) == 1
    assert gfx.get_pixel(29, 20) == 0

    # Circle outline
    gfx.draw_circle(64, 32, 10, 1)
    # Cardinal points
    assert gfx.get_pixel(64 + 10, 32) == 1
    assert gfx.get_pixel(64 - 10, 32) == 1
    assert gfx.get_pixel(64, 32 + 10) == 1
    assert gfx.get_pixel(64, 32 - 10) == 1
    # Center empty
    assert gfx.get_pixel(64, 32) == 0

    # Filled circle
    gfx.fill_circle(100, 32, 5, 1)
    assert gfx.get_pixel(100, 32) == 1
    assert gfx.get_pixel(100 + 4, 32) == 1


def test_triangles_and_round_rects():
    oled = SSD1306()
    gfx = SSD1306GFX(oled)

    # Triangle outline
    gfx.draw_triangle(10, 50, 20, 30, 30, 50, 1)
    assert gfx.get_pixel(20, 30) == 1
    assert gfx.get_pixel(10, 50) == 1
    assert gfx.get_pixel(30, 50) == 1

    # Filled triangle
    gfx.fill_triangle(50, 50, 60, 30, 70, 50, 1)
    assert gfx.get_pixel(60, 40) == 1

    # Rounded rectangle
    gfx.draw_round_rect(80, 10, 20, 15, 3, 1)
    # Inside straight edges
    assert gfx.get_pixel(85, 10) == 1
    assert gfx.get_pixel(85, 24) == 1


def test_text_and_character_rendering():
    oled = SSD1306()
    gfx = oled.gfx

    # Character rendering
    w = gfx.draw_char(0, 0, "A", color=1, bg=0, size=1)
    assert w == 6  # 5 cols + 1 space

    # 'A' has pixel in column 0 (0x7E: bits 1..6)
    assert gfx.get_pixel(0, 1) == 1
    assert gfx.get_pixel(0, 0) == 0

    # Draw string
    cur_x, cur_y = gfx.draw_string(0, 10, "Hi!", color=1, size=1)
    assert cur_x == 18  # 3 chars * 6px
    assert cur_y == 10

    # Multiline string
    _, cur_y = gfx.draw_string(0, 20, "Line1\nLine2", color=1, size=1)
    assert cur_y == 28

    # Scaled text
    w_scaled = gfx.draw_char(0, 40, "X", color=1, size=2)
    assert w_scaled == 12


def test_bitmap_rendering():
    oled = SSD1306()
    gfx = oled.gfx

    # 8x8 checkerboard bitmap: 0xAA = 10101010, 0x55 = 01010101
    bitmap = [0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x55]
    gfx.draw_bitmap(10, 10, bitmap, 8, 8, color=1, bg=0)

    assert gfx.get_pixel(10, 10) == 1
    assert gfx.get_pixel(11, 10) == 0
    assert gfx.get_pixel(10, 11) == 0
    assert gfx.get_pixel(11, 11) == 1
