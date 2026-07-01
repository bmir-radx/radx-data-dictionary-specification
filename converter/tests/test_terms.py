"""Tests for the Terms cell tokeniser."""

import pytest

from radx_dd_converter.grammar import parse_terms


@pytest.mark.parametrize(
    "cell, expected",
    [
        ("UBERON:0001836", ["UBERON:0001836"]),
        (
            "UBERON:0001836 UBERON:0000178",
            ["UBERON:0001836", "UBERON:0000178"],
        ),
        (
            "http://purl.obolibrary.org/obo/UBERON_0001836",
            ["http://purl.obolibrary.org/obo/UBERON_0001836"],
        ),
        # Non-breaking space (U+00A0) is an allowed separator.
        ("UBERON:1 UBERON:2", ["UBERON:1", "UBERON:2"]),
        # Newline is an allowed separator; surrounding whitespace ignored.
        ("  UBERON:1\nUBERON:2  ", ["UBERON:1", "UBERON:2"]),
    ],
)
def test_parse_terms(cell, expected):
    assert parse_terms(cell) == expected


@pytest.mark.parametrize("blank", ["", "   ", "\n", None])
def test_parse_terms_blank_is_empty(blank):
    assert parse_terms(blank) == []
