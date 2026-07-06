"""Tests for report rendering."""

import json

from dd_validator.model import Finding, Level
from dd_validator.report import render

FINDINGS = [
    Finding(Level.ERROR, "unknown-datatype", "'Nope' is not a known datatype name",
            line=3, column="Datatype", value="Nope"),
    Finding(Level.WARNING, "label-missing", "Label is missing", line=2, column="Label"),
]


def test_text_format():
    out = render(FINDINGS, "text", file="d.csv")
    assert "d.csv:3: ERROR unknown-datatype — 'Nope' is not a known datatype name" in out
    assert "d.csv:2: WARNING label-missing" in out


def test_text_format_empty():
    assert render([], "text", file="d.csv") == ""


def test_csv_header_and_rows_agree():
    out = render(FINDINGS, "csv", file="d.csv")
    lines = out.strip().splitlines()
    header = lines[0].split(",")
    first_row = lines[1].split(",")
    assert header == ["File", "Row", "Level", "Check", "Message", "Value"]
    assert len(first_row) == len(header)  # no phantom column (unlike the Java writer)


def test_tsv_is_tab_delimited():
    out = render(FINDINGS, "tsv", file="d.csv")
    assert "\t" in out.splitlines()[0]


def test_json_format():
    out = render(FINDINGS, "json", file="d.csv")
    payload = json.loads(out)
    assert payload["file"] == "d.csv"
    assert payload["findings"][0]["check"] == "unknown-datatype"
    assert payload["findings"][0]["line"] == 3


def test_unknown_format_raises():
    try:
        render(FINDINGS, "xml")
    except ValueError as exc:
        assert "xml" in str(exc)
    else:
        raise AssertionError("expected ValueError")
