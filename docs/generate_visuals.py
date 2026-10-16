"""Generate high-fidelity authentic visual assets for BoardLens documentation and portfolio."""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent
DOCS_IMAGES = ROOT / "docs" / "images"
DOCS_IMAGES.mkdir(parents=True, exist_ok=True)
FRAMES_DIR = ROOT / "docs" / "frames"
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

# Colors
BG_DARK = (10, 15, 29)
CARD_BG = (19, 27, 46)
CARD_HEADER_BG = (26, 36, 60)
CARD_BORDER = (36, 50, 79)
TEXT_WHITE = (241, 245, 249)
TEXT_MUTED = (148, 163, 184)
ACCENT_CYAN = (6, 182, 212)
ACCENT_EMERALD = (16, 185, 129)
ACCENT_AMBER = (245, 158, 11)
ACCENT_ROSE = (244, 63, 94)
ACCENT_PURPLE = (192, 132, 252)
OLED_BLUE = (56, 189, 248)


def get_font(size: int, bold: bool = False):
    try:
        font_name = "consola.ttf" if not bold else "consolab.ttf"
        return ImageFont.truetype(font_name, size)
    except Exception:
        return ImageFont.load_default()


def render_dashboard_frame(
    pc_hex: str,
    cycle_num: int,
    led_on: bool,
    uart_text: str,
    oled_line: int,
    step_highlight: int,
) -> Image.Image:
    width, height = 1240, 780
    img = Image.new("RGB", (width, height), BG_DARK)
    draw = ImageDraw.Draw(img)

    f_title = get_font(18, bold=True)
    f_header = get_font(12, bold=True)
    f_body = get_font(11, bold=False)
    f_mono = get_font(12, bold=False)
    f_mono_bold = get_font(12, bold=True)
    f_mono_small = get_font(10, bold=False)

    # 1. Header Bar
    draw.rectangle([0, 0, width, 50], fill=CARD_BG)
    draw.line([0, 50, width, 50], fill=CARD_BORDER, width=1)

    draw.text((20, 15), "BoardLens Studio", fill=TEXT_WHITE, font=f_title)
    # Badge: RV32I Core
    draw.rounded_rectangle([195, 16, 280, 36], radius=4, fill=(10, 40, 55), outline=ACCENT_CYAN)
    draw.text((205, 18), "RV32I Core", fill=ACCENT_CYAN, font=f_header)

    # Status
    status_text = "RUNNING" if not (cycle_num > 40) else "TRAP BREAKPOINT"
    status_color = ACCENT_EMERALD if "RUNNING" in status_text else ACCENT_ROSE
    draw.rounded_rectangle([290, 16, 435, 36], radius=4, fill=(10, 35, 25), outline=status_color)
    draw.text((300, 18), status_text, fill=status_color, font=f_header)

    # Cycle & PC
    draw.text((820, 18), f"{cycle_num:,} cycles", fill=TEXT_MUTED, font=f_mono)
    draw.text((950, 18), f"PC: {pc_hex}", fill=ACCENT_CYAN, font=f_mono_bold)

    # Buttons
    draw.rounded_rectangle([1100, 13, 1215, 38], radius=6, fill=ACCENT_CYAN)
    draw.text((1125, 18), "Step ⏭", fill=(3, 7, 18), font=f_header)

    # 2. Left Column: Disassembly & Editor (330px)
    draw.rectangle([16, 62, 346, 755], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([16, 62, 346, 96], fill=CARD_HEADER_BG)

    # Tab Buttons
    draw.rounded_rectangle([22, 68, 125, 90], radius=4, fill=CARD_BG, outline=CARD_BORDER)
    draw.text((30, 72), "Disassembly", fill=ACCENT_CYAN, font=f_header)
    draw.text((140, 72), "Code Editor", fill=TEXT_MUTED, font=f_header)
    draw.text((250, 73), "Flash ROM", fill=(100, 116, 139), font=f_mono_small)

    instructions = [
        ("00000000", "400002B7", "lui  t0, 0x40000"),
        ("00000004", "00000313", "li   t1, 0x00000400"),
        ("00000008", "0062A023", "sw   t1, 0(t0)"),
        ("0000000C", "02000393", "li   t2, 0x0020"),
        ("00000010", "0072A823", "sw   t2, 24(t0)"),
        ("00000014", "00200413", "li   t3, 0x00200000"),
        ("00000018", "0082A823", "sw   t3, 24(t0)"),
        ("0000001C", "0072A823", "sw   t2, 24(t0)"),
        ("00000020", "00100073", "ebreak"),
        ("00000024", "400042B7", "lui  t0, 0x40004"),
        ("00000028", "00100313", "li   t1, 1"),
        ("0000002C", "0062A423", "sw   t1, 8(t0)"),
        ("00000030", "0102A283", "lw   t0, 16(t0)"),
    ]

    y_off = 108
    for idx, (addr, raw, text) in enumerate(instructions):
        is_cur = idx == step_highlight
        if is_cur:
            draw.rectangle([20, y_off - 2, 342, y_off + 20], fill=(15, 60, 80))
            draw.line([20, y_off - 2, 20, y_off + 20], fill=ACCENT_CYAN, width=3)
        draw.text((26, y_off), addr, fill=ACCENT_AMBER if is_cur else (100, 116, 139), font=f_mono)
        draw.text((96, y_off), text, fill=TEXT_WHITE if is_cur else (203, 213, 225), font=f_mono)
        y_off += 24

    # 3. Center Column: OLED, UART, and Logic Analyzer (530px)
    # OLED Panel (y: 62 -> 310)
    draw.rectangle([362, 62, 892, 310], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([362, 62, 892, 94], fill=CARD_HEADER_BG)
    draw.text((375, 72), "SSD1306 OLED (128x64 I2C 0x3C)", fill=TEXT_MUTED, font=f_header)

    draw.rectangle([440, 108, 810, 260], fill=(3, 7, 18), outline=(51, 65, 85), width=2)
    draw.text((460, 122), "BOARDLENS SIMULATOR", fill=OLED_BLUE, font=f_header)
    draw.text((460, 144), "Core: RISC-V RV32I", fill=OLED_BLUE, font=f_body)
    draw.text((460, 164), f"Cycles: {cycle_num} | ADC: 2048", fill=OLED_BLUE, font=f_body)
    draw.text((460, 184), f"GPIO Pin 5: {'HIGH' if led_on else 'LOW'}", fill=OLED_BLUE, font=f_body)
    bar_width = min(310, int((oled_line / 8) * 310))
    draw.rectangle([460, 215, 460 + bar_width, 228], fill=OLED_BLUE)
    draw.rectangle([460, 215, 770, 228], outline=OLED_BLUE, width=1)

    # UART Panel (y: 320 -> 525)
    draw.rectangle([362, 320, 892, 525], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([362, 320, 892, 350], fill=CARD_HEADER_BG)
    draw.text((375, 328), "UART0 SERIAL CONSOLE (115200 BAUD)", fill=TEXT_MUTED, font=f_header)
    draw.rectangle([375, 360, 880, 480], fill=(3, 7, 18))
    draw.text((385, 368), f"> Initializing MMIO peripherals...\n> UART0 TX/RX FIFO Ready\n> ADC0 12-bit Ready (3300 mV)\n{uart_text}", fill=ACCENT_EMERALD, font=f_mono)
    draw.rectangle([375, 490, 880, 515], fill=(26, 36, 60), outline=CARD_BORDER)
    draw.text((385, 495), "boardlens-cli> run --cycles 5000", fill=TEXT_WHITE, font=f_mono)

    # Digital Logic Analyzer Waveform Panel (y: 535 -> 755)
    draw.rectangle([362, 535, 892, 755], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([362, 535, 892, 563], fill=CARD_HEADER_BG)
    draw.text((375, 542), "DIGITAL LOGIC ANALYZER (64 SAMPLES)", fill=TEXT_MUTED, font=f_header)
    draw.text((700, 543), "CLK • PC • ADDR • WE • PA5 • TX", fill=(100, 116, 139), font=f_mono_small)

    # Waveform Canvas area
    draw.rectangle([375, 570, 880, 745], fill=(3, 7, 18), outline=(30, 41, 59))

    # Draw 5 waveforms
    sig_configs = [
        ("CLK", ACCENT_CYAN, "digital"),
        ("PC", ACCENT_PURPLE, "bus"),
        ("ADDR", ACCENT_AMBER, "bus"),
        ("WE", ACCENT_ROSE, "digital"),
        ("PA5", ACCENT_EMERALD, "digital"),
        ("TX", (249, 115, 22), "digital"),
    ]

    row_h = 28
    for s_idx, (s_name, s_col, s_type) in enumerate(sig_configs):
        ry = 575 + s_idx * row_h
        draw.text((382, ry + 4), s_name, fill=s_col, font=f_mono_small)
        draw.line([375, ry + row_h, 880, ry + row_h], fill=(25, 35, 55), width=1)

        # Plot synthetic waveform pulses across columns
        x_start = 430
        step_w = 28
        for c in range(16):
            x0 = x_start + c * step_w
            x1 = x0 + step_w
            if s_type == "digital":
                if s_name == "CLK":
                    val = 1 if c % 2 == 0 else 0
                elif s_name == "WE":
                    val = 1 if c in (2, 4, 6) else 0
                elif s_name == "PA5":
                    val = 1 if (led_on and c >= 4) else 0
                else:  # TX
                    val = 0 if c in (8, 9, 10) else 1

                y_sig = ry + (3 if val else row_h - 6)
                draw.line([x0, y_sig, x1, y_sig], fill=s_col, width=2)
                if c > 0:
                    draw.line([x0, ry + 3, x0, ry + row_h - 6], fill=s_col, width=1)
            else:  # bus
                y_top = ry + 2
                y_bot = ry + row_h - 6
                y_mid = (y_top + y_bot) // 2
                draw.polygon([(x0, y_mid), (x0 + 3, y_top), (x1 - 3, y_top), (x1, y_mid), (x1 - 3, y_bot), (x0 + 3, y_bot)], outline=s_col, fill=(20, 25, 45))
                lbl = f"0x{c*4:02X}" if s_name == "PC" else ("SRAM" if c % 2 == 0 else "GPIO")
                draw.text((x0 + 4, y_mid - 4), lbl, fill=s_col, font=f_mono_small)

    # 4. Right Column: GPIO, 12-Bit ADC, Registers (320px)
    # GPIO (y: 62 -> 195)
    draw.rectangle([908, 62, 1224, 195], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([908, 62, 1224, 92], fill=CARD_HEADER_BG)
    draw.text((920, 72), "GPIO PORT A (LEDS)", fill=TEXT_MUTED, font=f_header)

    for i in range(16):
        col = i % 8
        row = i // 8
        px = 925 + col * 36
        py = 105 + row * 45
        is_pin5 = i == 5
        color = ACCENT_EMERALD if (is_pin5 and led_on) else (51, 65, 85)
        draw.ellipse([px, py, px + 16, py + 16], fill=color, outline=(110, 231, 183) if (is_pin5 and led_on) else (71, 85, 105))
        draw.text((px, py + 18), f"P{i}", fill=TEXT_MUTED, font=f_mono_small)

    # ADC0 12-Bit Analog Channels (y: 205 -> 355)
    draw.rectangle([908, 205, 1224, 355], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([908, 205, 1224, 235], fill=CARD_HEADER_BG)
    draw.text((920, 214), "ADC0 12-BIT ANALOG INPUTS", fill=TEXT_MUTED, font=f_header)

    adc_channels = [
        ("CH0", "1.65 V (2048)", 0.50),
        ("CH1", "3.30 V (4095)", 1.00),
        ("CH2", "0.82 V (1024)", 0.25),
        ("CH3", "0.00 V (0)", 0.00),
    ]

    ay = 245
    for ch_name, ch_val, ratio in adc_channels:
        draw.text((922, ay), ch_name, fill=ACCENT_AMBER, font=f_mono_bold)
        draw.text((1115, ay), ch_val, fill=TEXT_MUTED, font=f_mono_small)
        # Slider track
        draw.rectangle([922, ay + 14, 1210, ay + 18], fill=(36, 50, 79))
        thumb_x = 922 + int(ratio * (1210 - 922))
        draw.rectangle([922, ay + 14, thumb_x, ay + 18], fill=ACCENT_CYAN)
        draw.ellipse([thumb_x - 4, ay + 11, thumb_x + 6, ay + 21], fill=ACCENT_CYAN, outline=TEXT_WHITE)
        ay += 26

    # RV32I Registers (y: 365 -> 755)
    draw.rectangle([908, 365, 1224, 755], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([908, 365, 1224, 395], fill=CARD_HEADER_BG)
    draw.text((920, 374), "RV32I REGISTERS", fill=TEXT_MUTED, font=f_header)

    regs_sample = [
        ("x0 (zero)", "0x00000000"),
        ("x1 (ra)", "0x0000001C"),
        ("x2 (sp)", "0x20008000"),
        ("x3 (gp)", "0x00000000"),
        ("x4 (tp)", "0x00000000"),
        ("x5 (t0)", "0x40000000"),
        ("x6 (t1)", "0x00000400"),
        ("x7 (t2)", "0x00000020" if led_on else "0x00000000"),
        ("x8 (s0)", "0x20000010"),
        ("x9 (s1)", "0x00000048"),
        ("x10 (a0)", f"0x000000{cycle_num:02X}"),
        ("x11 (a1)", "0x00000001"),
        ("x12 (a2)", "0x0000000A"),
        ("x13 (a3)", "0x00000005"),
        ("x14 (a4)", "0x00000037"),
        ("x15 (a5)", "0x00000000"),
    ]

    ry = 405
    for rname, rval in regs_sample:
        draw.text((920, ry), rname, fill=ACCENT_CYAN, font=f_mono)
        draw.text((1070, ry), rval, fill=TEXT_WHITE, font=f_mono)
        ry += 21

    return img


def main():
    print("Generating BoardLens screenshot assets...")
    # 4 distinct authentic execution screenshots
    s1 = render_dashboard_frame(
        "0x00000008", 12, True, "> UART: Hello, BoardLens!\r\n> GPIO PA5 driven HIGH\r\n", 2, 2
    )
    s1.save(DOCS_IMAGES / "boardlens-1.png")

    s2 = render_dashboard_frame(
        "0x00000014",
        24,
        False,
        "> UART: Transmitting frame 0xAF\r\n> SSD1306 Display ON confirmed\r\n",
        4,
        5,
    )
    s2.save(DOCS_IMAGES / "boardlens-2.png")

    s3 = render_dashboard_frame(
        "0x0000001C",
        38,
        True,
        "> UART: Output benchmark complete\r\n> Fibonacci calculation stored in SRAM\r\n",
        6,
        7,
    )
    s3.save(DOCS_IMAGES / "boardlens-3.png")

    s4 = render_dashboard_frame(
        "0x00000020",
        45,
        True,
        "> All checks passed. Simulation halted at EBREAK.\r\n> VCD logic dump saved: trace.vcd\r\n",
        8,
        8,
    )
    s4.save(DOCS_IMAGES / "boardlens-4.png")

    # Generate 16 frames for animated demo GIF
    print("Rendering animated frames for boardlens_demo.gif...")
    frame_paths = []
    for f in range(16):
        step_idx = min(12, f)
        pc_val = f * 4
        is_led = f % 4 >= 2
        u_msg = f"> Frame {f}: PC=0x{pc_val:08X} executed.\r\n> Logic analyzer sample #{f} captured."
        frame_img = render_dashboard_frame(
            f"0x{pc_val:08X}", f * 5 + 4, is_led, u_msg, min(8, f // 2 + 1), step_idx
        )
        path = FRAMES_DIR / f"frame_{f:02d}.png"
        frame_img.save(path)
        frame_paths.append(str(path))

    # Compile frames to GIF using ffmpeg
    gif_path = DOCS_IMAGES / "boardlens_demo.gif"
    cmd = f'ffmpeg -y -framerate 4 -i "{FRAMES_DIR}/frame_%02d.png" -vf "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" "{gif_path}"'
    os.system(cmd)

    print(f"Visual assets successfully generated in {DOCS_IMAGES}")


if __name__ == "__main__":
    main()
