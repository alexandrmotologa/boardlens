"""GDB Remote Serial Protocol (RSP) stub server for BoardLens."""

import socket
import threading
from typing import TYPE_CHECKING, Any, Optional, Tuple
from boardlens.cpu.base import TrapCause

if TYPE_CHECKING:
    from boardlens.board import Board



def int_to_gdb_hex(val: int, width_bytes: int = 4) -> str:
    """Format integer as little-endian hexadecimal byte string for GDB."""
    return (val & 0xFFFFFFFF).to_bytes(width_bytes, byteorder="little").hex()


def gdb_hex_to_int(hex_str: str, width_bytes: int = 4) -> int:
    """Parse little-endian hexadecimal string into integer."""
    raw = bytes.fromhex(hex_str)
    return int.from_bytes(raw[:width_bytes], byteorder="little")


def compute_checksum(payload: str) -> int:
    """Compute standard GDB RSP 8-bit checksum."""
    return sum(payload.encode("latin1")) % 256


def format_packet(payload: str) -> str:
    """Wrap payload into GDB RSP packet format: $payload#checksum."""
    return f"${payload}#{compute_checksum(payload):02x}"


class GDBServer:
    """Embedded GDB RSP server bridging GNU Debugger (gdb-multiarch) to BoardLens."""

    def __init__(
        self,
        board: Any,
        host: str = "127.0.0.1",
        port: int = 3333,
    ) -> None:
        self.board = board
        self.host = host
        self.port = port
        self.running: bool = False
        self._server_socket: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None
        self._interrupt_requested: bool = False

    def handle_packet(self, cmd: str) -> str:
        """Process incoming GDB command and return raw unpacketized response string.

        Returning empty string causes stub to respond with '$#00' (unsupported).
        """
        if not cmd:
            return ""

        # Halt reason query
        if cmd == "?":
            return "S05"

        # Query packets
        if cmd.startswith("qSupported"):
            return "PacketSize=1000;hwbreak+;swbreak+;vContSupported+"
        if cmd.startswith("qAttached"):
            return "1"
        if cmd == "qC":
            return "QC1"
        if cmd.startswith("qOffsets"):
            return "Text=0;Data=0;Bss=0"

        # Read all general-purpose registers
        if cmd == "g":
            return self._read_all_regs()

        # Write all general-purpose registers
        if cmd.startswith("G"):
            return self._write_all_regs(cmd[1:])

        # Read single register: p<hex_regnum>
        if cmd.startswith("p"):
            try:
                regnum = int(cmd[1:], 16)
                return self._read_single_reg(regnum)
            except Exception:
                return "E01"

        # Write single register: P<hex_regnum>=<val_hex>
        if cmd.startswith("P"):
            try:
                parts = cmd[1:].split("=")
                if len(parts) == 2:
                    regnum = int(parts[0], 16)
                    val = gdb_hex_to_int(parts[1])
                    return self._write_single_reg(regnum, val)
                return "E01"
            except Exception:
                return "E01"

        # Read memory: m<addr_hex>,<len_hex>
        if cmd.startswith("m"):
            try:
                params = cmd[1:].split(",")
                addr = int(params[0], 16)
                length = int(params[1], 16)
                data = bytearray()
                for i in range(length):
                    data.append(self.board.bus.read8(addr + i))
                return data.hex()
            except Exception:
                return "E01"

        # Write memory: M<addr_hex>,<len_hex>:<hex_data>
        if cmd.startswith("M"):
            try:
                header, hex_data = cmd[1:].split(":")
                addr_str, _ = header.split(",")
                addr = int(addr_str, 16)
                raw_bytes = bytes.fromhex(hex_data)
                for i, b in enumerate(raw_bytes):
                    self.board.bus.write8(addr + i, b)
                return "OK"
            except Exception:
                return "E01"

        # Breakpoints: Z0,<addr>,<kind> and z0,<addr>,<kind>
        if cmd.startswith("Z0,"):
            try:
                parts = cmd.split(",")
                addr = int(parts[1], 16)
                self.board.add_breakpoint(addr)
                return "OK"
            except Exception:
                return "E01"

        if cmd.startswith("z0,"):
            try:
                parts = cmd.split(",")
                addr = int(parts[1], 16)
                self.board.remove_breakpoint(addr)
                return "OK"
            except Exception:
                return "E01"

        # Single step: s or s<addr>
        if cmd.startswith("s"):
            if len(cmd) > 1:
                try:
                    self.board.cpu.pc = int(cmd[1:], 16)
                except Exception:
                    pass
            res = self.board.step()
            if res.trap == TrapCause.ENVIRONMENT_CALL:
                return "W00"
            return "S05"

        # Continue: c or c<addr>
        if cmd.startswith("c"):
            if len(cmd) > 1:
                try:
                    self.board.cpu.pc = int(cmd[1:], 16)
                except Exception:
                    pass
            return self._continue_execution()

        # vCont support
        if cmd == "vCont?":
            return "vCont;c;s;t"
        if cmd.startswith("vCont;s"):
            self.board.step()
            return "S05"
        if cmd.startswith("vCont;c"):
            return self._continue_execution()

        # Detach
        if cmd.startswith("D"):
            return "OK"

        # Kill
        if cmd == "k":
            self.running = False
            return ""

        return ""

    def _read_all_regs(self) -> str:
        """Serialize all architecture registers to GDB little-endian hex."""
        chunks = []
        is_arm = self.board.core_type in ("arm", "cortex-m")

        if is_arm:
            # ARM Thumb: R0-R15 + xPSR (17 registers)
            for r in range(16):
                val = self.board.cpu.regs.read(r)
                chunks.append(int_to_gdb_hex(val))
            psr = getattr(self.board.cpu.regs, "read_psr", lambda: 0)()
            chunks.append(int_to_gdb_hex(psr))
        else:
            # RV32I: x0-x31 + PC (33 registers)
            for r in range(32):
                val = self.board.cpu.regs.read(r)
                chunks.append(int_to_gdb_hex(val))
            chunks.append(int_to_gdb_hex(self.board.cpu.pc))

        return "".join(chunks)

    def _write_all_regs(self, hex_payload: str) -> str:
        """Deserialize and write all architecture registers from GDB hex."""
        is_arm = self.board.core_type in ("arm", "cortex-m")
        stride = 8
        count = len(hex_payload) // stride

        if is_arm:
            for i in range(min(16, count)):
                chunk = hex_payload[i * stride : (i + 1) * stride]
                val = gdb_hex_to_int(chunk)
                self.board.cpu.regs.write(i, val)
        else:
            for i in range(min(32, count)):
                chunk = hex_payload[i * stride : (i + 1) * stride]
                val = gdb_hex_to_int(chunk)
                self.board.cpu.regs.write(i, val)
            if count >= 33:
                pc_chunk = hex_payload[32 * stride : 33 * stride]
                self.board.cpu.pc = gdb_hex_to_int(pc_chunk)

        return "OK"

    def _read_single_reg(self, regnum: int) -> str:
        is_arm = self.board.core_type in ("arm", "cortex-m")
        if is_arm:
            if 0 <= regnum < 16:
                return int_to_gdb_hex(self.board.cpu.regs.read(regnum))
            if regnum == 25:  # xPSR index in standard GDB
                psr = getattr(self.board.cpu.regs, "read_psr", lambda: 0)()
                return int_to_gdb_hex(psr)
        else:
            if 0 <= regnum < 32:
                return int_to_gdb_hex(self.board.cpu.regs.read(regnum))
            if regnum == 32:
                return int_to_gdb_hex(self.board.cpu.pc)
        return "E01"

    def _write_single_reg(self, regnum: int, val: int) -> str:
        is_arm = self.board.core_type in ("arm", "cortex-m")
        if is_arm:
            if 0 <= regnum < 16:
                self.board.cpu.regs.write(regnum, val)
                return "OK"
        else:
            if 0 <= regnum < 32:
                self.board.cpu.regs.write(regnum, val)
                return "OK"
            if regnum == 32:
                self.board.cpu.pc = val & 0xFFFFFFFF
                return "OK"
        return "E01"

    def _continue_execution(self, max_steps: int = 1000000) -> str:
        """Run execution loop until breakpoint, trap, interrupt, or budget exhaustion."""
        self._interrupt_requested = False
        steps = 0
        while steps < max_steps and not self._interrupt_requested:
            res = self.board.step()
            steps += 1
            if res.trap == TrapCause.BREAKPOINT:
                return "S05"
            if res.trap == TrapCause.ENVIRONMENT_CALL:
                return "W00"
            if res.trap is not None:
                return "S05"

        return "S05"

    def process_client_stream(self, client: socket.socket) -> None:
        """Serve a single connected GDB client session."""
        buffer = bytearray()
        client.settimeout(0.5)

        while self.running:
            try:
                chunk = client.recv(1024)
                if not chunk:
                    break
                buffer.extend(chunk)
            except socket.timeout:
                continue
            except OSError:
                break

            # Handle Ctrl+C interrupt (\x03)
            while b"\x03" in buffer:
                buffer.remove(0x03)
                self._interrupt_requested = True
                client.sendall(format_packet("S05").encode("latin1"))

            # Process GDB $...#xx packets
            while True:
                start_idx = buffer.find(b"$")
                if start_idx == -1:
                    buffer.clear()
                    break
                hash_idx = buffer.find(b"#", start_idx)
                if hash_idx == -1 or len(buffer) < hash_idx + 3:
                    # Incomplete packet, wait for more data
                    if start_idx > 0:
                        del buffer[:start_idx]
                    break

                payload_bytes = buffer[start_idx + 1 : hash_idx]
                checksum_str = buffer[hash_idx + 1 : hash_idx + 3].decode("latin1", errors="ignore")
                del buffer[: hash_idx + 3]

                # ACK incoming packet
                client.sendall(b"+")

                payload = payload_bytes.decode("latin1", errors="ignore")
                resp_payload = self.handle_packet(payload)
                resp_packet = format_packet(resp_payload)
                client.sendall(resp_packet.encode("latin1"))

    def start(self) -> None:
        """Start listening for GDB connections in a background thread."""
        self.running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(1)

        def _serve() -> None:
            while self.running:
                try:
                    self._server_socket.settimeout(0.5)
                    client, _ = self._server_socket.accept()
                    self.process_client_stream(client)
                    client.close()
                except socket.timeout:
                    continue
                except OSError:
                    break

        self._server_thread = threading.Thread(target=_serve, daemon=True)
        self._server_thread.start()

    def stop(self) -> None:
        """Stop GDB stub server."""
        self.running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        if self._server_thread:
            self._server_thread.join(timeout=1.0)
