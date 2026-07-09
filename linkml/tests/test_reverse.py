"""Round-trip tests: CSV -> LinkML -> CSV should be semantically equivalent."""

import io
from pathlib import Path

import pytest
from dd_core import read_data_dictionary
from dd_core.grammar import parse_enumeration, parse_terms
from dd_linkml import EmitOptions, emit_schema, schema_to_csv

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

# A small dictionary exercising the tricky columns: an enumeration (with an
# ontology meaning), a multivalued field, a datatype, terms, unit, section,
# aliases, examples, and a field-specific missing-value code.
SAMPLE = (
    "Id,Label,Description,Section,Cardinality,Terms,Datatype,Pattern,Unit,"
    "Enumeration,MissingValueCodes,Notes,Provenance,SeeAlso,Aliases,Examples\n"
    "part_id,Participant,The participant,IDs,single,,string,^[NP]\\d+$,,,,note1,,,"
    "pid|subject_id,N001|N002\n"
    'sample,Sample Type,The sample,Lab,single,UBERON:0001836,integer,,,'
    '"""0""=[Saliva](UBERON:0001836) | ""1""=[Blood]",'
    '"""-1""=[Refused]",,,,,\n'
    "height,Height,The height,Lab,single,,decimal,,mm,,,,,,,\n"
)


def _norm(s):
    return " ".join((s or "").split())


def _roundtrip(csv_text):
    orig = read_data_dictionary(io.StringIO(csv_text))
    schema = emit_schema(orig, EmitOptions(schema_name="s", class_name="Record"))
    rebuilt = read_data_dictionary(io.StringIO(schema_to_csv(schema)))
    return orig, rebuilt


def test_roundtrip_preserves_all_ids():
    orig, rebuilt = _roundtrip(SAMPLE)
    assert [r.id for r in orig] == [r.id for r in rebuilt]


def test_roundtrip_semantic_equivalence():
    orig, rebuilt = _roundtrip(SAMPLE)
    o = {r.id: r for r in orig}
    b = {r.id: r for r in rebuilt}
    columns = [
        "Id", "Label", "Description", "Section", "Pattern", "Unit", "Datatype",
        "Notes", "Provenance", "SeeAlso", "Aliases", "Examples",
    ]
    for rid in o:
        for col in columns:
            assert _norm(o[rid].get(col)) == _norm(b[rid].get(col)), (rid, col)
        # Cardinality: blank and "single" are equivalent (single is the default).
        assert (_norm(o[rid].get("Cardinality")) or "single") == (
            _norm(b[rid].get("Cardinality")) or "single"
        )
        # Enumeration / Terms compared as parsed structures, not raw text.
        assert parse_enumeration(o[rid].get("Enumeration")) == parse_enumeration(
            b[rid].get("Enumeration")
        )
        assert parse_enumeration(o[rid].get("MissingValueCodes")) == parse_enumeration(
            b[rid].get("MissingValueCodes")
        )
        assert parse_terms(o[rid].get("Terms")) == parse_terms(b[rid].get("Terms"))


def test_enumeration_cell_reconstructed_with_meaning():
    _, rebuilt = _roundtrip(SAMPLE)
    sample = {r.id: r for r in rebuilt}["sample"]
    items = parse_enumeration(sample.get("Enumeration"))
    assert [(i.value, i.label) for i in items] == [("0", "Saliva"), ("1", "Blood")]
    assert items[0].iri == "UBERON:0001836"  # ontology meaning survived


def test_datatype_under_enumeration_preserved():
    _, rebuilt = _roundtrip(SAMPLE)
    # `sample` has an enumeration but its Datatype was integer; it must come back.
    assert {r.id: r for r in rebuilt}["sample"].get("Datatype") == "integer"


def test_field_missing_value_codes_preserved():
    _, rebuilt = _roundtrip(SAMPLE)
    codes = parse_enumeration(
        {r.id: r for r in rebuilt}["sample"].get("MissingValueCodes")
    )
    assert [(c.value, c.label) for c in codes] == [("-1", "Refused")]


# --- Datatypes whose LinkML range differs from the spec name -----------------

def test_datatype_with_renamed_linkml_range_roundtrips():
    """dateTime -> range datetime and anyURI -> range uri must map back to the
    spec names, not leak LinkML range names into the reconstructed CSV."""
    text = "Id,Label,Datatype\nwhen,When,dateTime\nlink,Link,anyURI\n"
    _, rebuilt = _roundtrip(text)
    datatypes = {r.id: r.get("Datatype") for r in rebuilt}
    assert datatypes == {"when": "dateTime", "link": "anyURI"}


# --- Hand-authored schema representation variants ----------------------------
# schema_to_rows accepts common shapes a person would write, not only the
# generated form: class-level slots + slot_usage, a named enum as the slot's
# range, and inline enum_range.

def test_slots_and_slot_usage_style():
    from dd_linkml import schema_to_rows

    schema = {
        "id": "https://example.org/t",
        "name": "t",
        "classes": {
            "Record": {
                "tree_root": True,
                "slots": ["age", "name"],
                "slot_usage": {"age": {"description": "Age in years"}},
            }
        },
        "slots": {
            "age": {"title": "Age", "range": "integer", "description": "overridden"},
            "name": {"title": "Name", "range": "string"},
        },
    }
    rows = {r["Id"]: r for r in schema_to_rows(schema)}
    assert set(rows) == {"age", "name"}
    assert rows["age"]["Datatype"] == "integer"
    assert rows["age"]["Description"] == "Age in years"  # slot_usage wins
    assert rows["name"]["Label"] == "Name"


def test_inherited_slots_are_included():
    from dd_linkml import schema_to_rows

    schema = {
        "id": "https://example.org/t",
        "name": "t",
        "classes": {
            "Base": {"slots": ["age"]},
            "Record": {"tree_root": True, "is_a": "Base", "slots": ["name"]},
        },
        "slots": {
            "age": {"title": "Age", "range": "integer"},
            "name": {"title": "Name", "range": "string"},
        },
    }
    rows = {r["Id"]: r for r in schema_to_rows(schema)}
    assert set(rows) == {"age", "name"}  # `age` comes via is_a inheritance


def test_named_enum_as_direct_range():
    from dd_linkml import schema_to_rows

    schema = {
        "id": "https://example.org/t",
        "name": "t",
        "classes": {
            "Record": {
                "tree_root": True,
                "attributes": {"status": {"range": "StatusEnum"}},
            }
        },
        "enums": {
            "StatusEnum": {
                "permissible_values": {"0": {"title": "Inactive"}, "1": {"title": "Active"}}
            }
        },
    }
    (row,) = schema_to_rows(schema)
    items = parse_enumeration(row["Enumeration"])
    assert [(i.value, i.label) for i in items] == [("0", "Inactive"), ("1", "Active")]
    assert row["Datatype"] == "string"  # no value_datatype annotation to recover


def test_inline_enum_range():
    from dd_linkml import schema_to_rows

    schema = {
        "id": "https://example.org/t",
        "name": "t",
        "classes": {
            "Record": {
                "tree_root": True,
                "attributes": {
                    "status": {
                        "enum_range": {
                            "permissible_values": {"y": {"title": "Yes"}, "n": {"title": "No"}}
                        }
                    }
                },
            }
        },
    }
    (row,) = schema_to_rows(schema)
    items = parse_enumeration(row["Enumeration"])
    assert [(i.value, i.label) for i in items] == [("y", "Yes"), ("n", "No")]


# --- Round-trip on the committed real-world example dictionaries ------------

# gcb is spec-clean; rad has duplicate Ids (kept-first via allow_duplicates).
_EXAMPLE_DICTS = [
    pytest.param("gcb.dd.csv", False, id="gcb"),
    pytest.param("rad.dd.csv", True, id="rad"),
]


def _column_equivalent(column: str, original: str, rebuilt: str) -> bool:
    """Compare a reconstructed column to the original, allowing the forward
    conversion's documented normalisations (whitespace, Terms spacing, blank
    ==single Cardinality, canonical Enumeration serialisation)."""
    if column in ("Enumeration", "MissingValueCodes"):
        return parse_enumeration(original) == parse_enumeration(rebuilt)
    if column == "Terms":
        return parse_terms(original) == parse_terms(rebuilt)
    if column == "Cardinality":
        return (_norm(original) or "single") == (_norm(rebuilt) or "single")
    return _norm(original) == _norm(rebuilt)


@pytest.mark.parametrize("filename, allow_dup", _EXAMPLE_DICTS)
def test_example_dictionary_roundtrips(filename, allow_dup):
    """Each committed example dictionary must survive CSV -> LinkML -> CSV with
    every column semantically equivalent for every data element."""
    path = EXAMPLES / filename
    if not path.exists():
        pytest.skip(f"{filename} not available")

    original = read_data_dictionary(path, allow_duplicates=allow_dup)
    schema = emit_schema(original, EmitOptions(schema_name="ex", class_name="Record"))
    rebuilt = read_data_dictionary(
        io.StringIO(schema_to_csv(schema)), allow_duplicates=allow_dup
    )

    orig_by_id = {r.id: r for r in original}
    rebuilt_by_id = {r.id: r for r in rebuilt}
    assert set(orig_by_id) == set(rebuilt_by_id)

    from dd_core.reader import KNOWN_COLUMNS

    mismatches = []
    for row_id, orig_row in orig_by_id.items():
        rebuilt_row = rebuilt_by_id[row_id]
        for column in KNOWN_COLUMNS:
            if not _column_equivalent(
                column, orig_row.get(column), rebuilt_row.get(column)
            ):
                mismatches.append(f"{row_id}.{column}")
    assert not mismatches, f"{len(mismatches)} column mismatches: {mismatches[:10]}"
