from collections import deque
from typing import Any, Callable, Dict, List, Optional, Union

from boardlens.cpu.arm.core import ARMCortexMCore
from boardlens.cpu.base import CPUCore, StepResult, TrapCause
from boardlens.cpu.rv32i.core import RV32ICore
from boardlens.devices.ssd1306 import SSD1306
from boardlens.memory.bus import BusTransaction, MemoryBus
from boardlens.memory.ram import RAM
from boardlens.peripherals.adc import ADCPeripheral
from boardlens.peripherals.gpio import GPIOPort
from boardlens.peripherals.i2c import I2CController
from boardlens.peripherals.timer import SysTickTimer
from boardlens.peripherals.uart import UARTPeripheral
from boardlens.tooling.assembler import assemble
from boardlens.tooling.elf_loader import ELF32
from boardlens.tooling.vcd import VCDTracer


class Board:
    """Virtual Microcontroller Board emulating 32-bit hardware platform."""

    FLASH_BASE = 0x00000000
    FLASH_SIZE = 128 * 1024       # 128 KB
    SRAM_BASE = 0x20000000
    SRAM_SIZE = 64 * 1024         # 64 KB

    GPIO_BASE = 0x40000000
    UART_BASE = 0x40001000
    TIMER_BASE = 0x40002000
    I2C_BASE = 0x40003000
    ADC_BASE = 0x40004000

    def __init__(self, core: str = "rv32i", enable_vcd: bool = False) -> None:
        self.core_type = core.lower()
        self.bus = MemoryBus(allow_unaligned=True)

        # Physical Memory Regions
        self.flash = RAM(self.FLASH_BASE, self.FLASH_SIZE, name="FLASH", read_only=False)
        self.sram = RAM(self.SRAM_BASE, self.SRAM_SIZE, name="SRAM", read_only=False)
        self.bus.map_region(self.flash)
        self.bus.map_region(self.sram)

        # Peripherals
        self.gpio = GPIOPort(self.GPIO_BASE, name="GPIOA")
        self.uart = UARTPeripheral(self.UART_BASE, name="UART0")
        self.timer = SysTickTimer(self.TIMER_BASE, name="SysTick")
        self.i2c = I2CController(self.I2C_BASE, name="I2C0")
        self.adc = ADCPeripheral(self.ADC_BASE, name="ADC0")

        self.bus.map_region(self.gpio)
        self.bus.map_region(self.uart)
        self.bus.map_region(self.timer)
        self.bus.map_region(self.i2c)
        self.bus.map_region(self.adc)

        # Virtual Hardware Devices
        self.oled = SSD1306(address=0x3C)
        self.i2c.attach_device(self.oled)

        # CPU Core
        initial_pc = self.FLASH_BASE
        if self.core_type == "arm" or self.core_type == "cortex-m":
            self.cpu: CPUCore = ARMCortexMCore(self.bus, initial_pc=initial_pc)
        else:
            self.cpu = RV32ICore(self.bus, initial_pc=initial_pc)

        # VCD Waveform Tracer
        self.vcd: Optional[VCDTracer] = None
        if enable_vcd:
            self.enable_vcd_tracing()

        # Telemetry & Logic Analyzer Waveform History
        self.loaded_image: bytes = b""
        self._waveform_history: deque[Dict[str, Any]] = deque(maxlen=64)
        self._last_bus_tx: Optional[BusTransaction] = None

        def track_bus(tx: BusTransaction) -> None:
            self._last_bus_tx = tx

        self.bus.add_listener(track_bus)


    def enable_vcd_tracing(self, timescale: str = "10ns") -> VCDTracer:
        """Attach VCD waveform tracer to internal bus and peripheral signals."""
        self.vcd = VCDTracer(timescale=timescale)
        self.vcd.register_signal("clk", width=1, initial_value=0)
        self.vcd.register_signal("pc", width=32, initial_value=self.cpu.pc)
        self.vcd.register_signal("bus_addr", width=32, initial_value=0)
        self.vcd.register_signal("bus_data", width=32, initial_value=0)
        self.vcd.register_signal("bus_we", width=1, initial_value=0)
        self.vcd.register_signal("gpio_out", width=16, initial_value=0)
        self.vcd.register_signal("uart_tx", width=1, initial_value=1)

        def on_bus_tx(tx: BusTransaction) -> None:
            if self.vcd:
                t = tx.cycle * 10
                self.vcd.set_time(t)
                self.vcd.change("bus_addr", tx.address, timestamp=t)
                self.vcd.change("bus_data", tx.data, timestamp=t)
                self.vcd.change("bus_we", 1 if tx.is_write else 0, timestamp=t)

        self.bus.add_listener(on_bus_tx)

        def on_pin_change(pin: int, high: bool) -> None:
            if self.vcd:
                odr = self.gpio.read_reg(GPIOPort.REG_ODR)
                self.vcd.change("gpio_out", odr)

        self.gpio.add_pin_listener(on_pin_change)

        return self.vcd

    def load_flash(self, data: Union[bytes, bytearray, str]) -> None:
        """Load firmware image. Supports assembly strings, raw binaries, or ELF32 executables."""
        if isinstance(data, str):
            from boardlens.tooling.assembler import Assembler
            asm = Assembler(base_address=self.FLASH_BASE)
            binary = asm.assemble(data)
            self.loaded_image = binary
            self.symbols = dict(asm.symbols)
            self.symbol_names = {v: k for k, v in asm.symbols.items()}
            self.flash.load_bytes(0, binary)
            self.reset()

        elif bytes(data).startswith(b"\x7fELF"):
            from boardlens.tooling.elf_loader import ELF32
            elf = ELF32(bytes(data))
            self.symbols = elf.symbols
            self.symbol_names = elf.symbol_names
            self.loaded_image = bytes(data)
            self.reset()
            entry = elf.load_into_bus(self.bus)
            self.cpu.pc = entry
        else:
            binary = bytes(data)
            self.loaded_image = binary
            self.symbols = {}
            self.symbol_names = {}
            self.flash.load_bytes(0, binary)
            self.reset()

    def reset(self) -> None:
        """Reset CPU, bus, peripherals, and device states."""
        self.flash.reset()
        if self.loaded_image:
            self.flash.load_bytes(0, self.loaded_image)
        self.sram.reset()
        self.gpio.reset()
        self.uart.reset()
        self.timer.reset()
        self.i2c.reset()
        self.adc.reset()
        self.oled.clear()
        self._waveform_history.clear()
        self._last_bus_tx = None
        self.cpu.reset(initial_pc=self.FLASH_BASE)

    def add_breakpoint(self, address: int) -> None:
        if hasattr(self.cpu, "add_breakpoint"):
            self.cpu.add_breakpoint(address)

    def remove_breakpoint(self, address: int) -> None:
        if hasattr(self.cpu, "remove_breakpoint"):
            self.cpu.remove_breakpoint(address)

    def step(self) -> StepResult:
        """Execute one CPU instruction step and advance peripheral timers."""
        res = self.cpu.step()
        cycles = res.cycles if res.cycles > 0 else 1

        # Advance peripherals
        self.timer.step(cycles=cycles)
        self.gpio.step(cycles=cycles)
        self.uart.step(cycles=cycles)
        self.i2c.step(cycles=cycles)
        self.adc.step(cycles=cycles)

        # Record waveform sample for logic analyzer
        tx = self._last_bus_tx
        self._waveform_history.append({
            "cycle": self.cpu.cycles,
            "pc": f"0x{res.pc:08X}",
            "pc_val": res.pc,
            "addr": f"0x{tx.address:08X}" if tx else "0x00000000",
            "we": 1 if (tx and tx.is_write) else 0,
            "pa5": 1 if self.gpio.get_pin_output(5) else 0,
            "tx": 0 if len(self.uart._tx_fifo) > 0 else 1,
            "adc": self.adc.read_reg(ADCPeripheral.REG_DR),
        })

        if self.vcd:
            t = self.cpu.cycles * 10
            self.vcd.set_time(t)
            self.vcd.change("clk", 1, timestamp=t)
            self.vcd.change("pc", res.pc, timestamp=t)
            self.vcd.change("clk", 0, timestamp=t + 5)

        return res

    def run(self, max_cycles: int = 100000) -> StepResult:
        """Run execution loop until breakpoint, trap, halt, or cycle budget exhausted."""
        last_res = StepResult(self.cpu.pc, self.cpu.pc, 0, "INIT", 0)
        while self.cpu.cycles < max_cycles:
            last_res = self.step()
            if last_res.trap is not None:
                break
        return last_res

    @property
    def cycles(self) -> int:
        return self.cpu.cycles

    def get_waveform_history(self) -> List[Dict[str, Any]]:
        """Return rolling history of clock/bus/peripheral transitions for logic analyzer."""
        return list(self._waveform_history)

    def get_status(self) -> Dict[str, Any]:
        """Aggregate system status for Web Studio dashboard."""
        return {
            "core": self.core_type,
            "pc": f"0x{self.cpu.pc:08X}",
            "pc_decimal": self.cpu.pc,
            "cycles": self.cpu.cycles,
            "halted": getattr(self.cpu, "halted", False),
            "registers": self.cpu.registers.to_dict() if hasattr(self.cpu, "registers") else {},
            "gpio": {
                "pins": [
                    {
                        "pin": i,
                        "mode": ["INPUT", "OUTPUT", "ALTERNATE", "ANALOG"][self.gpio.get_pin_mode(i)],
                        "output": self.gpio.get_pin_output(i),
                        "state": self.gpio.get_pin_state(i),
                    }
                    for i in range(16)
                ],
                "odr": f"0x{self.gpio.read_reg(GPIOPort.REG_ODR):04X}",
                "idr": f"0x{self.gpio.read_reg(GPIOPort.REG_IDR):04X}",
            },
            "uart": {
                "tx_pending_bytes": len(self.uart._tx_fifo),
                "rx_pending_bytes": len(self.uart._rx_fifo),
            },
            "oled": {
                "on": self.oled.display_on,
                "contrast": self.oled.contrast,
                "inverted": self.oled.inverted,
            },
            "adc": {
                "dr": self.adc.read_reg(ADCPeripheral.REG_DR),
                "sr": f"0x{self.adc.read_reg(ADCPeripheral.REG_SR):02X}",
                "cr2": f"0x{self.adc.read_reg(ADCPeripheral.REG_CR2):08X}",
                "channels": [
                    {
                        "channel": i,
                        "millivolts": self.adc.get_channel_millivolts(i),
                        "voltage": round(self.adc.get_channel_voltage(i), 2),
                    }
                    for i in range(4)
                ],
            },
        }

