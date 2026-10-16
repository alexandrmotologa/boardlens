"""FastAPI backend application for BoardLens Web Studio."""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from boardlens import __version__
from boardlens.board import Board
from boardlens.examples import BLINKY_ASM, EXAMPLES
from boardlens.tooling.disassembler import disassemble_bytes

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="BoardLens Studio API",
    description="Live telemetry and control API for BoardLens virtual microcontroller",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global active board instance
board = Board(core="rv32i")
board.load_flash(BLINKY_ASM)


class LoadRequest(BaseModel):
    source: Optional[str] = None
    example: Optional[str] = None


class PinInputRequest(BaseModel):
    pin: int = Field(..., ge=0, le=15)
    high: bool


class UartSendRequest(BaseModel):
    data: str


class RunRequest(BaseModel):
    cycles: int = Field(default=1000, ge=1, le=1000000)


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Studio frontend not found.")
    return FileResponse(index_path)


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """Retrieve full board telemetry snapshot."""
    return board.get_status()


@app.post("/api/step")
async def step_board() -> Dict[str, Any]:
    """Execute one instruction step."""
    res = board.step()
    return {
        "step": {
            "pc": f"0x{res.pc:08X}",
            "mnemonic": res.mnemonic,
            "cycles": res.cycles,
            "trap": res.trap.name if res.trap else None,
        },
        "status": board.get_status(),
    }


@app.post("/api/run")
async def run_board(req: RunRequest) -> Dict[str, Any]:
    """Execute instructions up to cycle limit."""
    res = board.run(max_cycles=board.cycles + req.cycles)
    return {
        "halted_by": res.trap.name if res.trap else "CYCLE_LIMIT",
        "last_instruction": res.mnemonic,
        "status": board.get_status(),
    }


@app.post("/api/reset")
async def reset_board() -> Dict[str, Any]:
    """Reset board to initial loaded state."""
    board.reset()
    return board.get_status()


@app.post("/api/load")
async def load_firmware(req: LoadRequest) -> Dict[str, Any]:
    """Load new firmware from assembly source or pre-built example."""
    if req.example:
        if req.example not in EXAMPLES:
            raise HTTPException(status_code=400, detail=f"Unknown example '{req.example}'")
        source = EXAMPLES[req.example]
    elif req.source:
        source = req.source
    else:
        raise HTTPException(status_code=400, detail="Must provide either 'example' or 'source'")

    try:
        board.load_flash(source)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Assembly error: {exc}")

    return {
        "message": "Firmware loaded successfully",
        "status": board.get_status(),
    }


@app.get("/api/examples")
async def get_examples() -> Dict[str, str]:
    """List all available example firmwares."""
    return EXAMPLES


@app.get("/api/disassembly")
async def get_disassembly() -> List[Dict[str, Any]]:
    """Return disassembled instructions for the loaded Flash memory image."""
    records = disassemble_bytes(board.loaded_image, base_address=board.FLASH_BASE)
    current_pc = board.cpu.pc
    return [
        {
            "address": f"0x{addr:08X}",
            "raw": f"0x{raw:08X}",
            "mnemonic": text,
            "is_current": (addr == current_pc),
        }
        for addr, raw, text in records
    ]


@app.get("/api/memory")
async def get_memory(address: int = 0x20000000, length: int = 256) -> Dict[str, Any]:
    """Read a memory region slice with hex and ASCII formatting."""
    length = min(length, 1024)
    data: List[Dict[str, Any]] = []

    for offset in range(0, length, 16):
        row_addr = address + offset
        row_bytes: List[int] = []
        ascii_chars: List[str] = []
        for i in range(16):
            target = row_addr + i
            try:
                b = board.bus.read8(target)
            except Exception:
                b = 0
            row_bytes.append(b)
            ascii_chars.append(chr(b) if 32 <= b <= 126 else ".")

        data.append({
            "address": f"0x{row_addr:08X}",
            "hex": " ".join(f"{b:02X}" for b in row_bytes),
            "ascii": "".join(ascii_chars),
        })

    return {"rows": data}


@app.post("/api/gpio/input")
async def set_gpio_input(req: PinInputRequest) -> Dict[str, Any]:
    """Externally drive a GPIO pin state."""
    board.gpio.set_pin_input(req.pin, req.high)
    return {"pin": req.pin, "state": req.high, "status": board.get_status()}


@app.post("/api/uart/send")
async def send_uart_data(req: UartSendRequest) -> Dict[str, Any]:
    """Inject string into UART receiver FIFO."""
    board.uart.write_to_rx(req.data)
    return {"queued_bytes": len(req.data)}


@app.get("/api/uart/read")
async def read_uart_output() -> Dict[str, str]:
    """Read accumulated UART TX console output."""
    output = board.uart.read_tx_string()
    return {"output": output}


@app.get("/api/oled/pixels")
async def get_oled_pixels() -> List[List[int]]:
    """Return 64x128 pixel matrix of SSD1306 OLED."""
    return board.oled.to_pixel_matrix()


@app.websocket("/ws")
async def websocket_telemetry(ws: WebSocket):
    """Bidirectional WebSocket connection for live studio telemetry."""
    await ws.accept()
    try:
        while True:
            # Check for client messages with timeout to allow continuous periodic push
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=0.1)
                cmd = data.get("action")
                if cmd == "step":
                    board.step()
                elif cmd == "run":
                    board.run(max_cycles=board.cycles + data.get("cycles", 1000))
                elif cmd == "reset":
                    board.reset()
                elif cmd == "pin":
                    board.gpio.set_pin_input(data.get("pin", 0), data.get("high", False))
                elif cmd == "uart":
                    board.uart.write_to_rx(data.get("data", ""))
            except asyncio.TimeoutError:
                pass

            # Send live telemetry snapshot
            payload = {
                "status": board.get_status(),
                "uart_tx": board.uart.read_tx_string(),
                "oled_pixels": board.oled.to_pixel_matrix(),
            }
            await ws.send_json(payload)
            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        pass


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
