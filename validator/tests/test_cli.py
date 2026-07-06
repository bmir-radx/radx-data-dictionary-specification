"""Tests for the command-line interface."""

import json

from dd_validator.cli import main

CLEAN = "Id,Label,Datatype\nage,Age,integer\n"
DIRTY = "Id,Label,Datatype\nage,Age,Nope\n"  # unknown datatype -> ERROR


def test_clean_exits_zero(tmp_path, capsys):
    p = tmp_path / "clean.csv"
    p.write_text(CLEAN)
    assert main([str(p)]) == 0
    assert "0 error(s)" in capsys.readouterr().err


def test_errors_exit_one(tmp_path, capsys):
    p = tmp_path / "dirty.csv"
    p.write_text(DIRTY)
    assert main([str(p)]) == 1
    assert "unknown-datatype" in capsys.readouterr().out


def test_exit_zero_flag_overrides(tmp_path):
    p = tmp_path / "dirty.csv"
    p.write_text(DIRTY)
    assert main([str(p), "--exit-zero"]) == 0


def test_missing_input_exits_two(capsys):
    assert main(["/no/such/file.csv"]) == 2
    assert "not found" in capsys.readouterr().err


def test_json_output_to_file(tmp_path):
    p = tmp_path / "dirty.csv"
    p.write_text(DIRTY)
    out = tmp_path / "report.json"
    main([str(p), "-o", str(out), "-f", "json"])
    payload = json.loads(out.read_text())
    assert payload["findings"][0]["check"] == "unknown-datatype"


def test_levels_filter(tmp_path, capsys):
    # A row with only a label warning; filtering to ERROR should hide it.
    p = tmp_path / "warn.csv"
    p.write_text("Id,Label,Datatype\nage,,integer\n")
    assert main([str(p), "--levels", "ERROR"]) == 0
    assert capsys.readouterr().out == ""


def test_no_duplicate_check_flag(tmp_path, capsys):
    p = tmp_path / "dup.csv"
    p.write_text("Id,Label,Datatype\na,A,integer\na,A2,integer\n")
    assert main([str(p), "--no-duplicate-check"]) == 0
    out = capsys.readouterr().out
    assert "duplicate-id" not in out


def test_directory_input(tmp_path, capsys):
    (tmp_path / "a.csv").write_text(CLEAN)
    (tmp_path / "b.csv").write_text(DIRTY)
    rc = main([str(tmp_path), "-f", "csv"])
    out = capsys.readouterr().out
    assert rc == 1
    # One header row shared across both files' sections.
    assert out.count("File,Row,Level,Check,Message,Value") == 1
    assert "unknown-datatype" in out
