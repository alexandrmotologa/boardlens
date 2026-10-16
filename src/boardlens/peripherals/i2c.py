"""Authentic I2C master bus controller and slave device interfaces."""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from boardlens.peripherals.base import Peripheral


class I2CDevice(ABC):
    """Abstract interface for devices connected to the virtual I2C bus."""

    def __init__(self, address: int) -> None:
        self.address = address & 0x7F

    @abstractmethod
    def on_start(self) -> None:
        """Called when master issues an I2C START condition."""
        pass

    @abstractmethod
    def on_address(self, address: int, is_read: bool) -> bool:
        """Called when master sends target address. Returns True if device ACKs."""
        pass

    @abstractmethod
    def on_write_byte(self, byte_val: int) -> bool:
        """Called when master writes data byte. Returns True if device ACKs."""
        pass

    @abstractmethod
    def on_read_byte(self) -> int:
        """Called when master reads data byte. Returns byte value."""
        pass

    @abstractmethod
    def on_stop(self) -> None:
        """Called when master issues an I2C STOP condition."""
        pass


class I2CController(Peripheral):
    """Memory-mapped I2C master controller state machine."""

    REG_CR1 = 0x00
    REG_CR2 = 0x04
    REG_OAR1 = 0x08
    REG_DR = 0x0C
    REG_SR1 = 0x10
    REG_SR2 = 0x14
    REG_CCR = 0x18

    # CR1 bits
    CR1_PE = 1 << 0
    CR1_START = 1 << 8
    CR1_STOP = 1 << 9
    CR1_ACK = 1 << 10

    # SR1 bits
    SR1_SB = 1 << 0     # Start bit generated
    SR1_ADDR = 1 << 1   # Address sent / matched
    SR1_BTF = 1 << 2    # Byte transfer finished
    SR1_RXNE = 1 << 6   # Rx data register not empty
    SR1_TXE = 1 << 7    # Tx data register empty
    SR1_AF = 1 << 10    # Acknowledge failure (NACK)

    # SR2 bits
    SR2_MSL = 1 << 0    # Master / Slave mode
    SR2_BUSY = 1 << 1   # Bus busy
    SR2_TRA = 1 << 2    # Transmitter / Receiver

    def __init__(self, base_address: int = 0x40003000, name: str = "I2C0") -> None:
        super().__init__(base_address, size=0x400, name=name)
        self.register_def(self.REG_CR1, "CR1", reset_val=0x00000000)
        self.register_def(self.REG_CR2, "CR2", reset_val=0x00000010)
        self.register_def(self.REG_OAR1, "OAR1", reset_val=0x00004000)
        self.register_def(self.REG_DR, "DR", reset_val=0x00000000)
        self.register_def(self.REG_SR1, "SR1", reset_val=self.SR1_TXE)
        self.register_def(self.REG_SR2, "SR2", reset_val=0x00000000)
        self.register_def(self.REG_CCR, "CCR", reset_val=0x00000000)

        self._devices: Dict[int, I2CDevice] = {}
        self._active_device: Optional[I2CDevice] = None
        self._is_read: bool = False
        self._addr_phase: bool = False

    def attach_device(self, device: I2CDevice) -> None:
        """Attach a virtual I2C peripheral device at its 7-bit slave address."""
        self._devices[device.address & 0x7F] = device

    def on_register_write(self, offset: int, old_value: int, new_value: int) -> None:
        cr1 = self._regs.get(self.REG_CR1, 0)

        # Check peripheral enable
        if not (cr1 & self.CR1_PE):
            self._regs[self.REG_SR1] = self.SR1_TXE
            self._regs[self.REG_SR2] = 0
            self._active_device = None
            return

        # Check START condition generation
        if (new_value & self.CR1_START) and not (old_value & self.CR1_START):
            self._regs[self.REG_CR1] &= ~self.CR1_START
            self._regs[self.REG_SR1] |= self.SR1_SB
            self._regs[self.REG_SR2] |= (self.SR2_MSL | self.SR2_BUSY)
            self._addr_phase = True
            for dev in self._devices.values():
                dev.on_start()

        # Check STOP condition generation
        if (new_value & self.CR1_STOP) and not (old_value & self.CR1_STOP):
            self._regs[self.REG_CR1] &= ~self.CR1_STOP
            self._regs[self.REG_SR1] = self.SR1_TXE
            self._regs[self.REG_SR2] &= ~(self.SR2_MSL | self.SR2_BUSY | self.SR2_TRA)
            if self._active_device:
                self._active_device.on_stop()
                self._active_device = None
            self._addr_phase = False

        # Data Register transmission
        if offset == self.REG_DR:
            byte_val = new_value & 0xFF
            if self._addr_phase:
                # Transmitting 7-bit address + R/W bit
                target_addr = (byte_val >> 1) & 0x7F
                self._is_read = bool(byte_val & 1)
                self._active_device = self._devices.get(target_addr)

                if self._active_device and self._active_device.on_address(target_addr, self._is_read):
                    # Address acknowledged
                    self._regs[self.REG_SR1] |= self.SR1_ADDR | self.SR1_TXE | self.SR1_BTF
                    self._regs[self.REG_SR1] &= ~self.SR1_SB
                    if not self._is_read:
                        self._regs[self.REG_SR2] |= self.SR2_TRA
                    else:
                        self._regs[self.REG_SR2] &= ~self.SR2_TRA
                else:
                    # NACK
                    self._regs[self.REG_SR1] |= self.SR1_AF
                    self._regs[self.REG_SR1] &= ~(self.SR1_ADDR | self.SR1_SB)
                    self._active_device = None

                self._addr_phase = False

            else:
                # Transmitting data payload byte
                if self._active_device and not self._is_read:
                    ack = self._active_device.on_write_byte(byte_val)
                    if ack:
                        self._regs[self.REG_SR1] |= (self.SR1_TXE | self.SR1_BTF)
                        self._regs[self.REG_SR1] &= ~self.SR1_AF
                    else:
                        self._regs[self.REG_SR1] |= self.SR1_AF
                        self._regs[self.REG_SR1] &= ~self.SR1_BTF
                else:
                    self._regs[self.REG_SR1] |= self.SR1_AF

    def on_register_read(self, offset: int, value: int) -> int:
        if offset == self.REG_SR1:
            return self._regs.get(self.REG_SR1, 0)

        elif offset == self.REG_SR2:
            # Reading SR2 after reading SR1 clears ADDR flag (standard STM32 / ARM I2C protocol)
            self._regs[self.REG_SR1] &= ~self.SR1_ADDR
            return self._regs.get(self.REG_SR2, 0)

        elif offset == self.REG_DR:
            if self._active_device and self._is_read:
                data = self._active_device.on_read_byte() & 0xFF
                self._regs[self.REG_SR1] &= ~self.SR1_RXNE
                return data
            return 0

        return value
