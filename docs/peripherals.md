# Peripheral Specifications

BoardLens maps hardware peripherals into the `0x40000000` address window. Each peripheral operates as a finite state machine responding to 32-bit register reads and writes.

## GPIO Port A (`0x40000000`)

Controls 16 digital pins (PA0 to PA15).

| Offset | Register | Reset Value | Access | Description |
|:---|:---|:---:|:---:|:---|
| `0x00` | MODER | `0x00000000` | R/W | Pin mode (2 bits per pin: 00=In, 01=Out, 10=Alt, 11=Analog) |
| `0x04` | OTYPER | `0x00000000` | R/W | Output type (0=Push-Pull, 1=Open-Drain) |
| `0x08` | OSPEEDR | `0x00000000` | R/W | Output slew rate |
| `0x0C` | PUPDR | `0x00000000` | R/W | Pull-up / pull-down configuration |
| `0x10` | IDR | `0x00000000` | R | Input data register (live pin state) |
| `0x14` | ODR | `0x00000000` | R/W | Output data register (driven pin levels) |
| `0x18` | BSRR | `0x00000000` | W | Atomic bit set (bits 0-15) and reset (bits 16-31) |

## UART0 (`0x40001000`)

Serial communication transceiver with 2048-byte FIFO queues.

| Offset | Register | Reset Value | Access | Description |
|:---|:---|:---:|:---:|:---|
| `0x00` | SR | `0x000000C0` | R | Status register (bit 7: TXE, bit 6: TC, bit 5: RXNE) |
| `0x04` | DR | `0x00000000` | R/W | Data register (transmits on write, receives on read) |
| `0x08` | BRR | `0x00000341` | R/W | Baud rate divisor register |
| `0x0C` | CR1 | `0x0000200C` | R/W | Control register 1 (UE, TE, RE, TXEIE, RXNEIE) |

## SysTick Timer (`0x40002000`)

24-bit down-counter with auto-reload.

| Offset | Register | Reset Value | Access | Description |
|:---|:---|:---:|:---:|:---|
| `0x00` | CSR | `0x00000000` | R/W | Control/Status (bit 0: ENABLE, bit 1: TICKINT, bit 16: COUNTFLAG) |
| `0x04` | RVR | `0x00FFFFFF` | R/W | Reload value register |
| `0x08` | CVR | `0x00000000` | R/W | Current value counter (writing reloads RVR) |

## I2C0 Controller (`0x40003000`)

Master serial bus controller.

| Offset | Register | Reset Value | Access | Description |
|:---|:---|:---:|:---:|:---|
| `0x00` | CR1 | `0x00000000` | R/W | Control 1 (bit 0: PE, bit 8: START, bit 9: STOP, bit 10: ACK) |
| `0x04` | CR2 | `0x00000010` | R/W | Peripheral clock frequency |
| `0x08` | OAR1 | `0x00004000` | R/W | Own address register |
| `0x0C` | DR | `0x00000000` | R/W | Serial data transfer register |
| `0x10` | SR1 | `0x00000080` | R | Status 1 (bit 0: SB, bit 1: ADDR, bit 2: BTF, bit 7: TXE) |
| `0x14` | SR2 | `0x00000000` | R | Status 2 (bit 0: MSL, bit 1: BUSY, bit 2: TRA) |
| `0x18` | CCR | `0x00000000` | R/W | Clock control register |

## SSD1306 Virtual OLED Display (`I2C Address 0x3C`)

Monochrome display controller with 128 columns and 64 rows (8 pages of 128 bytes).
The controller parses I2C control bytes with Co and D/C# flags, separating command instructions from pixel bitmap data.
