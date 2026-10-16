"""Unit and integration tests for the BoardLens Typer CLI."""

from pathlib import Path
import pytest
from typer.testing import CliRunner
from boardlens.cli.main import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "BoardLens version" in result.stdout


def test_cli_info():
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "BoardLens Memory Map" in result.stdout
    assert "Flash ROM" in result.stdout
    assert "SRAM" in result.stdout


def test_cli_asm_and_disasm(tmp_path):
    src_file = tmp_path / "simple.s"
    src_file.write_text("addi x1, x0, 42\nebreak\n", encoding="utf-8")
    bin_file = tmp_path / "simple.bin"

    asm_res = runner.invoke(app, ["asm", str(src_file), "-o", str(bin_file)])
    assert asm_res.exit_code == 0
    assert "Successfully assembled" in asm_res.stdout
    assert bin_file.exists()

    disasm_res = runner.invoke(app, ["disasm", str(bin_file)])
    assert disasm_res.exit_code == 0
    assert "addi x1, x0, 42" in disasm_res.stdout
    assert "ebreak" in disasm_res.stdout


def test_cli_run(tmp_path):
    src_file = tmp_path / "test.s"
    src_file.write_text("addi x1, x0, 10\nebreak\n", encoding="utf-8")
    vcd_file = tmp_path / "trace.vcd"

    run_res = runner.invoke(app, ["run", str(src_file), "--cycles", "100", "--trace", str(vcd_file)])
    assert run_res.exit_code == 0
    assert "Execution halted" in run_res.stdout
    assert "TRAP BREAKPOINT" in run_res.stdout
    assert vcd_file.exists()
