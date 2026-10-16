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

2. **Program Disassembly & Code Editor Tabs**:
   - Disassembly tab: inspect instructions in Flash memory with active PC highlighting.
   - Code Editor tab: write and modify RV32I assembly programs directly in the browser and hot-flash them to the virtual microcontroller with instant symbol resolution.

3. **SSD1306 OLED Display (128x64)**:
   - Emulates an organic light-emitting diode screen connected via I2C.
   - Displays real-time pixels written to the virtual GDDRAM buffer.

4. **UART0 Serial Terminal**:
   - Full-duplex interactive terminal emulator.
   - Shows streaming console text from firmware.
   - Allows typing input strings and sending them to the receiver FIFO queue.

5. **Digital Logic Analyzer Waveform Viewer**:
   - Real-time 64-sample digital waveform canvas plotting synchronized logic traces.
   - Tracks CLK, PC, memory bus address (ADDR), Write Enable (WE), GPIO output (PA5), and UART transmission (TX).

6. **GPIO Port A Breadboard**:
   - 16 digital I/O pins (PA0 to PA15).
   - LED indicators show current output state.
   - Toggle buttons simulate pushbuttons to drive external input signals.

7. **ADC0 12-Bit Analog Input Sliders**:
   - 4 analog input channels (CH0 to CH3) with sliders adjustable from 0.00 V to 3.30 V (0 to 3300 mV).
   - Live digital readout showing millivolts, volts, and the raw 12-bit conversion value (0 to 4095).

8. **CPU Register Bank**:
   - Displays registers x0 through x31 with standard ABI names (ra, sp, t0-t6, s0-s11, a0-a7).
   - Shows hexadecimal and signed decimal representations.

9. **SRAM Memory Inspector**:
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
{ "action": "adc", "channel": 0, "millivolts": 1650 }
{ "action": "flash", "source": "addi x1, x0, 10\nebreak\n" }
```

### Server Telemetry Stream (JSON)
```json
{
  "status": { ... },
  "uart_tx": "...",
  "oled_pixels": [[ ... ]],
  "waveform": [
    { "cycle": 12, "pc": "0x00000008", "addr": "0x40000014", "we": 1, "pa5": 1, "tx": 1, "adc": 2048 }
  ]
}
```

