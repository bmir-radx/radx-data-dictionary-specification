"""Tests for the Precondition cell grammar."""

import pytest
from dd_converter.grammar import (
    And,
    Comparison,
    Contains,
    InSet,
    Or,
    ParseError,
    atoms,
    parse_precondition,
    referenced_fields,
    serialise_precondition,
)


def test_blank_means_always_applies():
    assert parse_precondition("") is None
    assert parse_precondition("   ") is None


def test_simple_equality():
    assert parse_precondition('smoker = "1"') == Comparison("smoker", "=", "1")


def test_non_blank_test():
    assert parse_precondition('a <> ""') == Comparison("a", "<>", "")


@pytest.mark.parametrize("op", ["<", "<=", ">", ">=", "<>"])
def test_comparators(op):
    node = parse_precondition(f"age {op} 65")
    assert node == Comparison("age", op, "65")


def test_in_set():
    assert parse_precondition('status in {"1", "2"}') == InSet("status", ("1", "2"))


def test_contains():
    assert parse_precondition('symptoms contains "3"') == Contains("symptoms", "3")


def test_and_binds_tighter_than_or():
    node = parse_precondition('a = "1" or b = "2" and c = "3"')
    assert isinstance(node, Or)
    assert node.clauses[0] == Comparison("a", "=", "1")
    assert node.clauses[1] == And((Comparison("b", "=", "2"), Comparison("c", "=", "3")))


def test_parentheses_group():
    node = parse_precondition('(a = "1" or b = "2") and c = "3"')
    assert isinstance(node, And)
    assert isinstance(node.clauses[0], Or)


def test_keywords_case_insensitive():
    node = parse_precondition('a = "1" AND b IN {"2"} OR c CONTAINS "3"')
    assert isinstance(node, Or)


def test_decimal_and_negative_literals():
    assert parse_precondition("severity > 2.5") == Comparison("severity", ">", "2.5")
    assert parse_precondition("t >= -1") == Comparison("t", ">=", "-1")


def test_referenced_fields_and_atoms():
    node = parse_precondition('a = "1" and (b > 2 or c contains "3")')
    assert referenced_fields(node) == {"a", "b", "c"}
    assert [type(x).__name__ for x in atoms(node)] == ["Comparison", "Comparison", "Contains"]


@pytest.mark.parametrize(
    "bad",
    [
        "datediff([a],[b]) > 3",   # function calls are out of scope
        '[a] = "1"',               # REDCap bracket syntax is not this grammar
        'a = ',                    # missing literal
        'a = "1" and',             # dangling keyword
        "sum(a)",
    ],
)
def test_malformed_raises(bad):
    with pytest.raises(ParseError):
        parse_precondition(bad)


@pytest.mark.parametrize(
    "text",
    [
        'a <> ""',
        'consented = "yes" and age >= 18',
        'status in {"a", "b"} or (symptoms contains "x" and severity > 2)',
    ],
)
def test_serialise_round_trips(text):
    node = parse_precondition(text)
    assert parse_precondition(serialise_precondition(node)) == node


# --- LinkML emit + round-trip -------------------------------------------------

def test_precondition_and_required_roundtrip_through_linkml():
    import io

    import yaml
    from dd_converter import emit_schema, read_data_dictionary, schema_to_csv

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
    import io

    import yaml
    from dd_converter import emit_schema, read_data_dictionary

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
    import io

    import yaml

    from dd_converter import emit_schema, read_data_dictionary

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
