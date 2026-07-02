"""Tests for the command-line interface."""

from pathlib import Path

import pytest
import yaml

from radx_dd_converter.cli import _class_from_name, _name_from_filename, main

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"


# --- filename / name derivation --------------------------------------------

@pytest.mark.parametrize(
    "filename, expected_name",
    [
        ("gcb.dd.csv", "gcb"),  # .dd suffix stripped
        ("patient_data.csv", "patient_data"),
        ("My Data.CSV", "my_data"),
        ("weird-name.tsv", "weird_name"),
    ],
)
def test_name_from_filename(filename, expected_name):
    assert _name_from_filename(Path(filename)) == expected_name


@pytest.mark.parametrize(
    "name, expected_class",
    [
        ("gcb", "Gcb"),
        ("patient_data", "PatientData"),
    ],
)
def test_class_from_name(name, expected_class):
    assert _class_from_name(name) == expected_class


# --- run behavior ----------------------------------------------------------

def test_writes_output_file_with_filename_defaults(tmp_path, capsys):
    out = tmp_path / "out.yaml"
    rc = main([str(FIXTURE), "-o", str(out)])
    assert rc == 0
    schema = yaml.safe_load(out.read_text())
    assert schema["name"] == "sample"
    assert schema["id"] == "https://w3id.org/radx/sample"
    assert list(schema["classes"]) == ["Sample"]  # CamelCase of "sample"


def test_flags_override_defaults(tmp_path):
    out = tmp_path / "out.yaml"
    rc = main(
        [
            str(FIXTURE),
            "-o",
            str(out),
            "--name",
            "custom",
            "--id",
            "https://example.org/custom",
            "--class-name",
            "Thing",
        ]
    )
    assert rc == 0
    schema = yaml.safe_load(out.read_text())
    assert schema["name"] == "custom"
    assert schema["id"] == "https://example.org/custom"
    assert list(schema["classes"]) == ["Thing"]


def test_output_to_stdout_by_default(capsys):
    rc = main([str(FIXTURE)])
    assert rc == 0
    out = capsys.readouterr().out
    schema = yaml.safe_load(out)
    assert "Record" in schema["classes"] or "Sample" in schema["classes"]


def test_missing_input_returns_2(capsys):
    rc = main(["/no/such/file.csv"])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_malformed_dictionary_reports_cleanly(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("Id,Label,Datatype\nA,Label A,\n")  # blank required Datatype
    rc = main([str(bad)])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_duplicate_id_fails_but_allow_duplicates_succeeds(tmp_path, capsys):
    dup = tmp_path / "dup.csv"
    dup.write_text(
        "Id,Label,Datatype\nA,First,string\nA,Second,integer\n"
    )
    # Without the flag: clean error, exit 1.
    assert main([str(dup)]) == 1
    assert "duplicate Id" in capsys.readouterr().err
    # With the flag: succeeds.
    out = tmp_path / "out.yaml"
    assert main([str(dup), "-o", str(out), "--allow-duplicates"]) == 0
    schema = yaml.safe_load(out.read_text())
    attrs = list(schema["classes"].values())[0]["attributes"]
    assert list(attrs) == ["A"]  # duplicate collapsed to the first occurrence
