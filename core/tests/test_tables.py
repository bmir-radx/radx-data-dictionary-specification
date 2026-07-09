"""Tests for the constant tables: standard missing-value codes and units."""

import pytest
from dd_core import (
    STANDARD_MISSING_VALUE_CODES,
    UnitOfMeasure,
    lookup_unit,
)

# --- Standard missing-value codes ------------------------------------------

def test_standard_codes_count():
    # The specification defines exactly 25 standard codes.
    assert len(STANDARD_MISSING_VALUE_CODES) == 25


def test_standard_codes_are_unique():
    values = [c.value for c in STANDARD_MISSING_VALUE_CODES]
    assert len(set(values)) == len(values)


def test_standard_codes_spot_check():
    by_value = {c.value: c.label for c in STANDARD_MISSING_VALUE_CODES}
    assert by_value["-9999"] == "Reason Unknown"
    assert by_value["-9980"] == "Not Sent to Data Hub"
    assert by_value["-9946"] == "Other Unpresented Reason Not Specified"


# --- Unit table ------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected_name, expected_symbol",
    [
        ("mm", "millimeter", "mm"),
        ("millimeter", "millimeter", "mm"),
        ("MILLIMETER", "millimeter", "mm"),  # case-insensitive
        (" mL ", "milliliter", "mL"),  # surrounding whitespace ignored
        ("°C", "degrees Celsius", "°C"),
        ("mol/L", "moles per liter", "mol/L"),
    ],
)
def test_lookup_by_name_or_symbol(raw, expected_name, expected_symbol):
    u = lookup_unit(raw)
    assert isinstance(u, UnitOfMeasure)
    assert u.descriptive_name == expected_name
    assert u.symbol == expected_symbol


def test_lookup_populates_ucum_code():
    assert lookup_unit("degrees Celsius").ucum_code == "Cel"
    assert lookup_unit("mm").ucum_code == "mm"


@pytest.mark.parametrize("unknown", ["parsecs", "widgets", "", "   ", None])
def test_lookup_unknown_returns_none(unknown):
    assert lookup_unit(unknown) is None
