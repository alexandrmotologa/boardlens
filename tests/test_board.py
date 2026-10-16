"""End-to-end integration tests for the virtual microcontroller Board."""

import pytest
from boardlens.board import Board
from boardlens.cpu.base import TrapCause
from boardlens.examples import BLINKY_ASM, FIBONACCI_ASM, OLED_DEMO_ASM, UART_HELLO_ASM


def test_board_blinky():
    board = Board(core="rv32i")
    board.load_flash(BLINKY_ASM)

    # Track Pin 5 toggles
    toggles = []
    board.gpio.add_pin_listener(lambda pin, high: toggles.append((pin, high)))

    res = board.run(max_cycles=1000)
    assert res.trap == TrapCause.BREAKPOINT

    # Pin 5 should have toggled ON, OFF, and ON
    pin5_toggles = [high for pin, high in toggles if pin == 5]
    assert pin5_toggles == [True, False, True]
    assert board.gpio.get_pin_output(5) is True


def test_board_uart_hello():
    board = Board(core="rv32i")
    board.load_flash(UART_HELLO_ASM)

    res = board.run(max_cycles=1000)
    assert res.trap == TrapCause.BREAKPOINT

    output = board.uart.read_tx_string()
    assert output == "Hello!\n"


def test_board_fibonacci():
    board = Board(core="rv32i")
    board.load_flash(FIBONACCI_ASM)

    res = board.run(max_cycles=10000)
    assert res.trap == TrapCause.BREAKPOINT

    # Expected Fibonacci numbers: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89
    expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
    for idx, expected_val in enumerate(expected):
        addr = board.SRAM_BASE + (idx * 4)
        assert board.bus.read32(addr) == expected_val


def test_board_oled_demo():
    board = Board(core="rv32i")
    board.load_flash(OLED_DEMO_ASM)

    res = board.run(max_cycles=1000)
    assert res.trap == TrapCause.BREAKPOINT
    assert board.oled.display_on is True


def test_board_breakpoint_and_vcd():
    board = Board(core="rv32i", enable_vcd=True)
    board.load_flash(BLINKY_ASM)

    # Breakpoint at PC=0x04
    board.add_breakpoint(0x04)
    res = board.run(max_cycles=100)
    assert res.trap == TrapCause.BREAKPOINT
    assert board.cpu.pc == 0x04

    # Remove breakpoint and continue
    board.remove_breakpoint(0x04)
    res2 = board.run(max_cycles=100)
    assert res2.trap == TrapCause.BREAKPOINT

    # VCD generation check
    assert board.vcd is not None
    vcd_text = board.vcd.generate()
    assert "$timescale" in vcd_text
    assert "gpio_out" in vcd_text
    assert "bus_addr" in vcd_text


def test_board_telemetry_status():
    board = Board(core="rv32i")
    status = board.get_status()
    assert status["core"] == "rv32i"
    assert "registers" in status
    assert len(status["gpio"]["pins"]) == 16
    assert "oled" in status


def test_board_load_elf():
    from boardlens.tooling.assembler import assemble
    from boardlens.tooling.elf_loader import create_minimal_elf32

    code = assemble("addi a0, zero, 99\nebreak\n")
    elf_bytes = create_minimal_elf32(code, entry_addr=0x00000000, symbols={"main": 0x00000000})

    board = Board(core="rv32i")
    board.load_flash(elf_bytes)
    assert "main" in board.symbol_names
    assert board.symbols[0x00000000].name == "main"

    res = board.run(max_cycles=100)
    assert res.trap == TrapCause.BREAKPOINT
    assert board.cpu.registers.read("a0") == 99
