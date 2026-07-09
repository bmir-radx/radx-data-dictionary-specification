"""Tests for the dd-json command-line interface."""

import io
import json

from dd_api import DataDictionary
from dd_api.cli import _detect, main

CSV = "Id,Label,Datatype\nage,Age,integer\nsex,Sex,string\n"


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


# --- input detection ---------------------------------------------------------

def test_detect_formats():
    assert _detect(CSV) == "csv"
    assert _detect('{"format": "dd-json", "version": 1, "elements": []}') == "json"
    assert _detect("classes:\n  Record:\n    tree_root: true\n") == "linkml"


# --- output formats ----------------------------------------------------------

def test_csv_to_json_stdout(tmp_path, capsys):
    src = _write(tmp_path, "d.csv", CSV)
    assert main([str(src)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "dd-json"
    assert [e["id"] for e in payload["elements"]] == ["age", "sex"]


def test_output_to_file_and_format_flag(tmp_path, capsys):
    src = _write(tmp_path, "d.csv", CSV)
    out = tmp_path / "d.yaml"
    assert main([str(src), "-o", str(out), "--format", "linkml"]) == 0
    assert "age:" in out.read_text()
    assert "2 data elements" in capsys.readouterr().err


def test_json_input_detected_and_reconverted(tmp_path):
    # CSV -> dd-json, then dd-json -> CSV: the CLI detects dd-json input.
    dd_json = DataDictionary.load(io.StringIO(CSV)).to_json()
    src = _write(tmp_path, "d.json", dd_json)
    out = tmp_path / "back.csv"
    assert main([str(src), "--format", "csv", "-o", str(out)]) == 0
    assert DataDictionary.load(out).ids == ("age", "sex")


def test_linkml_input_detected(tmp_path):
    schema = DataDictionary.load(io.StringIO(CSV)).to_linkml()
    src = _write(tmp_path, "s.yaml", schema)
    out = tmp_path / "d.json"
    assert main([str(src), "-o", str(out)]) == 0
    assert DataDictionary.from_json(out.read_text()).ids == ("age", "sex")


# --- errors ------------------------------------------------------------------

def test_missing_input_returns_2(capsys):
    assert main(["/no/such/file.csv"]) == 2
    assert "not found" in capsys.readouterr().err


def test_malformed_input_returns_1(tmp_path, capsys):
    bad = _write(tmp_path, "bad.csv", "Id,Label,Datatype\nage,Age,Nope\n")
    assert main([str(bad)]) == 1
    assert "error:" in capsys.readouterr().err
