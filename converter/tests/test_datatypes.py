"""Tests for the XSD datatype -> LinkML range mapping."""

from pathlib import Path

import pytest
import yaml

from dd_converter import (
    CustomType,
    UnknownDatatypeError,
    resolve_datatype,
)

# The authoritative set of datatype names lives in the LinkML schema's
# DatatypeEnum. Read it so this test fails if the two ever drift apart.
_SCHEMA = Path(__file__).resolve().parents[2] / "linkml" / "data-dictionary.yaml"


def _datatype_enum_names():
    schema = yaml.safe_load(_SCHEMA.read_text(encoding="utf-8"))
    return list(schema["enums"]["DatatypeEnum"]["permissible_values"].keys())


def test_every_allowable_datatype_resolves():
    """Every name in DatatypeEnum must map to a builtin range or a custom type."""
    unresolved = []
    for name in _datatype_enum_names():
        try:
            resolve_datatype(name)
        except UnknownDatatypeError:
            unresolved.append(name)
    assert unresolved == []


@pytest.mark.parametrize(
    "name, expected",
    [
        ("string", "string"),
        ("integer", "integer"),
        ("long", "integer"),
        ("positiveInteger", "integer"),
        ("decimal", "decimal"),
        ("float", "float"),
        ("double", "double"),
        ("boolean", "boolean"),
        ("date", "date"),
        ("dateTime", "datetime"),  # note: LinkML spells it datetime
        ("time", "time"),
        ("anyURI", "uri"),
        ("token", "string"),
    ],
)
def test_builtin_mappings(name, expected):
    assert resolve_datatype(name) == expected


def test_timestamp_is_custom_integer_type():
    result = resolve_datatype("timestamp")
    assert isinstance(result, CustomType)
    assert result.typeof == "integer"
    assert result.pattern == r"^[0-9]+$"


def test_date_mdy_is_custom_date_type():
    result = resolve_datatype("date_mdy")
    assert isinstance(result, CustomType)
    assert result.typeof == "date"
    assert result.pattern == r"^\d{2}/\d{2}/\d{4}$"


def test_xsd_custom_type_carries_provenance_uri():
    result = resolve_datatype("gYearMonth")
    assert isinstance(result, CustomType)
    assert result.uri == "xsd:gYearMonth"


@pytest.mark.parametrize("bad", ["Integer", "String", "DateTime", "notatype", ""])
def test_unknown_or_miscased_raises(bad):
    with pytest.raises(UnknownDatatypeError):
        resolve_datatype(bad)
