"""Unit tests for the VCDTracer."""

import pytest
from boardlens.tooling.vcd import VCDTracer


def test_vcd_tracer_generation(tmp_path):
    vcd = VCDTracer(timescale="1ns")
    vcd.register_signal("clk", width=1, initial_value=0)
    vcd.register_signal("pc", width=32, initial_value=0x00000000)
    vcd.register_signal("bus_we", width=1, initial_value=0)

    # Time 10ns
    vcd.set_time(10)
    vcd.change("clk", 1)
    vcd.change("pc", 0x00000004)

    # Time 20ns
    vcd.set_time(20)
    vcd.change("clk", 0)

    # Time 30ns
    vcd.set_time(30)
    vcd.change("clk", 1)
    vcd.change("bus_we", 1)

    output = vcd.generate()
    assert "$timescale" in output
    assert "1ns" in output
    assert "$var wire 1" in output
    assert "$var wire 32" in output
    assert "$dumpvars" in output
    assert "#10" in output
    assert "#20" in output
    assert "#30" in output

    filepath = tmp_path / "test.vcd"
    vcd.write_to_file(str(filepath))
    assert filepath.exists()
    assert filepath.read_text(encoding="utf-8") == output
