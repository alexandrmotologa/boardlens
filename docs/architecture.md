# BoardLens System Architecture

BoardLens is an instruction-level and bus-transaction-level simulator for embedded systems development. It models 32-bit microprocessor cores, physical memory maps, peripheral register state machines, and virtual hardware displays.

## Core Modules

### 1. Processor Cores (`boardlens.cpu`)
- **RV32ICore**: Simulates the standard 32-bit RISC-V integer base instruction set (37 base instructions, unprivileged machine mode, control and status registers).
- **ARMCortexMCore**: Simulates ARM Cortex-M0/M3 Thumb-1 16-bit instruction decoding, register bank with R0-R15, and xPSR condition flags (N, Z, C, V).
- **Registers**: Strict register file abstractions. For RV32I, register x0 is hardwired to zero, and write attempts are discarded.

### 2. Memory Interconnect (`boardlens.memory`)
- **MemoryBus**: Manages address decoding, bus arbitration, and bounds checking.
- Supports 8-bit byte, 16-bit halfword, and 32-bit word access in little-endian order.
- Generates BusFault exceptions on unmapped memory access, unaligned access (when strict alignment is enabled), and write attempts to read-only regions.
- Transaction listeners monitor bus traffic in real time for VCD tracing and logic analyzer export.

### 3. Memory-Mapped Peripherals (`boardlens.peripherals`)
- **GPIOPort**: 16-pin I/O port emulating standard microcontroller GPIO controllers (MODER, OTYPER, OSPEEDR, PUPDR, IDR, ODR, and BSRR atomic bit set/reset).
- **UARTPeripheral**: Full-duplex serial transceiver with transmit and receive FIFO buffers, baud rate divisor registers, and status flags (TXE, RXNE, TC).
- **SysTickTimer**: 24-bit down-counter with auto-reload value register, control/status flags, and periodic tick callbacks.
- **I2CController**: Master I2C bus controller state machine supporting START/STOP condition generation, 7-bit addressing, ACK/NACK handshakes, and multi-byte transfers.
- **ADCPeripheral**: 12-bit successive approximation analog-to-digital converter supporting 4 analog channels with configurable input millivolts, single and continuous conversion modes, EOC flag, and SWSTART software trigger.

### 4. Virtual Devices (`boardlens.devices`)
- **SSD1306**: 128x64 monochrome OLED display attached to I2C slave address 0x3C. Emulates 1024 bytes of Graphic Display Data RAM (GDDRAM), horizontal/vertical/page addressing modes, contrast control, and bitmap rendering.
- **SSD1306GFX**: 2D graphics primitive renderer and complete 5x7 ASCII bitmap font engine supporting lines, rectangles, rounded boxes, circles, triangles, text strings with word wrapping, and 1-bit monochrome bitmaps.

### 5. Tooling (`boardlens.tooling`)
- **Assembler**: Two-pass RV32I assembler supporting labels, constants, directives (.text, .data, .word, .byte), and common pseudo-instructions (li, mv, nop, j, ret, call, beqz, bnez).
- **Disassembler**: Formats raw 32-bit machine code into aligned instruction listings.
- **ELF32**: Binary parser extracting program segments (PT_LOAD), sections, and symbol tables (.symtab / .strtab) from compiled GCC/Clang embedded ELF binaries without external dependencies.
- **GDBServer**: Embedded GDB Remote Serial Protocol (RSP) stub server enabling source-level debugging with gdb-multiarch over TCP socket (registers, memory, breakpoints, single-step, continue).
- **VCDTracer**: Generates IEEE 1364-1995 standard Value Change Dump files for inspection in PulseView or GTKWave.

### 6. Interactive Web Studio (`boardlens.web`)
- FastAPI application serving real-time telemetry over WebSockets and REST endpoints.
- Browser-based code editor with hot assembling and flashing into the virtual MCU.
- 64-sample HTML5 canvas digital logic analyzer plotting CLK, PC, ADDR, WE, PA5, and UART TX.
- Real-time analog input sliders (CH0 to CH3) driving virtual ADC voltages.

