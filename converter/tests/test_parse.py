"""Tests for the enumeration / missing-value-codes cell parser.

The valid examples are drawn from the specification's own worked examples so the
parser is checked against the authoritative source.
"""

import pytest
from dd_converter.grammar import (
    EnumItem,
    ParseError,
    parse_enumeration,
    parse_missing_value_codes,
)


@pytest.mark.parametrize(
    "cell, expected",
    [
        # Whitespace around | and = is insignificant; all three are equivalent.
        (
            '"0"=[Saliva] | "1"=[Blood]',
            [EnumItem("0", "Saliva"), EnumItem("1", "Blood")],
        ),
        (
            '"0"=[Saliva]|"1"=[Blood]',
            [EnumItem("0", "Saliva"), EnumItem("1", "Blood")],
        ),
        (
            '"0" = [Saliva] | "1" = [Blood]',
            [EnumItem("0", "Saliva"), EnumItem("1", "Blood")],
        ),
        # String values equal to their labels.
        (
            '"Saliva"=[Saliva] | "Blood"=[Blood]',
            [EnumItem("Saliva", "Saliva"), EnumItem("Blood", "Blood")],
        ),
        # Multi-word labels with spaces.
        (
            '"RBC" = [Red Blood Cells] | "WBC" = [White Blood Cells]',
            [
                EnumItem("RBC", "Red Blood Cells"),
                EnumItem("WBC", "White Blood Cells"),
            ],
        ),
        # A single pair, negative-signed value (as used by missing-value codes).
        ('"-9999"=[Reason Unknown]', [EnumItem("-9999", "Reason Unknown")]),
    ],
)
def test_parse_enumeration_valid(cell, expected):
    assert parse_enumeration(cell) == expected


def test_parse_enumeration_with_full_iri_and_obo_id():
    cell = (
        '"0"=[Saliva](http://purl.obolibrary.org/obo/UBERON_0001836) '
        '| "1"=[Blood](UBERON:0000178)'
    )
    assert parse_enumeration(cell) == [
        EnumItem("0", "Saliva", "http://purl.obolibrary.org/obo/UBERON_0001836"),
        EnumItem("1", "Blood", "UBERON:0000178"),
    ]


@pytest.mark.parametrize("blank", ["", "   ", "\t", None])
def test_parse_enumeration_blank_is_empty(blank):
    assert parse_enumeration(blank) == []


@pytest.mark.parametrize(
    "bad",
    [
        "0=[Saliva]",  # value not quoted
        '"0"=Saliva',  # label not bracketed
        '"0"=[Saliva] | ',  # trailing empty item
        '"0"=[Saliva] || "1"=[Blood]',  # empty middle item
        "garbage",  # no structure at all
    ],
)
def test_parse_enumeration_malformed_raises(bad):
    with pytest.raises(ParseError):
        parse_enumeration(bad)


def test_missing_value_codes_uses_same_grammar():
    cell = '"-9999"=[Reason Unknown] | "-9980"=[Not Sent to Data Hub]'
    assert parse_missing_value_codes(cell) == [
        EnumItem("-9999", "Reason Unknown"),
        EnumItem("-9980", "Not Sent to Data Hub"),
    ]
