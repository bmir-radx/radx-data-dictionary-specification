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
    assert pvs["0"]["description"] == "Saliva"


def test_obo_prefix_is_auto_registered(schema):
    assert schema["prefixes"]["UBERON"] == "http://purl.obolibrary.org/obo/UBERON_"


def test_standard_codes_enum_present_and_complete(schema):
    pvs = schema["enums"]["StandardMissingValueCodes"]["permissible_values"]
    assert len(pvs) == 25
    assert pvs["-9999"]["description"] == "Reason Unknown"


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
