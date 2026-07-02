"""Round-trip tests: CSV -> LinkML -> CSV should be semantically equivalent."""

import io

from radx_dd_converter import (
    EmitOptions,
    emit_schema,
    read_data_dictionary,
    schema_to_csv,
)
from radx_dd_converter.grammar import parse_enumeration, parse_terms

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
