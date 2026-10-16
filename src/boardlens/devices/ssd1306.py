"""Authentic SSD1306 128x64 OLED display controller emulation via I2C."""

from typing import Any, Callable, List, Optional
from boardlens.peripherals.i2c import I2CDevice


class SSD1306(I2CDevice):
    """SSD1306 128x64 monochrome OLED display attached to I2C bus."""

    WIDTH = 128
    HEIGHT = 64
    PAGES = 8

    # Addressing modes
    MODE_HORIZONTAL = 0
    MODE_VERTICAL = 1
    MODE_PAGE = 2

    def __init__(self, address: int = 0x3C) -> None:
        super().__init__(address)
        # 8 pages of 128 columns = 1024 bytes GDDRAM
        self._gddram = bytearray(self.PAGES * self.WIDTH)

        # Display state registers
        self.display_on: bool = False
        self.inverted: bool = False
        self.entire_display_on: bool = False
        self.contrast: int = 0x7F
        self.addressing_mode: int = self.MODE_PAGE
        self.start_line: int = 0
        self.segment_remap: bool = False
        self.com_scan_remap: bool = False

        # Current pointers
        self.current_page: int = 0
        self.current_column: int = 0
        self.column_start: int = 0
        self.column_end: int = 127
        self.page_start: int = 0
        self.page_end: int = 7

        # I2C Protocol state
        self._control_byte: Optional[int] = None
        self._is_data: bool = False
        self._pending_command: Optional[int] = None
        self._pending_bytes: List[int] = []

        # Change listeners
        self._frame_listeners: List[Callable[[], None]] = []
        self._gfx: Optional[Any] = None

    @property
    def gfx(self) -> Any:
        """Access 2D graphics primitives and 5x7 font engine for this display."""
        if self._gfx is None:
            from boardlens.devices.graphics import SSD1306GFX
            self._gfx = SSD1306GFX(self)
        return self._gfx

    def add_frame_listener(self, listener: Callable[[], None]) -> None:
        """Register a callback invoked when display memory changes."""
        self._frame_listeners.append(listener)

    def _notify_change(self) -> None:
        for listener in self._frame_listeners:
            listener()

    def on_start(self) -> None:
        self._control_byte = None
        self._is_data = False

    def on_address(self, address: int, is_read: bool) -> bool:
        return (address == self.address) and not is_read

    def on_read_byte(self) -> int:
        return 0

    def on_stop(self) -> None:
        self._control_byte = None
        self._notify_change()

    def on_write_byte(self, byte_val: int) -> bool:
        byte_val = byte_val & 0xFF

        if self._control_byte is None:
            # Control Byte: Co (bit 7), D/C# (bit 6)
            self._control_byte = byte_val
            self._is_data = bool(byte_val & 0x40)
            return True

        # Continuation check: if Co is 1, next byte will be another control byte
        is_co = bool(self._control_byte & 0x80)

        if self._is_data:
            self._write_gddram_byte(byte_val)
        else:
            self._handle_command_byte(byte_val)

        if is_co:
            self._control_byte = None

        return True

    def _write_gddram_byte(self, byte_val: int) -> None:
        """Store pixel column byte into GDDRAM according to current addressing mode."""
        if 0 <= self.current_page < self.PAGES and 0 <= self.current_column < self.WIDTH:
            idx = (self.current_page * self.WIDTH) + self.current_column
            self._gddram[idx] = byte_val

        # Advance address pointers
        if self.addressing_mode == self.MODE_PAGE:
            self.current_column += 1
            if self.current_column > self.column_end:
                self.current_column = self.column_start

        elif self.addressing_mode == self.MODE_HORIZONTAL:
            self.current_column += 1
            if self.current_column > self.column_end:
                self.current_column = self.column_start
                self.current_page += 1
                if self.current_page > self.page_end:
                    self.current_page = self.page_start

        elif self.addressing_mode == self.MODE_VERTICAL:
            self.current_page += 1
            if self.current_page > self.page_end:
                self.current_page = self.page_start
                self.current_column += 1
                if self.current_column > self.column_end:
                    self.current_column = self.column_start

    def _handle_command_byte(self, cmd: int) -> None:
        """Parse SSD1306 command byte and multi-byte command parameters."""
        if self._pending_command is not None:
            self._pending_bytes.append(cmd)
            # Check multi-byte completions
            pcmd = self._pending_command
            if pcmd in (0x20, 0x81, 0x8D, 0xA8, 0xD3, 0xD5, 0xD9, 0xDA, 0xDB):
                # 1 argument required
                val = self._pending_bytes[0]
                if pcmd == 0x20:
                    self.addressing_mode = val & 0x3
                elif pcmd == 0x81:
                    self.contrast = val
                self._pending_command = None
                self._pending_bytes.clear()
                return

            elif pcmd in (0x21, 0x22):
                # 2 arguments required
                if len(self._pending_bytes) >= 2:
                    start_val, end_val = self._pending_bytes[0], self._pending_bytes[1]
                    if pcmd == 0x21:
                        self.column_start = start_val & 0x7F
                        self.column_end = end_val & 0x7F
                        self.current_column = self.column_start
                    elif pcmd == 0x22:
                        self.page_start = start_val & 0x07
                        self.page_end = end_val & 0x07
                        self.current_page = self.page_start
                    self._pending_command = None
                    self._pending_bytes.clear()
                return

        # Single byte commands
        if 0x00 <= cmd <= 0x0F:
            self.current_column = (self.current_column & 0xF0) | (cmd & 0x0F)
        elif 0x10 <= cmd <= 0x1F:
            self.current_column = (self.current_column & 0x0F) | ((cmd & 0x0F) << 4)
        elif 0x40 <= cmd <= 0x7F:
            self.start_line = cmd & 0x3F
        elif 0xB0 <= cmd <= 0xB7:
            self.current_page = cmd & 0x07
        elif cmd == 0xA0:
            self.segment_remap = False
        elif cmd == 0xA1:
            self.segment_remap = True
        elif cmd == 0xA4:
            self.entire_display_on = False
        elif cmd == 0xA5:
            self.entire_display_on = True
        elif cmd == 0xA6:
            self.inverted = False
        elif cmd == 0xA7:
            self.inverted = True
        elif cmd == 0xAE:
            self.display_on = False
        elif cmd == 0xAF:
            self.display_on = True
        elif cmd == 0xC0:
            self.com_scan_remap = False
        elif cmd == 0xC8:
            self.com_scan_remap = True
        elif cmd in (0x20, 0x21, 0x22, 0x81, 0x8D, 0xA8, 0xD3, 0xD5, 0xD9, 0xDA, 0xDB):
            self._pending_command = cmd
            self._pending_bytes.clear()

    def get_pixel(self, x: int, y: int, raw: bool = False) -> bool:
        """Check if pixel at (x, y) is illuminated on screen (or set in GDDRAM if raw=True)."""
        if not (0 <= x < self.WIDTH and 0 <= y < self.HEIGHT):
            return False
        if not raw:
            if not self.display_on:
                return False
            if self.entire_display_on:
                return True

        page = y // 8
        bit = y % 8
        idx = (page * self.WIDTH) + x
        val = bool((self._gddram[idx] >> bit) & 1)

        return not val if (self.inverted and not raw) else val

    def set_pixel(self, x: int, y: int, on: bool = True) -> None:
        """Directly write a single pixel to GDDRAM."""
        if not (0 <= x < self.WIDTH and 0 <= y < self.HEIGHT):
            return
        page = y // 8
        bit = y % 8
        idx = (page * self.WIDTH) + x
        if on:
            self._gddram[idx] |= (1 << bit)
        else:
            self._gddram[idx] &= ~(1 << bit)

    def clear(self) -> None:
        """Clear the GDDRAM buffer."""
        self._gddram = bytearray(self.PAGES * self.WIDTH)
        self._notify_change()

    def to_pixel_matrix(self) -> List[List[int]]:
        """Export 64x128 binary pixel grid for web canvas."""
        matrix: List[List[int]] = []
        for y in range(self.HEIGHT):
            row = [1 if self.get_pixel(x, y) else 0 for x in range(self.WIDTH)]
            matrix.append(row)
        return matrix

    def render_ascii(self) -> str:
        """Render terminal ASCII preview of OLED display using unicode half-block characters."""
        lines: List[str] = []
        # Group 2 vertical pixels into half blocks: top is '▀', bottom is '▄', both is '█', neither is ' '
        for y in range(0, self.HEIGHT, 2):
            line_chars = []
            for x in range(self.WIDTH):
                top = self.get_pixel(x, y)
                bot = self.get_pixel(x, y + 1)
                if top and bot:
                    line_chars.append("█")
                elif top:
                    line_chars.append("▀")
                elif bot:
                    line_chars.append("▄")
                else:
                    line_chars.append(" ")
            lines.append("".join(line_chars))
        return "\n".join(lines)
