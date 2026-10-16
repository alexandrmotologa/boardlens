# SSD1306 OLED display initialization via simulated I2C0 bus
.text
    lui  s0, 0x40003       # I2C0 controller base (0x40003000)

    # 1. Enable peripheral: CR1 = PE (1)
    li   t0, 1
    sw   t0, 0(s0)

    # 2. Issue START condition: CR1 = PE | START (1 | 0x100 = 0x101)
    li   t0, 0x101
    sw   t0, 0(s0)

    # 3. Transmit SSD1306 7-bit address + Write bit: 0x3C << 1 = 0x78
    li   t1, 0x78
    sw   t1, 12(s0)        # Write to DR

    # Read SR2 to clear ADDR flag
    lw   zero, 20(s0)

    # 4. Transmit Control Byte: 0x00 (Command stream)
    li   t1, 0x00
    sw   t1, 12(s0)

    # 5. Send Command: Display ON (0xAF)
    li   t1, 0xAF
    sw   t1, 12(s0)

    # 6. Issue STOP condition: CR1 = PE | STOP (1 | 0x200 = 0x201)
    li   t0, 0x201
    sw   t0, 0(s0)

    ebreak
