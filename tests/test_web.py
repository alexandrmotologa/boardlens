"""Integration tests for FastAPI Web Studio endpoints."""

import pytest
from fastapi.testclient import TestClient
from boardlens.web.app import app

client = TestClient(app)


def test_web_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "BoardLens" in response.text


def test_web_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "core" in data
    assert "pc" in data
    assert "cycles" in data
    assert "gpio" in data
    assert "oled" in data


def test_web_api_step_and_run():
    # Step once
    step_res = client.post("/api/step")
    assert step_res.status_code == 200
    assert "step" in step_res.json()

    # Run 50 cycles
    run_res = client.post("/api/run", json={"cycles": 50})
    assert run_res.status_code == 200
    assert "status" in run_res.json()

    # Reset
    reset_res = client.post("/api/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["cycles"] == 0


def test_web_api_load_and_examples():
    # List examples
    ex_res = client.get("/api/examples")
    assert ex_res.status_code == 200
    assert "uart_hello" in ex_res.json()

    # Load example
    load_res = client.post("/api/load", json={"example": "uart_hello"})
    assert load_res.status_code == 200

    # Load custom source
    custom_res = client.post("/api/load", json={"source": "addi x1, x0, 10\nebreak\n"})
    assert custom_res.status_code == 200

    # Bad example
    bad_res = client.post("/api/load", json={"example": "nonexistent"})
    assert bad_res.status_code == 400


def test_web_api_disassembly_and_memory():
    client.post("/api/load", json={"source": "addi x1, x0, 42\nebreak\n"})
    disasm_res = client.get("/api/disassembly")
    assert disasm_res.status_code == 200
    items = disasm_res.json()
    assert len(items) >= 2
    assert "addi x1, x0, 42" in items[0]["mnemonic"]

    # Read memory
    mem_res = client.get("/api/memory?address=536870912&length=32")
    assert mem_res.status_code == 200
    rows = mem_res.json()["rows"]
    assert len(rows) == 2


def test_web_api_peripherals_interaction():
    # GPIO pin input toggle
    gpio_res = client.post("/api/gpio/input", json={"pin": 3, "high": True})
    assert gpio_res.status_code == 200
    assert gpio_res.json()["state"] is True

    # UART send and read
    uart_send = client.post("/api/uart/send", json={"data": "PING"})
    assert uart_send.status_code == 200

    uart_read = client.get("/api/uart/read")
    assert uart_read.status_code == 200
    assert "output" in uart_read.json()

    # OLED pixels
    oled_res = client.get("/api/oled/pixels")
    assert oled_res.status_code == 200
    pixels = oled_res.json()
    assert len(pixels) == 64
    assert len(pixels[0]) == 128


def test_web_api_adc_channel():
    res = client.post("/api/adc/channel", json={"channel": 1, "millivolts": 1650})
    assert res.status_code == 200
    data = res.json()
    assert data["channel"] == 1
    assert data["millivolts"] == 1650
    assert data["voltage"] == 1.65
    assert data["status"]["adc"]["channels"][1]["millivolts"] == 1650


def test_web_api_editor_flash():
    # Valid source
    code = "addi x1, x0, 123\nloop:\nj loop\n"
    res = client.post("/api/editor/flash", json={"source": code})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["bytes_flashed"] >= 8
    assert "loop" in data["symbols"]

    # Invalid source
    bad_res = client.post("/api/editor/flash", json={"source": "invalid_op x1, 2"})
    assert bad_res.status_code == 400


def test_web_api_waveform():
    client.post("/api/step")
    res = client.get("/api/waveform")
    assert res.status_code == 200
    samples = res.json()["samples"]
    assert len(samples) > 0
    sample = samples[-1]
    assert "cycle" in sample
    assert "pc" in sample
    assert "addr" in sample
    assert "we" in sample
    assert "pa5" in sample
    assert "tx" in sample
    assert "adc" in sample

