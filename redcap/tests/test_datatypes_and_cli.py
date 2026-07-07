"""Datatype-mapping and CLI tests."""

import io

import pytest
from dd_api import DataDictionary
from dd_redcap import convert_redcap
from dd_redcap.cli import main

_HEADER = "Variable,Label,Type,Field Note,Text Validation\n"


def _element(validation, note=""):
    text = _HEADER + f"f,F,text,{note},{validation}\n"
    return convert_redcap(io.StringIO(text))["f"]


@pytest.mark.parametrize(
    "validation, expected",
    [
        ("integer", "integer"),
        ("number", "decimal"),
        ("number_2dp", "decimal"),
        ("date_ymd", "date"),
        ("date_mdy", "date_mdy"),
        ("date_dmy", "date_dmy"),
        ("datetime_seconds_ymd", "dateTime"),
        ("time", "time"),
        ("time_hh_mm_ss", "time"),
        ("email", "string"),
        ("zipcode", "string"),
        ("phone", "string"),
        ("", "string"),
        ("something_unknown", "string"),
    ],
)
def test_validation_datatype_mapping(validation, expected):
    assert _element(validation).datatype == expected


def test_text_validation_with_us_date_note():
    assert _element("text", note="MM/DD/YYYY").datatype == "date_mdy"


def test_every_mapped_datatype_is_valid_in_the_model():
    # Round-trip guarantee: whatever the table maps to must load.
    from dd_redcap.datatypes import VALIDATION_DATATYPES

    for name in set(VALIDATION_DATATYPES.values()):
        dd = DataDictionary.from_rows([{"Id": "x", "Label": "X", "Datatype": name}])
        assert dd["x"].datatype == name


# --- CLI ----------------------------------------------------------------------

REDCAP_SAMPLE = 'Variable,Label,Type,Choices\nsex,Sex,radio,"1, Male | 2, Female"\n'


def test_cli_writes_output_file(tmp_path, capsys):
    src = tmp_path / "redcap.csv"
    src.write_text(REDCAP_SAMPLE)
    out = tmp_path / "dd.csv"
    assert main([str(src), "-o", str(out), "--provenance", "Study X"]) == 0
    dd = DataDictionary.load(out)
    assert dd["sex"].provenance == "Study X"
    assert [c.label for c in dd["sex"].enumeration] == ["Male", "Female"]
    assert "1 data elements" in capsys.readouterr().err


def test_cli_stdout_by_default(tmp_path, capsys):
    src = tmp_path / "redcap.csv"
    src.write_text(REDCAP_SAMPLE)
    assert main([str(src)]) == 0
    assert capsys.readouterr().out.startswith("Id,Aliases,Label,")


def test_cli_missing_input_exits_two(capsys):
    assert main(["/no/such/file.csv"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_non_redcap_input_exits_one(tmp_path, capsys):
    src = tmp_path / "notredcap.csv"
    src.write_text("Id,Label,Datatype\na,A,string\n")
    assert main([str(src)]) == 1
    assert "error:" in capsys.readouterr().err
