"""Tests for the high-level object model (DataDictionary / DataElement)."""

import io

import pytest
import yaml
from dd_api import DataDictionary, DataElement, ReadError
from dd_converter import UnknownDatatypeError, emit_schema, read_data_dictionary
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
    assert element.resolved_unit is None
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


def test_resolved_unit_from_builtin_table():
    dd = _load("Id,Label,Datatype,Unit\nheight,Height,decimal,cm\nmass,Mass,decimal,kg\n")
    assert dd["height"].unit == "cm"
    assert dd["height"].resolved_unit is None  # cm is not in the spec's table
    assert dd["mass"].resolved_unit.descriptive_name == "kilogram"
    assert dd["mass"].resolved_unit.ucum_code == "kg"


# --- cardinality -------------------------------------------------------------

@pytest.mark.parametrize(
    "cell, expected",
    [("", "single"), ("single", "single"), ("multiple", "multiple"), ("Multiple", "multiple")],
)
def test_cardinality_values(cell, expected):
    dd = _load(f"Id,Label,Datatype,Cardinality\nq,Q,string,{cell}\n")
    assert dd["q"].cardinality == expected
    assert dd["q"].is_multivalued == (expected == "multiple")


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


def test_membership_accepts_elements_and_ids():
    dd = _load("Id,Label,Datatype\na,A,string\n")
    element = dd["a"]
    assert element in dd            # membership by the element's id
    assert all(e in dd for e in dd)
    other = DataElement(id="zzz", label="Z", datatype="string")
    assert other not in dd


def test_elements_are_hashable_and_content_equal():
    text = "Id,Label,Datatype\na,A,string\n"
    first, second = _load(text)["a"], _load(text)["a"]
    assert first == second           # same content -> equal...
    assert hash(first) == hash(second)
    assert {first, second} == {first}  # ...and usable in sets


def test_equality_ignores_provenance():
    # The same element content on different lines still compares equal.
    a = _load("Id,Label,Datatype\nx,X,string\n")["x"]           # line 2
    b = _load("Id,Label,Datatype\nother,O,string\nx,X,string\n")["x"]  # line 3
    assert a.line != b.line
    assert a == b


def test_constructor_rejects_duplicate_ids():
    element = DataElement(id="a", label="A", datatype="string")
    with pytest.raises(ValueError, match="duplicate data element id 'a'"):
        DataDictionary([element, element])


def test_hand_built_element_has_no_provenance():
    element = DataElement(id="x", label="X", datatype="string")
    assert element.line is None
    assert element.row is None


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


def test_to_linkml_works_for_handbuilt_elements():
    dd = DataDictionary([DataElement(id="x", label="X", datatype="string")])
    reloaded = DataDictionary.from_linkml(io.StringIO(dd.to_linkml()))
    assert reloaded["x"].label == "X"


def test_from_rows_equivalent_to_load():
    text = "Id,Label,Datatype\na,A,string\n"
    via_rows = DataDictionary.from_rows(read_data_dictionary(io.StringIO(text)))
    via_load = _load(text)
    assert via_rows.ids == via_load.ids
    assert via_rows["a"].label == via_load["a"].label


def test_from_rows_accepts_plain_mappings():
    # schema_to_rows (LinkML -> rows) returns plain dicts, not Row objects.
    dd = DataDictionary.from_rows(
        [
            {"Id": "a", "Label": "A", "Datatype": "string"},
            {"Id": "b", "Label": "B", "Datatype": "integer", "Cardinality": "multiple"},
        ]
    )
    assert dd.ids == ("a", "b")
    assert dd["b"].is_multivalued
    assert dd["a"].line == 2 and dd["b"].line == 3  # as if rows of a CSV


def test_from_rows_round_trips_a_generated_schema():
    from dd_converter import schema_to_rows

    # Use an enumerated element: the emitter only represents MissingValueCodes
    # for enumerated fields (folded into the enum union), so only those
    # round-trip through a generated schema.
    text = (
        "Id,Label,Datatype,Enumeration,MissingValueCodes\n"
        'q,Q,integer,"""0""=[No] | ""1""=[Yes]","""-1""=[Refused]"\n'
    )
    schema = yaml.safe_load(emit_schema(read_data_dictionary(io.StringIO(text))))
    dd = DataDictionary.from_rows(schema_to_rows(schema))
    assert dd.ids == ("q",)
    assert dd["q"].label == "Q"
    assert [c.value for c in dd["q"].enumeration] == ["0", "1"]
    assert [c.value for c in dd["q"].missing_value_codes] == ["-1"]


# --- from_linkml -------------------------------------------------------------

def test_from_linkml_accepts_path_stream_and_dict(tmp_path):
    original = _load(f"{HEADER}\n{FULL_ROW}\n")
    schema_yaml = original.to_linkml()

    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(schema_yaml)

    for source in (schema_path, io.StringIO(schema_yaml), yaml.safe_load(schema_yaml)):
        dd = DataDictionary.from_linkml(source)
        assert dd.ids == ("age",)
        assert dd["age"].label == "Age"
        assert dd["age"].aliases == ("years_old", "age_years")


def test_from_linkml_matches_from_rows_route():
    from dd_converter import schema_to_rows

    schema = yaml.safe_load(_load(f"{HEADER}\n{FULL_ROW}\n").to_linkml())
    assert (
        DataDictionary.from_linkml(schema).elements
        == DataDictionary.from_rows(schema_to_rows(schema)).elements
    )


def test_from_linkml_recovers_renamed_ranges():
    # dateTime/anyURI have LinkML ranges spelled differently (datetime, uri);
    # the loader must map them back to the spec names.
    dd = _load("Id,Label,Datatype\nwhen,When,dateTime\nlink,Link,anyURI\n")
    back = DataDictionary.from_linkml(io.StringIO(dd.to_linkml()))
    assert [(e.id, e.datatype) for e in back] == [("when", "dateTime"), ("link", "anyURI")]


# --- to_csv ------------------------------------------------------------------

def test_to_csv_round_trips_semantically():
    text = (
        "Id,Label,Datatype,Cardinality,Enumeration\n"
        'q,Q,integer,,"""0""=[No] | ""1""=[Yes](http://example.org/yes)"\n'
        "r,R,string,multiple,\n"
    )
    original = _load(text)
    reloaded = DataDictionary.load(io.StringIO(original.to_csv()))
    # Equality is by content (provenance excluded), so this is a real check.
    assert reloaded.elements == original.elements


def test_to_csv_canonical_form():
    dd = _load("Id,Label,Datatype,Cardinality\nq,Q,string,\n")
    lines = dd.to_csv().splitlines()
    assert lines[0].startswith("Id,Aliases,Label,")  # spec column order
    assert ",single," in lines[1]  # blank cardinality written explicitly


def test_to_csv_serialises_enumeration_notation():
    import csv

    dd = _load(
        'Id,Label,Datatype,Enumeration\n'
        'q,Q,integer,"""0""=[No] | ""1""=[Yes](http://example.org/yes)"\n'
    )
    (row,) = list(csv.DictReader(io.StringIO(dd.to_csv())))
    assert row["Enumeration"] == '"0"=[No] | "1"=[Yes](http://example.org/yes)'


def test_to_csv_works_for_hand_built_elements():
    dd = DataDictionary([DataElement(id="x", label="X", datatype="string")])
    reloaded = DataDictionary.load(io.StringIO(dd.to_csv()))
    assert reloaded["x"].label == "X"
    assert reloaded["x"].datatype == "string"


# --- precondition / required ---------------------------------------------------

def test_precondition_and_required_parse():
    dd = _load(
        "Id,Label,Datatype,Precondition,Required\n"
        "smoker,Smoker,integer,,y\n"
        'packs,Packs,decimal,"smoker = ""1""",y\n'
        "age,Age,integer,,\n"
    )
    assert dd["smoker"].precondition is None and dd["smoker"].required
    assert dd["packs"].precondition == 'smoker = "1"'
    assert dd["packs"].required
    assert not dd["age"].required
    from dd_converter.grammar import Comparison
    assert dd["packs"].parsed_precondition == Comparison("smoker", "=", "1")
    assert dd["age"].parsed_precondition is None


def test_malformed_precondition_raises_with_line():
    from dd_converter.grammar import ParseError
    with pytest.raises(ReadError, match="Line 2") as excinfo:
        _load("Id,Label,Datatype,Precondition\nx,X,integer,datediff(a) > 3\n")
    assert isinstance(excinfo.value.__cause__, ParseError)


def test_invalid_required_raises():
    with pytest.raises(ReadError, match="Required 'maybe'"):
        _load("Id,Label,Datatype,Required\nx,X,integer,maybe\n")


def test_precondition_round_trips_via_csv_and_linkml():
    text = (
        "Id,Label,Datatype,Precondition,Required\n"
        "smoker,Smoker,integer,,\n"
        'packs,Packs,decimal,"smoker = ""1"" and smoker <> """"",y\n'
    )
    original = _load(text)
    via_csv = DataDictionary.load(io.StringIO(original.to_csv()))
    assert via_csv.elements == original.elements
    via_linkml = DataDictionary.from_linkml(io.StringIO(original.to_linkml()))
    assert via_linkml["packs"].precondition == original["packs"].precondition
    assert via_linkml["packs"].required
