"""Choices-parser tests, including every case from the Java test suite."""

import pytest
from dd_redcap.choices import parse_choices


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_empty_choice_list(empty):
    assert parse_choices(empty) == {}


def test_single_value():
    assert parse_choices("23") == {"23": "23"}


def test_single_value_label():
    assert parse_choices("22, Hello") == {"22": "Hello"}


def test_multiple_choices_with_pipe():
    assert parse_choices("1, Yes | 2, No | 3, Maybe") == {"1": "Yes", "2": "No", "3": "Maybe"}


def test_pipe_wins_over_semicolons():
    # A pipe-separated list whose labels contain semicolons.
    result = parse_choices("1, Yes; Possibly | 2, No | 3, Maybe")
    assert result == {"1": "Yes; Possibly", "2": "No", "3": "Maybe"}


def test_semicolon_separated():
    assert parse_choices("1, Yes ; 2, No ; 3, Maybe") == {"1": "Yes", "2": "No", "3": "Maybe"}


def test_labels_keep_their_commas():
    result = parse_choices("1, Less than $15,000 | 2, $15,000 - $19,999")
    assert result == {"1": "Less than $15,000", "2": "$15,000 - $19,999"}


def test_order_preserved():
    assert list(parse_choices("3, C | 1, A | 2, B")) == ["3", "1", "2"]
