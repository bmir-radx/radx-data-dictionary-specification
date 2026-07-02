"""Tests for the schema emitter.

The headline test converts the fixture dictionary and lints the *generated*
schema, asserting zero errors: the emitter must always produce a valid LinkML
schema. The remaining tests check specific mapping decisions from the plan.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from radx_dd_converter import read_data_dictionary
from radx_dd_converter.emit import EmitOptions, Emitter, emit_schema

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def schema_yaml():
    rows = read_data_dictionary(FIXTURES / "sample.csv")
    return emit_schema(
        rows,
        EmitOptions(
            schema_id="https://example.org/s",
            schema_name="s",
            class_name="Record",
        ),
    )


@pytest.fixture
def schema(schema_yaml):
    return yaml.safe_load(schema_yaml)


def _find_linter():
    """Locate the linkml-lint console script next to the running interpreter."""
    candidate = Path(sys.executable).with_name("linkml-lint")
    if candidate.exists():
        return str(candidate)
    from shutil import which

    return which("linkml-lint")


def test_generated_schema_lints_clean(schema_yaml, tmp_path):
    """The emitter must always produce a schema that linkml-lint accepts."""
    linter = _find_linter()
    if linter is None:
        pytest.skip("linkml-lint not available")
    path = tmp_path / "generated.yaml"
    path.write_text(schema_yaml, encoding="utf-8")
    result = subprocess.run(
        [linter, str(path)], capture_output=True, text=True, env=os.environ
    )
    error_lines = [ln for ln in result.stdout.splitlines() if "  error  " in ln]
    assert error_lines == [], "\n".join(error_lines)


def test_root_class_and_slot_order(schema):
    cls = schema["classes"]["Record"]
    assert cls["tree_root"] is True
    # Slot order preserves datafile field order.
    assert list(cls["attributes"].keys()) == ["PartId", "SampleType", "Symptoms"]


def test_label_becomes_title_and_pattern_verbatim(schema):
    part = schema["classes"]["Record"]["attributes"]["PartId"]
    assert part["title"] == "Participant Id"
    assert part["pattern"] == r"^[NP](\d+)$"
    assert part["range"] == "string"


def test_cardinality_multiple_becomes_multivalued(schema):
    symptoms = schema["classes"]["Record"]["attributes"]["Symptoms"]
    assert symptoms.get("multivalued") is True


def test_examples_are_split_on_pipe(schema):
    part = schema["classes"]["Record"]["attributes"]["PartId"]
    assert [e["value"] for e in part["examples"]] == ["N001", "N002"]


def test_enumeration_uses_any_of_with_standard_codes(schema):
    sample_type = schema["classes"]["Record"]["attributes"]["SampleType"]
    ranges = [b["range"] for b in sample_type["any_of"]]
    assert ranges == ["SampleTypeEnum", "StandardMissingValueCodes"]
    # underlying datatype is preserved (annotations serialize as bare strings)
    assert sample_type["annotations"]["value_datatype"] == "integer"


def test_enum_values_carry_meaning(schema):
    pvs = schema["enums"]["SampleTypeEnum"]["permissible_values"]
    assert pvs["0"]["meaning"] == "UBERON:0001836"
    assert pvs["0"]["title"] == "Saliva"


def test_obo_prefix_is_auto_registered(schema):
    assert schema["prefixes"]["UBERON"] == "http://purl.obolibrary.org/obo/UBERON_"


def test_terms_map_to_related_mappings_not_slot_uri():
    csv = (
        "Id,Label,Datatype,Terms\n"
        "age,Age,integer,PATO:0000011 NCIT:C25150\n"
    )
    slot = yaml.safe_load(emit_schema(read_data_dictionary(_csv(csv))))[
        "classes"
    ]["Record"]["attributes"]["age"]
    assert slot["related_mappings"] == ["PATO:0000011", "NCIT:C25150"]
    assert "slot_uri" not in slot
    assert "exact_mappings" not in slot


def test_standard_codes_enum_present_and_complete(schema):
    pvs = schema["enums"]["StandardMissingValueCodes"]["permissible_values"]
    assert len(pvs) == 25
    assert pvs["-9999"]["title"] == "Reason Unknown"


def test_custom_type_emitted_for_timestamp():
    rows = read_data_dictionary(
        _csv("Id,Label,Datatype\nWhen,When,timestamp\n")
    )
    schema = yaml.safe_load(emit_schema(rows))
    assert "timestamp" in schema["types"]
    assert schema["types"]["timestamp"]["typeof"] == "integer"
    assert schema["classes"]["Record"]["attributes"]["When"]["range"] == "timestamp"


def test_unit_lookup_and_raw_preserved():
    rows = read_data_dictionary(
        _csv("Id,Label,Datatype,Unit\nHeight,Height,decimal,mm\n")
    )
    slot = yaml.safe_load(emit_schema(rows))["classes"]["Record"]["attributes"]["Height"]
    assert slot["unit"]["descriptive_name"] == "millimeter"
    assert slot["unit"]["symbol"] == "mm"
    assert slot["annotations"]["unit_raw"] == "mm"


def test_output_has_section_comments_and_blank_lines(schema_yaml):
    assert "# --- Slots ---" not in schema_yaml  # slots live under Classes
    assert "# --- Classes ---" in schema_yaml
    assert "# --- Enumerations ---" in schema_yaml
    # A blank line separates slots (two attribute keys with a blank between).
    assert "\n\n      PartId:" in schema_yaml or "\n\n      SampleType:" in schema_yaml


def test_pretty_rendering_preserves_content(schema_yaml):
    """The comment/blank-line pass must not alter the schema data."""
    import json

    from linkml_runtime.dumpers import json_dumper

    from radx_dd_converter import read_data_dictionary
    from radx_dd_converter.emit import Emitter, EmitOptions, _strip_type_keys

    em = Emitter(EmitOptions(schema_id="https://example.org/s", schema_name="s",
                             class_name="Record"))
    schema = em.build(read_data_dictionary(FIXTURES / "sample.csv"))
    ref = _strip_type_keys(json.loads(json_dumper.dumps(schema)))
    from radx_dd_converter.emit import _render

    assert yaml.safe_load(_render(ref)) == ref


def test_redundant_name_and_text_keys_dropped(schema_yaml, schema):
    # `name:` is inferred from the mapping key; it should not be emitted.
    assert "\n    name:" not in schema_yaml and "\n        name:" not in schema_yaml
    # Permissible-value `text:` equal to its key should be dropped.
    pvs = schema["enums"]["SampleTypeEnum"]["permissible_values"]
    assert "text" not in pvs["0"]
    assert pvs["0"]["title"] == "Saliva"
    # Class / enum names still resolve (they come from the keys).
    assert "Record" in schema["classes"]
    assert "SampleTypeEnum" in schema["enums"]


def test_header_comment_present(schema_yaml):
    assert schema_yaml.startswith("# LinkML schema generated from a RADx data dictionary")


def test_multiline_description_is_block_scalar():
    csv = (
        "Id,Label,Datatype,Description\n"
        'A,A,string,"line one' "\n" 'line two"\n'
    )
    out = emit_schema(read_data_dictionary(_csv(csv)))
    assert "description: |" in out  # literal block, not escaped quoted string


def test_clean_text_strips_trailing_and_leading_blank_lines():
    from radx_dd_converter.emit import _clean_text

    # trailing blank lines and per-line trailing spaces removed; internal
    # newlines and spacing preserved.
    assert _clean_text("hello   \n\n\n") == "hello"
    assert _clean_text("\n\nhead\n\nmid\n\n") == "head\n\nmid"
    assert _clean_text("a  \nb  ") == "a\nb"


def test_description_has_no_trailing_blank_lines_in_output():
    # A description whose cell ends with blank lines must not carry them through.
    csv = 'Id,Label,Datatype,Description\nA,A,string,"body text\n\n\n"\n'
    schema = yaml.safe_load(emit_schema(read_data_dictionary(_csv(csv))))
    desc = schema["classes"]["Record"]["attributes"]["A"]["description"]
    assert desc == "body text"


def test_entries_are_numbered_n_of_m(schema_yaml):
    # Enums numbered within all enums; the sample fixture yields 2 (field + std).
    assert "SampleTypeEnum:  # 1 of 2 enums" in schema_yaml
    assert "StandardMissingValueCodes:  # 2 of 2 enums" in schema_yaml
    # The single tree_root class is 1 of 1 (singularised).
    assert "Record:  # 1 of 1 class" in schema_yaml
    # Slots are numbered within all slots, labelled "data elements".
    assert "PartId:  # 1 of 3 data elements" in schema_yaml
    assert "Symptoms:  # 3 of 3 data elements" in schema_yaml
    # A slot's sub-keys (title/range) are not numbered.
    assert "title: Participant Id\n" in schema_yaml


def test_number_entries_helper_resets_per_section():
    from radx_dd_converter.emit import _number_entries_at

    body = "  A:\n    x: 1\n  B:\n    y: 2\n  C:\n    z: 3"
    out = _number_entries_at(body, indent=2, total=3, label="enums")
    assert "  A:  # 1 of 3 enums" in out
    assert "  B:  # 2 of 3 enums" in out
    assert "  C:  # 3 of 3 enums" in out
    # nested keys (x/y/z) are untouched
    assert "    x: 1\n" in out


def test_annotate_enum_usage_lists_using_data_elements():
    rows = read_data_dictionary(FIXTURES / "sample.csv")
    out = emit_schema(
        rows,
        EmitOptions(schema_name="s", class_name="Record", annotate_enum_usage=True),
    )
    # Appended to the enum's existing "n of m enums" numbering comment.
    assert "SampleTypeEnum:  # 1 of 2 enums; used by: SampleType" in out
    # StandardMissingValueCodes is not a field enum -> no "used by".
    assert "StandardMissingValueCodes:  # 2 of 2 enums\n" in out


def test_annotate_enum_usage_dedup_and_cap():
    from radx_dd_converter.emit import _annotate_enum_usage

    users = {"E": [f"f{i}" for i in range(10)]}
    out = _annotate_enum_usage("  E:  # 1 of 1 enum\n", users)
    assert "used by: f0 | f1 | f2 | f3 | f4 | f5 (+4 more)" in out


def test_annotate_enum_values_off_by_default(schema_yaml):
    # Default output: no value comment after the enum range.
    assert "range: SampleTypeEnum\n" in schema_yaml
    assert "# 0=Saliva" not in schema_yaml


def test_annotate_enum_values_adds_capped_comment():
    rows = read_data_dictionary(FIXTURES / "sample.csv")
    out = emit_schema(
        rows,
        EmitOptions(schema_name="s", class_name="Record", annotate_enum_values=True),
    )
    assert "- range: SampleTypeEnum  # 0=Saliva | 1=Blood" in out
    # StandardMissingValueCodes is not a field enum -> never annotated.
    assert "range: StandardMissingValueCodes  #" not in out


def test_enum_value_comment_is_capped():
    from radx_dd_converter.emit import _annotate_enum_ranges

    pairs = [(str(i), f"L{i}") for i in range(10)]
    out = _annotate_enum_ranges(
        "        - range: BigEnum\n", {"BigEnum": pairs}
    )
    assert "(+4 more)" in out  # 10 values, cap 6 -> 4 hidden
    assert out.count("=") == 6  # exactly 6 value=label pairs shown


def test_identical_enumerations_are_deduplicated():
    csv = (
        "Id,Label,Datatype,Enumeration\n"
        'A,A,integer,"""0""=[No] | ""1""=[Yes]"\n'
        'B,B,integer,"""0""=[No] | ""1""=[Yes]"\n'
    )
    schema = yaml.safe_load(emit_schema(read_data_dictionary(_csv(csv))))
    enum_names = [n for n in schema["enums"] if n != "StandardMissingValueCodes"]
    # Both slots share one generated enum.
    assert len(enum_names) == 1


def _csv(text: str):
    import io

    return io.StringIO(text)
