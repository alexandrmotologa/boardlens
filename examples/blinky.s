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
