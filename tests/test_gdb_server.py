"""Unit tests for GDB Remote Serial Protocol (RSP) stub server."""

import socket
import time
import pytest
from boardlens.board import Board
from boardlens.tooling.gdb_server import (
    GDBServer,
    compute_checksum,
    format_packet,
    gdb_hex_to_int,
    int_to_gdb_hex,
)


def test_gdb_hex_helpers():
    # Little-endian encoding of 0x12345678 -> '78563412'
    val = 0x12345678
    encoded = int_to_gdb_hex(val)
    assert encoded == "78563412"
    assert gdb_hex_to_int(encoded) == val

    # 1-byte encoding
    assert int_to_gdb_hex(0x42, width_bytes=1) == "42"


def test_packet_framing_and_checksum():
    payload = "OK"
    # 'O' = 79, 'K' = 75, sum = 154 = 0x9a
    assert compute_checksum(payload) == 0x9A
    packet = format_packet(payload)
    assert packet == "$OK#9a"


def test_gdb_halt_and_query_packets():
    board = Board(core="rv32i")
    server = GDBServer(board)

    assert server.handle_packet("?") == "S05"
    assert "PacketSize" in server.handle_packet("qSupported")
    assert server.handle_packet("qAttached") == "1"
    assert server.handle_packet("qC") == "QC1"
    assert server.handle_packet("qOffsets") == "Text=0;Data=0;Bss=0"


def test_gdb_register_read_and_write_rv32i():
    board = Board(core="rv32i")
    server = GDBServer(board)

    # Set some register values
    board.cpu.regs.write(1, 0x11223344)
    board.cpu.pc = 0x00001000

    # 'g' packet returns 33 * 8 = 264 characters
    regs_hex = server.handle_packet("g")
    assert len(regs_hex) == 33 * 8

    # Verify x1 register chunk (offset 8 to 16)
    x1_hex = regs_hex[8:16]
    assert gdb_hex_to_int(x1_hex) == 0x11223344

    # Verify PC chunk (offset 32*8 to 33*8)
    pc_hex = regs_hex[32 * 8 : 33 * 8]
    assert gdb_hex_to_int(pc_hex) == 0x00001000

    # Write single register 'P1=44332211'
    resp = server.handle_packet("P1=44332211")
    assert resp == "OK"
    assert board.cpu.regs.read(1) == 0x11223344  # Note little endian parsing of 44332211

    # Read single register 'p1'
    single_hex = server.handle_packet("p1")
    assert single_hex == "44332211"


def test_gdb_register_read_arm():
    board = Board(core="arm")
    server = GDBServer(board)

    board.cpu.regs.write(0, 0xCAFEBABE)
    regs_hex = server.handle_packet("g")
    assert len(regs_hex) == 17 * 8
    assert gdb_hex_to_int(regs_hex[0:8]) == 0xCAFEBABE


def test_gdb_memory_read_and_write():
    board = Board(core="rv32i")
    server = GDBServer(board)

    # Write 4 bytes into SRAM at 0x20000000: 'M20000000,4:01020304'
    resp = server.handle_packet("M20000000,4:01020304")
    assert resp == "OK"
    assert board.bus.read8(0x20000000) == 0x01
    assert board.bus.read8(0x20000001) == 0x02
    assert board.bus.read8(0x20000002) == 0x03
    assert board.bus.read8(0x20000003) == 0x04

    # Read back 4 bytes: 'm20000000,4'
    read_hex = server.handle_packet("m20000000,4")
    assert read_hex == "01020304"


def test_gdb_breakpoints():
    board = Board(core="rv32i")
    server = GDBServer(board)

    # Insert breakpoint at 0x00000010
    assert server.handle_packet("Z0,10,2") == "OK"
    assert 0x10 in board.cpu.breakpoints

    # Remove breakpoint
    assert server.handle_packet("z0,10,2") == "OK"
    assert 0x10 not in board.cpu.breakpoints


def test_gdb_step_and_continue():
    board = Board(core="rv32i")
    server = GDBServer(board)

    # Assemble simple instructions: addi x1, x0, 5; addi x2, x0, 10
    from boardlens.tooling.assembler import assemble
    code = """
        addi x1, x0, 5
        addi x2, x0, 10
        ebreak
    """
    image = assemble(code)
    board.load_flash(image)

    # Step instruction 1
    resp = server.handle_packet("s")
    assert resp == "S05"
    assert board.cpu.regs.read(1) == 5

    # Continue until ebreak
    resp2 = server.handle_packet("c")
    assert resp2 == "S05"
    assert board.cpu.regs.read(2) == 10


def test_gdb_tcp_socket_interaction():
    board = Board(core="rv32i")
    # Find free port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    free_port = sock.getsockname()[1]
    sock.close()

    server = GDBServer(board, host="127.0.0.1", port=free_port)
    server.start()
    time.sleep(0.1)

    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2.0)
        client.connect(("127.0.0.1", free_port))

        # Send halt query packet: $?#3f
        client.sendall(b"$?#3f")

        # Expect ACK '+' and '$S05#b8'
        resp = bytearray()
        while b"$" not in resp:
            chunk = client.recv(1024)
            if not chunk:
                break
            resp.extend(chunk)

        assert b"+" in resp or len(resp) > 0
        assert b"$S05#" in resp

        client.close()
    finally:
        server.stop()

