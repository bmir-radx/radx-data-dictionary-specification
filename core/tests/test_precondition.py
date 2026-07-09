"""Tests for the Precondition cell grammar."""

import pytest
from dd_core.grammar import (
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
