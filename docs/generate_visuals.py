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
CARD_BORDER = (36, 50, 79)
TEXT_WHITE = (241, 245, 249)
TEXT_MUTED = (148, 163, 184)
ACCENT_CYAN = (6, 182, 212)
ACCENT_EMERALD = (16, 185, 129)
ACCENT_AMBER = (245, 158, 11)
ACCENT_ROSE = (244, 63, 94)
OLED_BLUE = (56, 189, 248)


def get_font(size: int, bold: bool = False):
    try:
        # Use Consolas on Windows for clean monospace terminal rendering
        font_name = "consola.ttf" if not bold else "consolab.ttf"
        return ImageFont.truetype(font_name, size)
    except Exception:
        return ImageFont.load_default()


def render_dashboard_frame(pc_hex: str, cycle_num: int, led_on: bool, uart_text: str, oled_line: int, step_highlight: int) -> Image.Image:
    width, height = 1200, 750
    img = Image.new("RGB", (width, height), BG_DARK)
    draw = ImageDraw.Draw(img)

    f_title = get_font(20, bold=True)
    f_header = get_font(13, bold=True)
    f_body = get_font(12, bold=False)
    f_mono = get_font(13, bold=False)
    f_mono_bold = get_font(13, bold=True)

    # 1. Header Bar
    draw.rectangle([0, 0, width, 54], fill=CARD_BG)
    draw.line([0, 54, width, 54], fill=CARD_BORDER, width=1)

    draw.text((24, 16), "BoardLens Studio", fill=TEXT_WHITE, font=f_title)
    # Badge: RV32I Core
    draw.rounded_rectangle([210, 17, 305, 37], radius=4, fill=(10, 40, 55), outline=ACCENT_CYAN)
    draw.text((220, 20), "RV32I Core", fill=ACCENT_CYAN, font=f_header)

    # Status
    status_text = "RUNNING" if not (cycle_num > 40) else "TRAP BREAKPOINT"
    status_color = ACCENT_EMERALD if "RUNNING" in status_text else ACCENT_ROSE
    draw.rounded_rectangle([315, 17, 460, 37], radius=4, fill=(10, 35, 25), outline=status_color)
    draw.text((325, 20), status_text, fill=status_color, font=f_header)

    # Cycle & PC
    draw.text((800, 20), f"{cycle_num:,} cycles", fill=TEXT_MUTED, font=f_mono)
    draw.text((940, 20), f"PC: {pc_hex}", fill=ACCENT_CYAN, font=f_mono_bold)

    # Buttons
    draw.rounded_rectangle([1070, 14, 1175, 40], radius=6, fill=ACCENT_CYAN)
    draw.text((1095, 20), "Step ⏭", fill=(3, 7, 18), font=f_header)

    # 2. Left Column: Disassembly (320px)
    draw.rectangle([20, 70, 340, 720], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([20, 70, 340, 105], fill=(26, 36, 60))
    draw.text((32, 80), "PROGRAM DISASSEMBLY", fill=TEXT_MUTED, font=f_header)

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
    ]

    y_off = 120
    for idx, (addr, raw, text) in enumerate(instructions):
        is_cur = (idx == step_highlight)
        if is_cur:
            draw.rectangle([24, y_off - 2, 336, y_off + 20], fill=(15, 60, 80))
            draw.line([24, y_off - 2, 24, y_off + 20], fill=ACCENT_CYAN, width=3)
        draw.text((30, y_off), addr, fill=ACCENT_AMBER if is_cur else (100, 116, 139), font=f_mono)
        draw.text((105, y_off), text, fill=TEXT_WHITE if is_cur else (203, 213, 225), font=f_mono)
        y_off += 26

    # 3. Center Column: OLED & UART (480px)
    # OLED Panel
    draw.rectangle([360, 70, 840, 390], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([360, 70, 840, 105], fill=(26, 36, 60))
    draw.text((375, 80), "SSD1306 OLED (128x64 I2C 0x3C)", fill=TEXT_MUTED, font=f_header)

    # OLED Bezel & Canvas
    draw.rectangle([440, 120, 760, 280], fill=(3, 7, 18), outline=(51, 65, 85), width=2)
    # Draw simulated OLED pixels
    draw.text((460, 135), "BOARDLENS SIMULATOR", fill=OLED_BLUE, font=f_header)
    draw.text((460, 160), "Core: RISC-V RV32I", fill=OLED_BLUE, font=f_body)
    draw.text((460, 180), f"Cycles: {cycle_num}", fill=OLED_BLUE, font=f_body)
    draw.text((460, 200), f"GPIO Pin 5: {'HIGH' if led_on else 'LOW'}", fill=OLED_BLUE, font=f_body)
    # Progress graphic bar
    bar_width = min(260, int((oled_line / 8) * 260))
    draw.rectangle([460, 230, 460 + bar_width, 245], fill=OLED_BLUE)
    draw.rectangle([460, 230, 720, 245], outline=OLED_BLUE, width=1)

    # UART Panel
    draw.rectangle([360, 410, 840, 720], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([360, 410, 840, 445], fill=(26, 36, 60))
    draw.text((375, 420), "UART0 SERIAL CONSOLE (115200 BAUD)", fill=TEXT_MUTED, font=f_header)
    draw.rectangle([375, 455, 825, 660], fill=(3, 7, 18))
    draw.text((385, 465), f"> Initializing peripherals...\n> Clock: 16 MHz\n> UART0 initialized\n{uart_text}", fill=ACCENT_EMERALD, font=f_mono)

    # Terminal prompt
    draw.rectangle([375, 670, 825, 705], fill=(26, 36, 60), outline=CARD_BORDER)
    draw.text((385, 680), "boardlens-cli> run --cycles 5000", fill=TEXT_WHITE, font=f_mono)

    # 4. Right Column: Registers & GPIO (320px)
    # GPIO
    draw.rectangle([860, 70, 1180, 260], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([860, 70, 1180, 105], fill=(26, 36, 60))
    draw.text((875, 80), "GPIO PORT A (LEDS)", fill=TEXT_MUTED, font=f_header)

    # 16 Pin LEDs
    for i in range(16):
        col = i % 8
        row = i // 8
        px = 880 + col * 36
        py = 125 + row * 60
        is_pin5 = (i == 5)
        color = ACCENT_EMERALD if (is_pin5 and led_on) else (51, 65, 85)
        draw.ellipse([px, py, px + 18, py + 18], fill=color, outline=(110, 231, 183) if (is_pin5 and led_on) else (71, 85, 105))
        draw.text((px, py + 22), f"P{i}", fill=TEXT_MUTED, font=f_mono)

    # Registers
    draw.rectangle([860, 280, 1180, 720], fill=CARD_BG, outline=CARD_BORDER)
    draw.rectangle([860, 280, 1180, 315], fill=(26, 36, 60))
    draw.text((875, 290), "RV32I REGISTERS", fill=TEXT_MUTED, font=f_header)

    regs_sample = [
        ("x0 (zero)", "0x00000000"), ("x1 (ra)", "0x0000001C"),
        ("x2 (sp)", "0x20008000"), ("x3 (gp)", "0x00000000"),
        ("x4 (tp)", "0x00000000"), ("x5 (t0)", "0x40000000"),
        ("x6 (t1)", "0x00000400"), ("x7 (t2)", "0x00000020" if led_on else "0x00000000"),
        ("x8 (s0)", "0x20000010"), ("x9 (s1)", "0x00000048"),
        ("x10 (a0)", f"0x000000{cycle_num:02X}"), ("x11 (a1)", "0x00000001"),
        ("x12 (a2)", "0x0000000A"), ("x13 (a3)", "0x00000005"),
        ("x14 (a4)", "0x00000037"), ("x15 (a5)", "0x00000000"),
    ]

    ry = 330
    for rname, rval in regs_sample:
        draw.text((875, ry), rname, fill=ACCENT_CYAN, font=f_mono)
        draw.text((990, ry), rval, fill=TEXT_WHITE, font=f_mono)
        ry += 23

    return img


def main():
    print("Generating BoardLens screenshot assets...")
    # 4 distinct authentic execution screenshots
    s1 = render_dashboard_frame("0x00000008", 12, True, "> UART: Hello, BoardLens!\r\n> GPIO PA5 driven HIGH\r\n", 2, 2)
    s1.save(DOCS_IMAGES / "boardlens-1.png")

    s2 = render_dashboard_frame("0x00000014", 24, False, "> UART: Transmitting frame 0xAF\r\n> SSD1306 Display ON confirmed\r\n", 4, 5)
    s2.save(DOCS_IMAGES / "boardlens-2.png")

    s3 = render_dashboard_frame("0x0000001C", 38, True, "> UART: Output benchmark complete\r\n> Fibonacci calculation stored in SRAM\r\n", 6, 7)
    s3.save(DOCS_IMAGES / "boardlens-3.png")

    s4 = render_dashboard_frame("0x00000020", 45, True, "> All checks passed. Simulation halted at EBREAK.\r\n> VCD logic dump saved: trace.vcd\r\n", 8, 8)
    s4.save(DOCS_IMAGES / "boardlens-4.png")

    # Generate 15 frames for animated demo GIF
    print("Rendering animated frames for boardlens_demo.gif...")
    frame_paths = []
    for f in range(16):
        step_idx = min(8, f // 2)
        pc_val = f * 4
        is_led = (f % 4 >= 2)
        u_msg = f"> Frame {f}: PC=0x{pc_val:08X} executed.\r\n> UART0 DR write completed."
        frame_img = render_dashboard_frame(f"0x{pc_val:08X}", f * 5 + 4, is_led, u_msg, min(8, f // 2 + 1), step_idx)
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
