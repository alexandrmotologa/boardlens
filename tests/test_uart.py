"""Unit tests for UARTPeripheral."""

import pytest
from boardlens.peripherals.uart import UARTPeripheral


def test_uart_transmission():
    uart = UARTPeripheral()

    # Initial state: TX ready
    sr = uart.read32(UARTPeripheral.REG_SR)
    assert bool(sr & UARTPeripheral.SR_TXE) is True

    # Transmit characters: "HELLO"
    tx_events = []
    uart.add_tx_listener(lambda b: tx_events.append(b))

    for char in "HELLO":
        uart.write32(UARTPeripheral.REG_DR, ord(char))

    assert bytes(tx_events) == b"HELLO"
    assert uart.read_tx_string() == "HELLO"
    # Drained
    assert uart.read_tx_string() == ""


def test_uart_reception():
    uart = UARTPeripheral()

    # Initially RX is empty
    sr = uart.read32(UARTPeripheral.REG_SR)
    assert bool(sr & UARTPeripheral.SR_RXNE) is False

    # Inject input from virtual console
    uart.write_to_rx("OK\n")

    # Status register now indicates data available
    sr = uart.read32(UARTPeripheral.REG_SR)
    assert bool(sr & UARTPeripheral.SR_RXNE) is True

    # Read data register byte by byte
    c1 = chr(uart.read32(UARTPeripheral.REG_DR))
    c2 = chr(uart.read32(UARTPeripheral.REG_DR))
    c3 = chr(uart.read32(UARTPeripheral.REG_DR))

    assert c1 == "O"
    assert c2 == "K"
    assert c3 == "\n"

    # Now empty again
    sr = uart.read32(UARTPeripheral.REG_SR)
    assert bool(sr & UARTPeripheral.SR_RXNE) is False
    assert uart.read32(UARTPeripheral.REG_DR) == 0
