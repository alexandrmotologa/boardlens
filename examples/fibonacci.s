# Fibonacci sequence calculator saving values to SRAM
.text
    lui  s0, 0x20000       # SRAM base (0x20000000)
    li   t0, 0             # Fib(0)
    li   t1, 1             # Fib(1)
    li   t2, 10            # Iterations limit
    li   t3, 0             # Loop counter

    sw   t0, 0(s0)         # Save Fib(0)
    addi s0, s0, 4
    sw   t1, 0(s0)         # Save Fib(1)

loop:
    add  t4, t0, t1        # Fib(n) = Fib(n-1) + Fib(n-2)
    addi s0, s0, 4
    sw   t4, 0(s0)         # Store in SRAM
    mv   t0, t1
    mv   t1, t4
    addi t3, t3, 1
    blt  t3, t2, loop

    ebreak
