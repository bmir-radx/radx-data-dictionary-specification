"""Tests for the high-level object model (DataDictionary / DataElement)."""

import io

import pytest
import yaml

from dd_converter import (
    DataDictionary,
    DataElement,
    ReadError,
    UnknownDatatypeError,
    emit_schema,
    read_data_dictionary,
)
from dd_converter.grammar import ParseError

HEADER = (
    "Id,Aliases,Label,Description,Section,Cardinality,Terms,Datatype,"
    "Pattern,Unit,Enumeration,MissingValueCodes,Examples,Notes,Provenance,SeeAlso"
)

FULL_ROW = (
    'age,years_old|age_years,Age,Age in years,Demographics,single,'
    'http://purl.obolibrary.org/obo/NCIT_C25150,integer,'
    '^[0-9]+$,year,,"""-1""=[Refused]",42|7,Some notes,From intake form,'
    'https://example.org/age'
)


def _load(text, **kwargs):
    return DataDictionary.load(io.StringIO(text), **kwargs)


# --- element parsing ---------------------------------------------------------

def test_every_field_parses():
    dd = _load(f"{HEADER}\n{FULL_ROW}\n")
    element = dd["age"]
    assert element.id == "age"
    assert element.label == "Age"
    assert element.aliases == ("years_old", "age_years")
    assert element.description == "Age in years"
    assert element.section == "Demographics"
    assert element.cardinality == "single"
    assert element.terms == ("http://purl.obolibrary.org/obo/NCIT_C25150",)
    assert element.datatype == "integer"
    assert element.pattern == "^[0-9]+$"
    assert element.unit == "year"
    assert element.enumeration == ()
    assert [c.value for c in element.missing_value_codes] == ["-1"]
    assert element.missing_value_codes[0].label == "Refused"
    assert element.examples == ("42", "7")
    assert element.notes == "Some notes"
    assert element.provenance == "From intake form"
    assert element.see_also == "https://example.org/age"
    assert element.line == 2
    assert element.row is not None and element.row.id == "age"


def test_blank_optional_cells_become_none_or_empty():
    dd = _load("Id,Label,Datatype\nq,Q,string\n")
    element = dd["q"]
    assert element.description is None
    assert element.section is None
    assert element.pattern is None
    assert element.unit is None
    assert element.unit_of_measure is None
    assert element.notes is None
    assert element.provenance is None
    assert element.see_also is None
    assert element.aliases == ()
    assert element.terms == ()
    assert element.enumeration == ()
    assert element.missing_value_codes == ()
    assert element.examples == ()


def test_enumeration_parsed_into_items():
    dd = _load(
        'Id,Label,Datatype,Enumeration\n'
        'q,Q,integer,"""0""=[No] | ""1""=[Yes](http://example.org/yes)"\n'
    )
    enumeration = dd["q"].enumeration
    assert [(c.value, c.label) for c in enumeration] == [("0", "No"), ("1", "Yes")]
    assert enumeration[0].iri is None
    assert enumeration[1].iri == "http://example.org/yes"
    assert dd["q"].is_enumerated


def test_unit_of_measure_resolved_from_builtin_table():
    dd = _load("Id,Label,Datatype,Unit\nheight,Height,decimal,cm\nmass,Mass,decimal,kg\n")
    assert dd["height"].unit == "cm"
    assert dd["height"].unit_of_measure is None  # cm is not in the spec's table
    assert dd["mass"].unit_of_measure.descriptive_name == "kilogram"
    assert dd["mass"].unit_of_measure.ucum_code == "kg"


# --- cardinality -------------------------------------------------------------

@pytest.mark.parametrize(
    "cell, expected",
    [("", "single"), ("single", "single"), ("multiple", "multiple"), ("Multiple", "multiple")],
)
def test_cardinality_values(cell, expected):
    dd = _load(f"Id,Label,Datatype,Cardinality\nq,Q,string,{cell}\n")
    assert dd["q"].cardinality == expected
    assert dd["q"].is_multiple == (expected == "multiple")


def test_invalid_cardinality_raises_with_line():
    with pytest.raises(ReadError, match="Line 2.*many"):
        _load("Id,Label,Datatype,Cardinality\nq,Q,string,many\n")


# --- fail-fast errors --------------------------------------------------------

def test_unknown_datatype_raises_with_line_and_cause():
    with pytest.raises(ReadError, match="Line 3") as excinfo:
        _load("Id,Label,Datatype\na,A,string\nb,B,notatype\n")
    assert isinstance(excinfo.value.__cause__, UnknownDatatypeError)


def test_malformed_enumeration_raises_with_line_and_cause():
    with pytest.raises(ReadError, match="Line 2") as excinfo:
        _load('Id,Label,Datatype,Enumeration\nq,Q,integer,"""0""=[No] | garbage"\n')
    assert isinstance(excinfo.value.__cause__, ParseError)


def test_duplicate_id_raises_unless_allowed():
    text = "Id,Label,Datatype\na,A,string\na,A2,integer\n"
    with pytest.raises(ReadError, match="duplicate"):
        _load(text)
    dd = _load(text, allow_duplicates=True)
    assert dd.ids == ("a",)


# --- collection protocol -----------------------------------------------------

def test_collection_protocol():
    dd = _load("Id,Label,Datatype\na,A,string\nb,B,integer\n")
    assert len(dd) == 2
    assert [e.id for e in dd] == ["a", "b"]
    assert "a" in dd and "zzz" not in dd
    assert dd["b"].datatype == "integer"
    assert dd.get("zzz") is None
    assert dd.ids == ("a", "b")
    assert [e.id for e in dd.elements] == ["a", "b"]
    assert repr(dd) == "DataDictionary(2 elements)"


def test_missing_id_raises_helpful_keyerror():
    dd = _load("Id,Label,Datatype\na,A,string\n")
    with pytest.raises(KeyError, match="no data element with id 'zzz'"):
        dd["zzz"]


# --- sections ----------------------------------------------------------------

def test_sections_in_first_appearance_order():
    dd = _load(
        "Id,Label,Datatype,Section\n"
        "a,A,string,Two\n"
        "b,B,string,One\n"
        "c,C,string,Two\n"
        "d,D,string,\n"
    )
    assert dd.sections == ("Two", "One")
    assert [e.id for e in dd.elements_in_section("Two")] == ["a", "c"]
    assert [e.id for e in dd.elements_in_section(None)] == ["d"]


# --- conversion --------------------------------------------------------------

def test_to_linkml_matches_emit_schema():
    text = f"{HEADER}\n{FULL_ROW}\n"
    dd = _load(text)
    expected = emit_schema(read_data_dictionary(io.StringIO(text)))
    assert dd.to_linkml() == expected
    schema = yaml.safe_load(dd.to_linkml())
    assert "age" in schema["classes"]["Record"]["attributes"]


def test_to_linkml_refuses_handbuilt_elements():
    dd = DataDictionary([DataElement(id="x", label="X", datatype="string")])
    with pytest.raises(ValueError, match="hand-built"):
        dd.to_linkml()


def test_from_rows_equivalent_to_load():
    text = "Id,Label,Datatype\na,A,string\n"
    via_rows = DataDictionary.from_rows(read_data_dictionary(io.StringIO(text)))
    via_load = _load(text)
    assert via_rows.ids == via_load.ids
    assert via_rows["a"].label == via_load["a"].label
