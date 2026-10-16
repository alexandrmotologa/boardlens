"""Authentic UART peripheral with FIFO queues and status registers."""

from collections import deque
from typing import Callable, List, Optional, Union
from boardlens.peripherals.base import Peripheral


class UARTPeripheral(Peripheral):
    """Universal Asynchronous Receiver/Transmitter with hardware FIFO queues."""

    REG_SR = 0x00
    REG_DR = 0x04
    REG_BRR = 0x08
    REG_CR1 = 0x0C

    # SR status bits
    SR_TXE = 1 << 7    # Transmit data register empty
    SR_TC = 1 << 6     # Transmission complete
    SR_RXNE = 1 << 5   # Read data register not empty

    # CR1 control bits
    CR1_UE = 1 << 13   # UART enable
    CR1_TE = 1 << 3    # Transmitter enable
    CR1_RE = 1 << 2    # Receiver enable

    def __init__(self, base_address: int = 0x40001000, name: str = "UART0") -> None:
        super().__init__(base_address, size=0x400, name=name)
        # Initial SR has TXE and TC asserted (ready to transmit)
        self.register_def(self.REG_SR, "SR", reset_val=self.SR_TXE | self.SR_TC, write_mask=0x00000000)
        self.register_def(self.REG_DR, "DR", reset_val=0x00000000)
        self.register_def(self.REG_BRR, "BRR", reset_val=0x00000341)  # Default 115200 baud at 16MHz
        self.register_def(self.REG_CR1, "CR1", reset_val=self.CR1_UE | self.CR1_TE | self.CR1_RE)

        self._tx_fifo: deque[int] = deque(maxlen=2048)
        self._rx_fifo: deque[int] = deque(maxlen=2048)
        self._tx_listeners: List[Callable[[int], None]] = []

    def add_tx_listener(self, listener: Callable[[int], None]) -> None:
        """Register a callback invoked every time a character is transmitted."""
        self._tx_listeners.append(listener)

    def write_to_rx(self, data: Union[str, bytes, int, List[int]]) -> None:
        """Inject received bytes into the UART RX FIFO (e.g. from terminal/web studio)."""
        if isinstance(data, str):
            bytes_to_add = data.encode("utf-8")
        elif isinstance(data, int):
            bytes_to_add = [data & 0xFF]
        else:
            bytes_to_add = data

        for b in bytes_to_add:
            val = b if isinstance(b, int) else ord(b)
            self._rx_fifo.append(val & 0xFF)

        self._update_sr()

    def read_tx_stream(self) -> bytes:
        """Drain all currently queued bytes from the TX buffer."""
        out = bytes(self._tx_fifo)
        self._tx_fifo.clear()
        return out

    def read_tx_string(self) -> str:
        """Drain and decode TX buffer as UTF-8 string (ignoring decode errors)."""
        return self.read_tx_stream().decode("utf-8", errors="replace")

    def _update_sr(self) -> None:
        sr = self.SR_TXE | self.SR_TC
        if len(self._rx_fifo) > 0:
            sr |= self.SR_RXNE
        self._regs[self.REG_SR] = sr

    def on_register_read(self, offset: int, value: int) -> int:
        if offset == self.REG_DR:
            if self._rx_fifo:
                val = self._rx_fifo.popleft()
                self._update_sr()
                return val
            return 0
        elif offset == self.REG_SR:
            self._update_sr()
            return self._regs[self.REG_SR]
        return value

    def on_register_write(self, offset: int, old_value: int, new_value: int) -> None:
        if offset == self.REG_DR:
            byte_val = new_value & 0xFF
            self._tx_fifo.append(byte_val)
            for listener in self._tx_listeners:
                listener(byte_val)
            self._update_sr()

    def reset(self) -> None:
        super().reset()
        self._tx_fifo.clear()
        self._rx_fifo.clear()
        self._update_sr()
