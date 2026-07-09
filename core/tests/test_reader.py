"""Tests for the data dictionary CSV reader."""

import io
from pathlib import Path

import pytest
from dd_core import ReadError, read_data_dictionary

FIXTURES = Path(__file__).parent / "fixtures"


def _read_str(text: str):
    return read_data_dictionary(io.StringIO(text))


def test_reads_fixture_in_order():
    rows = read_data_dictionary(FIXTURES / "sample.csv")
    assert [r.id for r in rows] == ["PartId", "SampleType", "Symptoms"]
    # Row order is significant and must be preserved.
    assert rows[0].get("Label") == "Participant Id"
    assert rows[0].get("Pattern") == r"^[NP](\d+)$"


def test_quoted_enumeration_cell_survives_rfc4180():
    rows = read_data_dictionary(FIXTURES / "sample.csv")
    sample_type = rows[1]
    # The doubled quotes in the CSV collapse to a single cell containing the
    # enumeration grammar verbatim.
    assert sample_type.get("Enumeration") == (
        '"0"=[Saliva](UBERON:0001836) | "1"=[Blood](UBERON:0000178)'
    )


def test_blank_optional_cell_is_empty_string():
    rows = _read_str(
        "Id,Label,Datatype,Description\n"
        "A,Label A,string,\n"
    )
    assert rows[0].get("Description") == ""


def test_utf8_bom_is_stripped_from_first_header():
    # Excel's "CSV UTF-8" writes a BOM; the Id column must still be found.
    rows = _read_str("﻿Id,Label,Datatype\nA,Label A,string\n")
    assert rows[0].id == "A"


def test_extra_columns_are_preserved():
    rows = _read_str(
        "Id,Label,Datatype,CustomThing\n"
        "A,Label A,string,hello\n"
    )
    assert rows[0].extra_columns == ("CustomThing",)
    assert rows[0].get("CustomThing") == "hello"


def test_wholly_blank_lines_are_skipped():
    rows = _read_str(
        "Id,Label,Datatype\n"
        "A,Label A,string\n"
        ",,\n"
        "B,Label B,integer\n"
    )
    assert [r.id for r in rows] == ["A", "B"]


def test_missing_required_header_raises():
    with pytest.raises(ReadError, match="Missing required column"):
        _read_str("Id,Label\nA,Label A\n")


def test_blank_required_cell_raises():
    with pytest.raises(ReadError, match="required column 'Datatype' is blank"):
        _read_str("Id,Label,Datatype\nA,Label A,\n")


def test_duplicate_id_raises():
    with pytest.raises(ReadError, match="duplicate Id 'A'"):
        _read_str(
            "Id,Label,Datatype\n"
            "A,Label A,string\n"
            "A,Label A2,integer\n"
        )


def test_allow_duplicates_keeps_first_skips_rest():
    rows = read_data_dictionary(
        io.StringIO(
            "Id,Label,Datatype\n"
            "A,First A,string\n"
            "B,Label B,integer\n"
            "A,Second A,integer\n"
        ),
        allow_duplicates=True,
    )
    # First occurrence kept, later duplicate skipped; order preserved.
    assert [r.id for r in rows] == ["A", "B"]
    assert rows[0].get("Label") == "First A"


def test_duplicate_header_raises():
    with pytest.raises(ReadError, match="Duplicate column header"):
        _read_str("Id,Label,Datatype,Label\nA,x,string,y\n")


def test_empty_file_raises():
    with pytest.raises(ReadError, match="empty"):
        _read_str("")
