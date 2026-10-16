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
    li   s1, 10            # '\n'
    sw   s1, 4(s0)
    ebreak
