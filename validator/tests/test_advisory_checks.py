"""Tests for the consistency / advisory checks added after v0.0.6."""

from dd_validator.checks import (
    check_aliases,
    check_boolean_enumeration,
    check_description_present,
    check_enumeration_consistency,
    check_examples,
    check_label_quality,
    check_precondition_values,
    check_section_runs,
    check_unit_hygiene,
)
from dd_validator.model import Level
from dd_validator.rows import RawRow


def _rows(*records):
    return [RawRow(cells=cells, line=line) for line, cells in records]


# --- aliases -----------------------------------------------------------------

def test_alias_colliding_with_an_id_is_warned():
    rows = _rows(
        (2, {"Id": "age", "Aliases": ""}),
        (3, {"Id": "weight", "Aliases": "age"}),
    )
    (finding,) = list(check_aliases(rows, {"Id", "Aliases"}))
    assert finding.check == "alias-id-collision" and finding.level is Level.WARNING
    assert finding.line == 3 and finding.value == "age"


def test_alias_claimed_twice_is_warned_on_the_second_claim():
    rows = _rows(
        (2, {"Id": "a", "Aliases": "old_name"}),
        (3, {"Id": "b", "Aliases": "old_name"}),
    )
    (finding,) = list(check_aliases(rows, {"Id", "Aliases"}))
    assert finding.check == "duplicate-alias" and finding.line == 3
    # Names the other element by Id — meaningful in every rendering.
    assert "'a'" in finding.message


def test_empty_alias_segment_suggests_cleaned_cell():
    rows = _rows((2, {"Id": "a", "Aliases": "x||y|"}))
    (finding,) = list(check_aliases(rows, {"Id", "Aliases"}))
    assert finding.check == "empty-list-segment"
    assert finding.suggestion == "x|y"


# --- examples ----------------------------------------------------------------

_ENUM = '"0"=[No] | "1"=[Yes]'


def test_example_outside_enumeration_is_warned():
    rows = _rows((2, {"Datatype": "integer", "Enumeration": _ENUM, "Examples": "0|9"}))
    (finding,) = list(check_examples(rows, {"Examples"}))
    assert finding.check == "example-not-in-enumeration" and finding.value == "9"


def test_example_violating_pattern_or_datatype_is_warned():
    rows = _rows((2, {"Datatype": "integer", "Pattern": r"\d{2}", "Examples": "abc"}))
    checks = {f.check for f in check_examples(rows, {"Examples"})}
    assert checks == {"example-pattern-mismatch", "example-datatype-mismatch"}


def test_conforming_examples_are_silent():
    rows = _rows(
        (2, {"Datatype": "integer", "Enumeration": _ENUM, "Examples": "0|1"}),
        (3, {"Datatype": "date", "Examples": "2024-01-31"}),
        (4, {"Datatype": "string", "Examples": "anything goes"}),
    )
    assert list(check_examples(rows, {"Examples"})) == []


# --- enumeration consistency ---------------------------------------------------

def test_duplicate_enumeration_value_is_an_error_reported_once():
    cell = '"1"=[Yes] | "1"=[No] | "1"=[Maybe]'
    rows = _rows((2, {"Enumeration": cell}))
    findings = [
        f for f in check_enumeration_consistency(rows, {"Enumeration"})
        if f.check == "enumeration-duplicate-value"
    ]
    assert len(findings) == 1 and findings[0].level is Level.ERROR


def test_shared_label_across_values_is_info():
    cell = '"1"=[Unknown] | "2"=[Unknown]'
    rows = _rows((2, {"Enumeration": cell}))
    (finding,) = list(check_enumeration_consistency(rows, {"Enumeration"}))
    assert finding.check == "enumeration-duplicate-label" and finding.level is Level.INFO


def test_enumeration_overlapping_missing_codes_is_warned():
    rows = _rows(
        (2, {
            "Enumeration": '"-1"=[Refused answer] | "1"=[Yes]',
            "MissingValueCodes": '"-1"=[Refused]',
        }),
        (3, {"Enumeration": '"-9999"=[Odd choice]', "MissingValueCodes": ""}),
    )
    findings = list(check_enumeration_consistency(rows, {"Enumeration"}))
    assert [f.check for f in findings] == ["enumeration-missing-code-overlap"] * 2
    assert "standard" in findings[1].message  # -9999 is a standard code


def test_enumeration_value_rejected_by_own_pattern_is_warned():
    rows = _rows((2, {"Enumeration": '"ten"=[Ten] | "2"=[Two]', "Pattern": r"\d+"}))
    (finding,) = list(check_enumeration_consistency(rows, {"Enumeration"}))
    assert finding.check == "enumeration-pattern-mismatch" and finding.value == "ten"


# --- precondition values -------------------------------------------------------

def test_precondition_value_outside_referenced_enumeration_is_warned():
    rows = _rows(
        (2, {"Id": "smoker", "Datatype": "integer", "Enumeration": _ENUM,
             "Precondition": ""}),
        (3, {"Id": "packs", "Datatype": "integer", "Enumeration": "",
             "Precondition": 'smoker = "9"'}),
    )
    (finding,) = list(check_precondition_values(rows, {"Precondition"}))
    assert finding.check == "precondition-value-not-in-enumeration"
    assert finding.line == 3 and finding.value == "9"


def test_precondition_literal_must_fit_referenced_datatype():
    rows = _rows(
        (2, {"Id": "age", "Datatype": "integer", "Enumeration": "",
             "Precondition": ""}),
        (3, {"Id": "x", "Datatype": "string", "Enumeration": "",
             "Precondition": 'age >= "abc"'}),
    )
    (finding,) = list(check_precondition_values(rows, {"Precondition"}))
    assert finding.check == "precondition-value-datatype" and finding.value == "abc"


def test_precondition_blank_test_and_valid_values_are_silent():
    rows = _rows(
        (2, {"Id": "smoker", "Datatype": "integer", "Enumeration": _ENUM,
             "Precondition": ""}),
        (3, {"Id": "packs", "Datatype": "integer", "Enumeration": "",
             "Precondition": 'smoker = "1" and smoker <> ""'}),
    )
    assert list(check_precondition_values(rows, {"Precondition"})) == []


# --- unit hygiene ----------------------------------------------------------------

def test_informal_unit_gets_ucum_suggestion():
    rows = _rows((2, {"Unit": "per year", "Datatype": "integer"}))
    (finding,) = list(check_unit_hygiene(rows, {"Unit"}))
    assert finding.check == "unit-suggestion" and finding.suggestion == "/a"


def test_exact_and_exotic_units_are_silent():
    rows = _rows(
        (2, {"Unit": "mg/dL", "Datatype": "decimal"}),
        (3, {"Unit": "nmol/L", "Datatype": "decimal"}),  # valid, outside subset
    )
    assert list(check_unit_hygiene(rows, {"Unit"})) == []


def test_unit_on_boolean_field_is_flagged():
    rows = _rows((2, {"Unit": "kg", "Datatype": "boolean"}))
    (finding,) = list(check_unit_hygiene(rows, {"Unit"}))
    assert finding.check == "unit-on-non-quantity"


def test_boolean_with_enumeration_is_flagged():
    rows = _rows((2, {"Datatype": "boolean", "Enumeration": _ENUM}))
    (finding,) = list(check_boolean_enumeration(rows, {"Datatype", "Enumeration"}))
    assert finding.check == "boolean-with-enumeration"


# --- labels, descriptions, sections ----------------------------------------------

def test_label_repeating_id_and_duplicate_labels_are_nudged():
    rows = _rows(
        (2, {"Id": "age", "Label": "age"}),
        (3, {"Id": "a1", "Label": "Age in years"}),
        (4, {"Id": "a2", "Label": "Age in years"}),
    )
    checks = [f.check for f in check_label_quality(rows, {"Label"})]
    assert checks == ["label-equals-id", "duplicate-label"]


def test_blank_description_is_nudged_only_when_the_column_exists():
    rows = _rows((2, {"Id": "a", "Description": ""}))
    (finding,) = list(check_description_present(rows, {"Description"}))
    assert finding.check == "description-missing"
    assert list(check_description_present(rows, {"Id"})) == []


def test_fragmented_section_is_flagged_where_it_resumes():
    rows = _rows(
        (2, {"Section": "A"}),
        (3, {"Section": "A"}),
        (4, {"Section": "B"}),
        (5, {"Section": "A"}),
    )
    (finding,) = list(check_section_runs(rows, {"Section"}))
    assert finding.check == "section-fragmented" and finding.line == 5


def test_contiguous_sections_are_silent():
    rows = _rows(
        (2, {"Section": "A"}),
        (3, {"Section": ""}),  # blank rows do not break a run
        (4, {"Section": "A"}),
        (5, {"Section": "B"}),
    )
    assert list(check_section_runs(rows, {"Section"})) == []
