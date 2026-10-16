"""Command-line interface for BoardLens virtual microcontroller platform."""

from pathlib import Path
from typing import Optional
import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from boardlens import __version__
from boardlens.board import Board
from boardlens.cpu.base import TrapCause
from boardlens.peripherals.gpio import GPIOPort
from boardlens.tooling.assembler import assemble
from boardlens.tooling.disassembler import format_disassembly
from boardlens.tooling.gdb_server import GDBServer

app = typer.Typer(
    name="boardlens",
    help="Virtual microcontroller and hardware logic simulator for embedded systems engineers.",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold cyan]BoardLens[/bold cyan] version [bold green]{__version__}[/bold green]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show BoardLens version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    pass


@app.command()
def run(
    source_file: Path = typer.Argument(
        ...,
        help="Path to firmware file (.s, .asm, or raw .bin).",
        exists=True,
    ),
    core: str = typer.Option("rv32i", "--core", "-m", help="Processor core: rv32i or arm."),
    cycles: int = typer.Option(100000, "--cycles", "-c", help="Maximum execution cycle limit."),
    trace: Optional[Path] = typer.Option(None, "--trace", "-t", help="Export VCD waveform to file."),
) -> None:
    """Run a firmware binary or assembly source file in the virtual board."""
    board = Board(core=core, enable_vcd=bool(trace))

    # Read input file
    raw_content = source_file.read_bytes()
    suffix = source_file.suffix.lower()

    if suffix in (".s", ".asm", ".txt"):
        text = raw_content.decode("utf-8", errors="replace")
        try:
            board.load_flash(text)
        except Exception as exc:
            console.print(f"[bold red]Assembly error:[/bold red] {exc}")
            raise typer.Exit(code=1)
    else:
        board.load_flash(raw_content)

    console.print(f"[dim]Running {source_file.name} on {core.upper()} core (limit: {cycles} cycles)...[/dim]")

    result = board.run(max_cycles=cycles)

    # Print summary panel
    status_str = f"[bold green]TRAP {result.trap.name}[/bold green]" if result.trap else "[yellow]CYCLE LIMIT[/yellow]"
    console.print(
        Panel(
            f"Execution halted: {status_str}\n"
            f"Program Counter: [bold cyan]0x{board.cpu.pc:08X}[/bold cyan]\n"
            f"Cycles executed: [bold]{board.cycles}[/bold]",
            title="[bold]Simulation Results[/bold]",
            border_style="cyan",
        )
    )

    # UART stream if any
    uart_output = board.uart.read_tx_string()
    if uart_output:
        console.print("\n[bold]UART Output:[/bold]")
        console.print(Panel(uart_output, border_style="green"))

    # GPIO state table
    gpio_table = Table(title="GPIO Output Pins", show_header=True)
    gpio_table.add_column("Pin", style="cyan")
    gpio_table.add_column("Mode", style="magenta")
    gpio_table.add_column("Level", style="green")

    for i in range(8):
        mode_idx = board.gpio.get_pin_mode(i)
        mode_names = ["INPUT", "OUTPUT", "ALT", "ANALOG"]
        level = "HIGH (1)" if board.gpio.get_pin_output(i) else "LOW (0)"
        gpio_table.add_row(f"PA{i}", mode_names[mode_idx], level)

    console.print(gpio_table)

    # Export VCD if requested
    if trace and board.vcd:
        board.vcd.write_to_file(str(trace))
        console.print(f"[bold green]VCD waveform saved to {trace}[/bold green]")


@app.command()
def asm(
    source_file: Path = typer.Argument(..., help="Assembly source file (.s or .asm)", exists=True),
    output_file: Path = typer.Option(Path("firmware.bin"), "--output", "-o", help="Output binary file path"),
    base: str = typer.Option("0x00000000", "--base", "-b", help="Base flash origin address"),
) -> None:
    """Assemble RV32I source code into binary machine code."""
    try:
        base_addr = int(base, 16) if base.startswith("0x") else int(base)
    except ValueError:
        console.print(f"[bold red]Invalid base address:[/bold red] {base}")
        raise typer.Exit(code=1)

    text = source_file.read_text(encoding="utf-8")
    try:
        binary = assemble(text, base_address=base_addr)
    except Exception as exc:
        console.print(f"[bold red]Assembly failed:[/bold red] {exc}")
        raise typer.Exit(code=1)

    output_file.write_bytes(binary)
    console.print(
        f"[bold green]Successfully assembled[/bold green] {source_file.name} -> "
        f"[bold cyan]{output_file.name}[/bold cyan] ({len(binary)} bytes, {len(binary)//4} instructions)"
    )


@app.command()
def disasm(
    binary_file: Path = typer.Argument(..., help="Path to machine code binary", exists=True),
    base: str = typer.Option("0x00000000", "--base", "-b", help="Base memory address for listing"),
) -> None:
    """Disassemble binary machine code file into readable assembly."""
    try:
        base_addr = int(base, 16) if base.startswith("0x") else int(base)
    except ValueError:
        console.print(f"[bold red]Invalid base address:[/bold red] {base}")
        raise typer.Exit(code=1)

    data = binary_file.read_bytes()
    listing = format_disassembly(data, base_address=base_addr)
    console.print(listing)


@app.command()
def info() -> None:
    """Display virtual board memory map, peripheral addresses, and device specifications."""
    table = Table(title="BoardLens Memory Map", show_header=True)
    table.add_column("Start Address", style="cyan")
    table.add_column("End Address", style="cyan")
    table.add_column("Size", style="yellow")
    table.add_column("Region Name", style="magenta")
    table.add_column("Permissions", style="green")

    table.add_row("0x00000000", "0x0001FFFF", "128 KB", "Flash ROM", "R/X")
    table.add_row("0x20000000", "0x2000FFFF", "64 KB", "SRAM", "R/W")
    table.add_row("0x40000000", "0x400003FF", "1 KB", "GPIO Port A", "R/W")
    table.add_row("0x40001000", "0x400013FF", "1 KB", "UART0 Serial", "R/W")
    table.add_row("0x40002000", "0x400023FF", "1 KB", "SysTick Timer", "R/W")
    table.add_row("0x40003000", "0x400033FF", "1 KB", "I2C0 Controller", "R/W")
    table.add_row("0x40004000", "0x400043FF", "1 KB", "ADC0 12-bit Converter", "R/W")

    console.print(table)


@app.command(name="gdb-server")
def gdb_server_cmd(
    source_file: Optional[Path] = typer.Option(None, "--bin", "-b", help="Firmware file to pre-load (.bin, .elf, or .s)."),
    core: str = typer.Option("rv32i", "--core", "-m", help="Processor core: rv32i or arm."),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="GDB stub bind host."),
    port: int = typer.Option(3333, "--port", "-p", help="GDB stub TCP port."),
) -> None:
    """Run an authentic GDB Remote Serial Protocol (RSP) stub server."""
    board = Board(core=core)
    if source_file:
        data = source_file.read_bytes()
        board.load_flash(data)
        console.print(f"[bold green]Loaded firmware into flash:[/bold green] {source_file}")

    server = GDBServer(board, host=host, port=port)
    console.print(f"[bold cyan]BoardLens GDB Server listening on {host}:{port}[/bold cyan] ({core.upper()})...")
    console.print(f"[dim]Connect with: gdb-multiarch -ex 'target remote {host}:{port}'[/dim]")
    server.start()
    try:
        import time
        while server.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping GDB server...[/yellow]")
        server.stop()


@app.command()
def studio(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host address."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on."),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable server reload."),
) -> None:
    """Launch the interactive BoardLens Web Studio."""
    console.print(f"[bold cyan]Launching BoardLens Studio[/bold cyan] at [bold green]http://{host}:{port}[/bold green]...")
    uvicorn.run("boardlens.web.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()

