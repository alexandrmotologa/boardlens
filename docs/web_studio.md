# BoardLens Web Studio

The Web Studio is a browser-based instrumentation workbench for interacting with the simulated microcontroller in real time.

## Starting the Server

```bash
boardlens studio --port 8000
```

Open `http://localhost:8000` in any modern web browser.

## Studio Components

1. **Top Control Bar**:
   - Status indicators: clock cycles executed, program counter, and running/halted state.
   - Example selector: quickly load Blinky, UART Hello World, Fibonacci, or OLED display test.
   - Simulation controls: Run, Single Step, Pause, and Reset.

2. **Program Disassembly**:
   - Inspect instructions in Flash memory.
   - Highlights the instruction currently addressed by the Program Counter.

3. **SSD1306 OLED Display (128x64)**:
   - Emulates an organic light-emitting diode screen connected via I2C.
   - Displays real-time pixels written to the virtual GDDRAM buffer.

4. **UART0 Serial Terminal**:
   - Full-duplex interactive terminal emulator.
   - Shows streaming console text from firmware.
   - Allows typing input strings and sending them to the receiver FIFO queue.

5. **GPIO Port A Breadboard**:
   - 16 digital I/O pins (PA0 to PA15).
   - LED indicators show current output state.
   - Toggle buttons simulate pushbuttons to drive external input signals.

6. **CPU Register Bank**:
   - Displays registers x0 through x31 with standard ABI names (ra, sp, t0-t6, s0-s11, a0-a7).
   - Shows hexadecimal and signed decimal representations.

7. **SRAM Memory Inspector**:
   - Hexadecimal viewer with ASCII representation for SRAM starting at address `0x20000000`.

## WebSocket Telemetry Protocol

Connect to `ws://localhost:8000/ws` for real-time bi-directional streaming:

### Client Commands (JSON)
```json
{ "action": "step" }
{ "action": "run", "cycles": 1000 }
{ "action": "reset" }
{ "action": "pin", "pin": 5, "high": true }
{ "action": "uart", "data": "echo test\n" }
```

### Server Telemetry Stream (JSON)
```json
{
  "status": {
    "pc": "0x00000010",
    "cycles": 1420,
    "halted": false,
    "registers": { ... },
    "gpio": { ... }
  },
  "uart_tx": "Hello!\n",
  "oled_pixels": [ [0, 0, 1, ...], ... ]
}
```
