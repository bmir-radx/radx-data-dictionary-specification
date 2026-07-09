"""LinkML round-trip tests for Precondition / Required (see also the
grammar tests in dd_core: test_precondition.py)."""

import io

import yaml
from dd_core import read_data_dictionary
from dd_linkml import emit_schema, schema_to_csv

# --- LinkML emit + round-trip -------------------------------------------------

def test_precondition_and_required_roundtrip_through_linkml():


    text = (
        "Id,Label,Datatype,Cardinality,Precondition,Required\n"
        "smoker,Smoker,integer,,,y\n"
        "symptoms,Symptoms,integer,multiple,,\n"
        'packs,Packs,decimal,,"smoker = ""1"" and age >= 18",y\n'
        "age,Age,integer,,,\n"
    )
    schema_yaml = emit_schema(read_data_dictionary(io.StringIO(text)))
    schema = yaml.safe_load(schema_yaml)
    record = schema["classes"]["Record"]

    # Machine form: rules (absent-when-false, plus present-when-required).
    assert len(record["rules"]) == 2
    assert record["attributes"]["smoker"]["required"] is True
    absent_rule = record["rules"][0]
    assert absent_rule["postconditions"]["slot_conditions"]["packs"]["value_presence"] == "ABSENT"
    assert "none_of" in absent_rule["preconditions"]

    # Round-trip: both columns come back.
    back = {r.id: r for r in read_data_dictionary(io.StringIO(schema_to_csv(schema_yaml)))}
    assert back["packs"].get("Precondition") == 'smoker = "1" and age >= 18'
    assert back["packs"].get("Required") == "y"
    assert back["smoker"].get("Required") == "y"
    assert back["age"].get("Required") == ""


def test_strict_bound_emits_inclusive_bound_plus_not_equal():


    text = 'Id,Label,Datatype,Precondition\nx,X,integer,severity > 2\nseverity,S,integer,\n'
    schema = yaml.safe_load(emit_schema(read_data_dictionary(io.StringIO(text))))
    condition = schema["classes"]["Record"]["rules"][0]["preconditions"]["none_of"][0]
    severity = condition["slot_conditions"]["severity"]
    assert severity["minimum_value"] == 2
    assert severity["none_of"][0]["equals_string"] == "2"


def test_emitted_yaml_with_many_rules_is_valid_yaml():
    """Regression: slot numbering/spacing must not decorate the rules block.

    A rule whose description wraps (long slot name) had a counter comment
    appended to its first physical line, producing unparseable YAML."""


    long_id = "self_reported_measurement_with_a_really_long_identifier"
    text = (
        "Id,Label,Datatype,Precondition\n"
        "gate,Gate,integer,\n"
        + "".join(f'{long_id}_{i},L{i},integer,"gate = ""1"""\n' for i in range(3))
    )
    schema_yaml = emit_schema(read_data_dictionary(io.StringIO(text)))
    schema = yaml.safe_load(schema_yaml)  # must parse
    assert len(schema["classes"]["Record"]["rules"]) == 3
    # Counters must appear only on slots, never inside the rules block.
    in_rules = False
    for line in schema_yaml.splitlines():
        if line.strip() == "rules:":
            in_rules = True
        if in_rules:
            assert "data elements" not in line, line
    # Each rule gets a comment block and a description naming the condition.
    assert '# Rule 1 of 3 — ' in schema_yaml
    assert 'blank unless gate = "1"' in schema_yaml
    # ...and each preconditioned slot points back at its rule.
    assert "# Precondition enforced by rule 1 of 3 (see rules:)" in schema_yaml
