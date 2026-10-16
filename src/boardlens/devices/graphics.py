"""Graphics primitives and 5x7 ASCII font engine for SSD1306 OLED display."""

import math
from typing import Any, List, Optional, Sequence, Tuple, Union

# Standard 5x7 ASCII Font Table (characters 32 to 126 inclusive)
# Each character is defined by 5 column bytes, where bit 0 is top and bit 6 is bottom.
FONT_5X7: List[Tuple[int, int, int, int, int]] = [
    (0x00, 0x00, 0x00, 0x00, 0x00),  # 32 ' '
    (0x00, 0x00, 0x5F, 0x00, 0x00),  # 33 '!'
    (0x00, 0x07, 0x00, 0x07, 0x00),  # 34 '"'
    (0x14, 0x7F, 0x14, 0x7F, 0x14),  # 35 '#'
    (0x24, 0x2A, 0x6B, 0x2A, 0x12),  # 36 '$'
    (0x23, 0x13, 0x08, 0x64, 0x62),  # 37 '%'
    (0x36, 0x49, 0x55, 0x22, 0x50),  # 38 '&'
    (0x00, 0x05, 0x03, 0x00, 0x00),  # 39 '''
    (0x00, 0x1C, 0x22, 0x41, 0x00),  # 40 '('
    (0x00, 0x41, 0x22, 0x1C, 0x00),  # 41 ')'
    (0x14, 0x08, 0x3E, 0x08, 0x14),  # 42 '*'
    (0x08, 0x08, 0x3E, 0x08, 0x08),  # 43 '+'
    (0x00, 0x50, 0x30, 0x00, 0x00),  # 44 ','
    (0x08, 0x08, 0x08, 0x08, 0x08),  # 45 '-'
    (0x00, 0x60, 0x60, 0x00, 0x00),  # 46 '.'
    (0x20, 0x10, 0x08, 0x04, 0x02),  # 47 '/'
    (0x3E, 0x51, 0x49, 0x45, 0x3E),  # 48 '0'
    (0x00, 0x42, 0x7F, 0x40, 0x00),  # 49 '1'
    (0x42, 0x61, 0x51, 0x49, 0x46),  # 50 '2'
    (0x21, 0x41, 0x45, 0x4B, 0x31),  # 51 '3'
    (0x18, 0x14, 0x12, 0x7F, 0x10),  # 52 '4'
    (0x27, 0x45, 0x45, 0x45, 0x39),  # 53 '5'
    (0x3C, 0x4A, 0x49, 0x49, 0x30),  # 54 '6'
    (0x01, 0x71, 0x09, 0x05, 0x03),  # 55 '7'
    (0x36, 0x49, 0x49, 0x49, 0x36),  # 56 '8'
    (0x06, 0x49, 0x49, 0x29, 0x1E),  # 57 '9'
    (0x00, 0x36, 0x36, 0x00, 0x00),  # 58 ':'
    (0x00, 0x56, 0x36, 0x00, 0x00),  # 59 ';'
    (0x08, 0x14, 0x22, 0x41, 0x00),  # 60 '<'
    (0x14, 0x14, 0x14, 0x14, 0x14),  # 61 '='
    (0x00, 0x41, 0x22, 0x14, 0x08),  # 62 '>'
    (0x02, 0x01, 0x51, 0x09, 0x06),  # 63 '?'
    (0x32, 0x49, 0x79, 0x41, 0x3E),  # 64 '@'
    (0x7E, 0x11, 0x11, 0x11, 0x7E),  # 65 'A'
    (0x7F, 0x49, 0x49, 0x49, 0x36),  # 66 'B'
    (0x3E, 0x41, 0x41, 0x41, 0x22),  # 67 'C'
    (0x7F, 0x41, 0x41, 0x22, 0x1C),  # 68 'D'
    (0x7F, 0x49, 0x49, 0x49, 0x41),  # 69 'E'
    (0x7F, 0x09, 0x09, 0x09, 0x01),  # 70 'F'
    (0x3E, 0x41, 0x49, 0x49, 0x7A),  # 71 'G'
    (0x7F, 0x08, 0x08, 0x08, 0x7F),  # 72 'H'
    (0x00, 0x41, 0x7F, 0x41, 0x00),  # 73 'I'
    (0x20, 0x40, 0x41, 0x3F, 0x01),  # 74 'J'
    (0x7F, 0x08, 0x14, 0x22, 0x41),  # 75 'K'
    (0x7F, 0x40, 0x40, 0x40, 0x40),  # 76 'L'
    (0x7F, 0x02, 0x0C, 0x02, 0x7F),  # 77 'M'
    (0x7F, 0x04, 0x08, 0x10, 0x7F),  # 78 'N'
    (0x3E, 0x41, 0x41, 0x41, 0x3E),  # 79 'O'
    (0x7F, 0x09, 0x09, 0x09, 0x06),  # 80 'P'
    (0x3E, 0x41, 0x51, 0x21, 0x5E),  # 81 'Q'
    (0x7F, 0x09, 0x19, 0x29, 0x46),  # 82 'R'
    (0x46, 0x49, 0x49, 0x49, 0x31),  # 83 'S'
    (0x01, 0x01, 0x7F, 0x01, 0x01),  # 84 'T'
    (0x3F, 0x40, 0x40, 0x40, 0x3F),  # 85 'U'
    (0x1F, 0x20, 0x40, 0x20, 0x1F),  # 86 'V'
    (0x3F, 0x40, 0x38, 0x40, 0x3F),  # 87 'W'
    (0x63, 0x14, 0x08, 0x14, 0x63),  # 88 'X'
    (0x07, 0x08, 0x70, 0x08, 0x07),  # 89 'Y'
    (0x61, 0x51, 0x49, 0x45, 0x43),  # 90 'Z'
    (0x00, 0x7F, 0x41, 0x41, 0x00),  # 91 '['
    (0x02, 0x04, 0x08, 0x10, 0x20),  # 92 '\'
    (0x00, 0x41, 0x41, 0x7F, 0x00),  # 93 ']'
    (0x04, 0x02, 0x01, 0x02, 0x04),  # 94 '^'
    (0x40, 0x40, 0x40, 0x40, 0x40),  # 95 '_'
    (0x00, 0x01, 0x02, 0x04, 0x00),  # 96 '`'
    (0x20, 0x54, 0x54, 0x54, 0x78),  # 97 'a'
    (0x7F, 0x48, 0x44, 0x44, 0x38),  # 98 'b'
    (0x38, 0x44, 0x44, 0x44, 0x20),  # 99 'c'
    (0x38, 0x44, 0x44, 0x48, 0x7F),  # 100 'd'
    (0x38, 0x54, 0x54, 0x54, 0x18),  # 101 'e'
    (0x08, 0x7E, 0x09, 0x01, 0x02),  # 102 'f'
    (0x0C, 0x52, 0x52, 0x52, 0x3E),  # 103 'g'
    (0x7F, 0x08, 0x04, 0x04, 0x78),  # 104 'h'
    (0x00, 0x44, 0x7D, 0x40, 0x00),  # 105 'i'
    (0x20, 0x40, 0x44, 0x3D, 0x00),  # 106 'j'
    (0x7F, 0x10, 0x28, 0x44, 0x00),  # 107 'k'
    (0x00, 0x41, 0x7F, 0x40, 0x00),  # 108 'l'
    (0x7C, 0x04, 0x18, 0x04, 0x78),  # 109 'm'
    (0x7C, 0x08, 0x04, 0x04, 0x78),  # 110 'n'
    (0x38, 0x44, 0x44, 0x44, 0x38),  # 111 'o'
    (0x7C, 0x14, 0x14, 0x14, 0x08),  # 112 'p'
    (0x08, 0x14, 0x14, 0x18, 0x7C),  # 113 'q'
    (0x7C, 0x08, 0x04, 0x04, 0x08),  # 114 'r'
    (0x48, 0x54, 0x54, 0x54, 0x20),  # 115 's'
    (0x04, 0x3F, 0x44, 0x40, 0x20),  # 116 't'
    (0x3C, 0x40, 0x40, 0x20, 0x7C),  # 117 'u'
    (0x1C, 0x20, 0x40, 0x20, 0x1C),  # 118 'v'
    (0x3C, 0x40, 0x30, 0x40, 0x3C),  # 119 'w'
    (0x44, 0x28, 0x10, 0x28, 0x44),  # 120 'x'
    (0x0C, 0x50, 0x50, 0x50, 0x3C),  # 121 'y'
    (0x44, 0x64, 0x54, 0x4C, 0x44),  # 122 'z'
    (0x00, 0x08, 0x36, 0x41, 0x00),  # 123 '{'
    (0x00, 0x00, 0x7F, 0x00, 0x00),  # 124 '|'
    (0x00, 0x41, 0x36, 0x08, 0x00),  # 125 '}'
    (0x10, 0x08, 0x08, 0x10, 0x08),  # 126 '~'
]


class SSD1306GFX:
    """Graphics context for SSD1306 OLED displays."""

    def __init__(self, display: Any) -> None:
        self.display = display
        self.width: int = getattr(display, "WIDTH", 128)
        self.height: int = getattr(display, "HEIGHT", 64)

    def draw_pixel(self, x: int, y: int, color: int = 1) -> None:
        """Plot a single pixel."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.display.set_pixel(x, y, on=bool(color))

    def get_pixel(self, x: int, y: int, raw: bool = True) -> int:
        """Read a single pixel value (0 or 1)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            try:
                return 1 if self.display.get_pixel(x, y, raw=raw) else 0
            except TypeError:
                return 1 if self.display.get_pixel(x, y) else 0
        return 0


    def draw_fast_h_line(self, x: int, y: int, w: int, color: int = 1) -> None:
        """Draw a fast horizontal line."""
        if y < 0 or y >= self.height:
            return
        x0 = max(0, x)
        x1 = min(self.width, x + w)
        for px in range(x0, x1):
            self.display.set_pixel(px, y, on=bool(color))

    def draw_fast_v_line(self, x: int, y: int, h: int, color: int = 1) -> None:
        """Draw a fast vertical line."""
        if x < 0 or x >= self.width:
            return
        y0 = max(0, y)
        y1 = min(self.height, y + h)
        for py in range(y0, y1):
            self.display.set_pixel(x, py, on=bool(color))

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: int = 1) -> None:
        """Draw a line using Bresenham's algorithm."""
        steep = abs(y1 - y0) > abs(x1 - x0)
        if steep:
            x0, y0 = y0, x0
            x1, y1 = y1, x1

        if x0 > x1:
            x0, x1 = x1, x0
            y0, y1 = y1, y0

        dx = x1 - x0
        dy = abs(y1 - y0)
        err = dx // 2
        ystep = 1 if y0 < y1 else -1
        y = y0

        for x in range(x0, x1 + 1):
            if steep:
                self.draw_pixel(y, x, color)
            else:
                self.draw_pixel(x, y, color)
            err -= dy
            if err < 0:
                y += ystep
                err += dx

    def draw_rect(self, x: int, y: int, w: int, h: int, color: int = 1) -> None:
        """Draw a rectangle outline."""
        if w <= 0 or h <= 0:
            return
        self.draw_fast_h_line(x, y, w, color)
        self.draw_fast_h_line(x, y + h - 1, w, color)
        self.draw_fast_v_line(x, y, h, color)
        self.draw_fast_v_line(x + w - 1, y, h, color)

    def fill_rect(self, x: int, y: int, w: int, h: int, color: int = 1) -> None:
        """Draw a filled rectangle."""
        if w <= 0 or h <= 0:
            return
        y0 = max(0, y)
        y1 = min(self.height, y + h)
        for py in range(y0, y1):
            self.draw_fast_h_line(x, py, w, color)

    def draw_circle(self, x0: int, y0: int, r: int, color: int = 1) -> None:
        """Draw a circle outline using midpoint circle algorithm."""
        f = 1 - r
        dd_f_x = 1
        dd_f_y = -2 * r
        x = 0
        y = r

        self.draw_pixel(x0, y0 + r, color)
        self.draw_pixel(x0, y0 - r, color)
        self.draw_pixel(x0 + r, y0, color)
        self.draw_pixel(x0 - r, y0, color)

        while x < y:
            if f >= 0:
                y -= 1
                dd_f_y += 2
                f += dd_f_y
            x += 1
            dd_f_x += 2
            f += dd_f_x

            self.draw_pixel(x0 + x, y0 + y, color)
            self.draw_pixel(x0 - x, y0 + y, color)
            self.draw_pixel(x0 + x, y0 - y, color)
            self.draw_pixel(x0 - x, y0 - y, color)
            self.draw_pixel(x0 + y, y0 + x, color)
            self.draw_pixel(x0 - y, y0 + x, color)
            self.draw_pixel(x0 + y, y0 - x, color)
            self.draw_pixel(x0 - y, y0 - x, color)

    def fill_circle(self, x0: int, y0: int, r: int, color: int = 1) -> None:
        """Draw a filled circle."""
        self.draw_fast_v_line(x0, y0 - r, 2 * r + 1, color)
        f = 1 - r
        dd_f_x = 1
        dd_f_y = -2 * r
        x = 0
        y = r

        while x < y:
            if f >= 0:
                y -= 1
                dd_f_y += 2
                f += dd_f_y
            x += 1
            dd_f_x += 2
            f += dd_f_x

            self.draw_fast_v_line(x0 + x, y0 - y, 2 * y + 1, color)
            self.draw_fast_v_line(x0 - x, y0 - y, 2 * y + 1, color)
            self.draw_fast_v_line(x0 + y, y0 - x, 2 * x + 1, color)
            self.draw_fast_v_line(x0 - y, y0 - x, 2 * x + 1, color)

    def draw_triangle(
        self, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int, color: int = 1
    ) -> None:
        """Draw a triangle outline."""
        self.draw_line(x0, y0, x1, y1, color)
        self.draw_line(x1, y1, x2, y2, color)
        self.draw_line(x2, y2, x0, y0, color)

    def fill_triangle(
        self, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int, color: int = 1
    ) -> None:
        """Draw a filled triangle using scanline rasterization."""
        # Sort coordinates by y ascending (y0 <= y1 <= y2)
        if y0 > y1:
            y0, y1 = y1, y0
            x0, x1 = x1, x0
        if y1 > y2:
            y2, y1 = y1, y2
            x2, x1 = x1, x2
        if y0 > y1:
            y0, y1 = y1, y0
            x0, x1 = x1, x0

        if y0 == y2:  # Flat line
            a = min(x0, min(x1, x2))
            b = max(x0, max(x1, x2))
            self.draw_fast_h_line(a, y0, b - a + 1, color)
            return

        dx01 = x1 - x0
        dy01 = y1 - y0
        dx02 = x2 - x0
        dy02 = y2 - y0
        dx12 = x2 - x1
        dy12 = y2 - y1

        sa = 0
        sb = 0

        last_y = y1 if y1 == y2 else y1 - 1
        for y in range(y0, last_y + 1):
            a = x0 + (sa // dy01) if dy01 != 0 else x0
            b = x0 + (sb // dy02) if dy02 != 0 else x0
            sa += dx01
            sb += dx02
            if a > b:
                a, b = b, a
            self.draw_fast_h_line(a, y, b - a + 1, color)

        sa = dx12 * (y - y1)
        sb = dx02 * (y - y0)
        for y in range(y1, y2 + 1):
            a = x1 + (sa // dy12) if dy12 != 0 else x1
            b = x0 + (sb // dy02) if dy02 != 0 else x0
            sa += dx12
            sb += dx02
            if a > b:
                a, b = b, a
            self.draw_fast_h_line(a, y, b - a + 1, color)

    def draw_round_rect(
        self, x: int, y: int, w: int, h: int, r: int, color: int = 1
    ) -> None:
        """Draw a rectangle with rounded corners."""
        if w < 2 * r or h < 2 * r or r <= 0:
            self.draw_rect(x, y, w, h, color)
            return
        self.draw_fast_h_line(x + r, y, w - 2 * r, color)
        self.draw_fast_h_line(x + r, y + h - 1, w - 2 * r, color)
        self.draw_fast_v_line(x, y + r, h - 2 * r, color)
        self.draw_fast_v_line(x + w - 1, y + r, h - 2 * r, color)

        # Draw 4 corner arcs
        f = 1 - r
        dd_f_x = 1
        dd_f_y = -2 * r
        cx = 0
        cy = r
        while cx < cy:
            if f >= 0:
                cy -= 1
                dd_f_y += 2
                f += dd_f_y
            cx += 1
            dd_f_x += 2
            f += dd_f_x

            # Top-right
            self.draw_pixel(x + w - r - 1 + cx, y + r - cy, color)
            self.draw_pixel(x + w - r - 1 + cy, y + r - cx, color)
            # Bottom-right
            self.draw_pixel(x + w - r - 1 + cx, y + h - r - 1 + cy, color)
            self.draw_pixel(x + w - r - 1 + cy, y + h - r - 1 + cx, color)
            # Bottom-left
            self.draw_pixel(x + r - cx, y + h - r - 1 + cy, color)
            self.draw_pixel(x + r - cy, y + h - r - 1 + cx, color)
            # Top-left
            self.draw_pixel(x + r - cx, y + r - cy, color)
            self.draw_pixel(x + r - cy, y + r - cx, color)

    def draw_char(
        self,
        x: int,
        y: int,
        c: str,
        color: int = 1,
        bg: Optional[int] = None,
        size: int = 1,
    ) -> int:
        """Render a single ASCII character (5x7) at (x, y) with scaling.

        Returns total width consumed in pixels including 1px spacing.
        """
        code = ord(c)
        if code < 32 or code > 126:
            code = 32  # Default to space
        glyph = FONT_5X7[code - 32]

        for col_idx in range(5):
            col_byte = glyph[col_idx]
            for row_idx in range(8):
                is_on = bool((col_byte >> row_idx) & 1) if row_idx < 7 else False
                pixel_color = color if is_on else bg
                if pixel_color is not None:
                    if size == 1:
                        self.draw_pixel(x + col_idx, y + row_idx, pixel_color)
                    else:
                        self.fill_rect(
                            x + col_idx * size, y + row_idx * size, size, size, pixel_color
                        )

        # 1-pixel gap after character
        if bg is not None:
            if size == 1:
                self.draw_fast_v_line(x + 5, y, 8, bg)
            else:
                self.fill_rect(x + 5 * size, y, size, 8 * size, bg)

        return 6 * size

    def draw_string(
        self,
        x: int,
        y: int,
        text: str,
        color: int = 1,
        bg: Optional[int] = None,
        size: int = 1,
        wrap: bool = True,
    ) -> Tuple[int, int]:
        """Render multi-line text string with automatic wrapping.

        Returns final (cursor_x, cursor_y) position.
        """
        cursor_x = x
        cursor_y = y
        char_w = 6 * size
        char_h = 8 * size

        for char in text:
            if char == "\n":
                cursor_x = x
                cursor_y += char_h
                continue
            if char == "\r":
                cursor_x = x
                continue

            if wrap and (cursor_x + char_w > self.width):
                cursor_x = x
                cursor_y += char_h

            self.draw_char(cursor_x, cursor_y, char, color=color, bg=bg, size=size)
            cursor_x += char_w

        return cursor_x, cursor_y

    def draw_bitmap(
        self,
        x: int,
        y: int,
        bitmap: Sequence[int],
        w: int,
        h: int,
        color: int = 1,
        bg: Optional[int] = None,
    ) -> None:
        """Render monochrome 1-bit bitmap array (horizontal byte rows)."""
        bytes_per_row = (w + 7) // 8
        for row in range(h):
            for col in range(w):
                byte_idx = row * bytes_per_row + (col // 8)
                if byte_idx < len(bitmap):
                    b = bitmap[byte_idx]
                    bit = 7 - (col % 8)
                    on = bool((b >> bit) & 1)
                    p_color = color if on else bg
                    if p_color is not None:
                        self.draw_pixel(x + col, y + row, p_color)
