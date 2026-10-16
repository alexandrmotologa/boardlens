"""Built-in firmware examples for BoardLens."""

BLINKY_ASM = """
# Blinky LED on GPIOA Pin 5
.text
    # 1. Configure GPIOA Pin 5 as General Purpose Output
    # MODER base is 0x40000000, Pin 5 mode bits are 11:10 -> 01 = 0x400
    lui  t0, 0x40000
    li   t1, 0x00000400
    sw   t1, 0(t0)

    # 2. Toggle Pin 5 ON
    li   t2, 0x0020        # Bit 5 set (1 << 5)
    sw   t2, 24(t0)        # Write to BSRR (offset 24)

    # 3. Toggle Pin 5 OFF
    li   t3, 0x00200000    # Bit 21 reset (1 << (16 + 5))
    sw   t3, 24(t0)        # Write to BSRR

    # 4. Turn Pin 5 ON again and halt
    sw   t2, 24(t0)
    ebreak
"""

UART_HELLO_ASM = """
# UART Hello World transmitter
.text
    lui  s0, 0x40001       # UART0 base address (0x40001000)
    li   s1, 72            # 'H'
    sw   s1, 4(s0)         # write to DR (offset 4)
    li   s1, 101           # 'e'
    sw   s1, 4(s0)
    li   s1, 108           # 'l'
    sw   s1, 4(s0)
    sw   s1, 4(s0)         # 'l'
    li   s1, 111           # 'o'
    sw   s1, 4(s0)
    li   s1, 33            # '!'
    sw   s1, 4(s0)
    li   s1, 10            # '\\n'
    sw   s1, 4(s0)
    ebreak
"""

FIBONACCI_ASM = """
# Fibonacci generator saving numbers to SRAM
.text
    lui  s0, 0x20000       # SRAM base (0x20000000)
    li   t0, 0             # Fib(0)
    li   t1, 1             # Fib(1)
    li   t2, 10            # Count limit
    li   t3, 0             # Loop counter

    sw   t0, 0(s0)         # Save Fib(0)
    addi s0, s0, 4
    sw   t1, 0(s0)         # Save Fib(1)

loop:
    add  t4, t0, t1        # Fib(n) = Fib(n-1) + Fib(n-2)
    addi s0, s0, 4
    sw   t4, 0(s0)         # Save to SRAM
    mv   t0, t1
    mv   t1, t4
    addi t3, t3, 1
    blt  t3, t2, loop

    ebreak
"""

OLED_DEMO_ASM = """
# SSD1306 OLED initialization and pattern display via I2C0
.text
    lui  s0, 0x40003       # I2C0 base (0x40003000)

    # 1. Enable I2C: CR1 = PE (1)
    li   t0, 1
    sw   t0, 0(s0)

    # 2. START condition: CR1 = PE | START (1 | 0x100 = 0x101)
    li   t0, 0x101
    sw   t0, 0(s0)

    # 3. Send SSD1306 address + Write: 0x3C << 1 = 0x78
    li   t1, 0x78
    sw   t1, 12(s0)        # DR (offset 12)

    # Read SR2 to clear ADDR flag
    lw   zero, 20(s0)      # SR2 (offset 20)

    # 4. Send Control Byte: 0x00 (Command stream)
    li   t1, 0x00
    sw   t1, 12(s0)

    # 5. Command: Display ON (0xAF)
    li   t1, 0xAF
    sw   t1, 12(s0)

    # 6. STOP condition: CR1 = PE | STOP (1 | 0x200 = 0x201)
    li   t0, 0x201
    sw   t0, 0(s0)

    ebreak
"""

EXAMPLES = {
    "blinky": BLINKY_ASM,
    "uart_hello": UART_HELLO_ASM,
    "fibonacci": FIBONACCI_ASM,
    "oled_demo": OLED_DEMO_ASM,
}
