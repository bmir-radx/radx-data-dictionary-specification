"""Tests for the individual checks."""

from dd_validator.checks import (
    check_cardinality,
    check_datatype,
    check_duplicate_ids,
    check_enumeration,
    check_id,
    check_label,
    check_missing_value_codes,
    check_pattern,
    check_required_headers,
    check_see_also,
)
from dd_validator.model import Level
from dd_validator.rows import RawRow


def _rows(*records):
    """Build RawRows from (line, {col: val}) tuples."""
    return [RawRow(cells=cells, line=line) for line, cells in records]


# --- required headers ------------------------------------------------------

def test_required_headers_all_present():
    assert list(check_required_headers(["Id", "Label", "Datatype"])) == []


def test_required_headers_missing_reported():
    findings = list(check_required_headers(["Id", "Datatype"]))
    assert [f.column for f in findings] == ["Label"]
    assert findings[0].level is Level.ERROR


def test_required_headers_suggests_rename_on_case_mismatch():
    (finding,) = list(check_required_headers(["id", "Label", "Datatype"]))
    assert finding.column == "Id"
    assert "did you mean" in finding.message and "'id'" in finding.message


# --- id --------------------------------------------------------------------

def test_id_missing():
    (f,) = list(check_id(_rows((2, {"Id": ""})), {"Id"}))
    assert f.check == "id-missing" and f.level is Level.ERROR


def test_id_leading_space_yields_error_and_info():
    findings = list(check_id(_rows((2, {"Id": " age"})), {"Id"}))
    checks = {f.check: f.level for f in findings}
    assert checks == {"id-leading-whitespace": Level.ERROR, "id-whitespace": Level.INFO}


def test_id_interior_space_is_info_only():
    findings = list(check_id(_rows((2, {"Id": "a b"})), {"Id"}))
    assert [f.check for f in findings] == ["id-whitespace"]
    assert findings[0].level is Level.INFO


def test_id_absent_column_is_silent():
    assert list(check_id(_rows((2, {"Label": "x"})), {"Label"})) == []


# --- label -----------------------------------------------------------------

def test_label_missing_is_warning():
    (f,) = list(check_label(_rows((2, {"Label": ""})), {"Label"}))
    assert f.level is Level.WARNING and f.check == "label-missing"


def test_label_present_is_silent():
    assert list(check_label(_rows((2, {"Label": "Age"})), {"Label"})) == []


# --- datatype --------------------------------------------------------------

def test_datatype_missing():
    (f,) = list(check_datatype(_rows((2, {"Datatype": ""})), {"Datatype"}))
    assert f.check == "datatype-missing"


def test_datatype_known_is_silent():
    assert list(check_datatype(_rows((2, {"Datatype": "integer"})), {"Datatype"})) == []


def test_datatype_unknown_with_case_suggestion():
    (f,) = list(check_datatype(_rows((2, {"Datatype": "Integer"})), {"Datatype"}))
    assert f.check == "unknown-datatype"
    assert "'integer'" in f.message


def test_datatype_unknown_with_fixmap_suggestion():
    (f,) = list(check_datatype(_rows((2, {"Datatype": "text"})), {"Datatype"}))
    assert "'string'" in f.message


def test_datatype_unknown_without_suggestion():
    (f,) = list(check_datatype(_rows((2, {"Datatype": "zorb"})), {"Datatype"}))
    assert "did you mean" not in f.message


# --- cardinality -----------------------------------------------------------

def test_cardinality_valid():
    rows = _rows((2, {"Cardinality": "single"}), (3, {"Cardinality": "multiple"}))
    assert list(check_cardinality(rows, {"Cardinality"})) == []


def test_cardinality_blank_is_silent():
    assert list(check_cardinality(_rows((2, {"Cardinality": ""})), {"Cardinality"})) == []


def test_cardinality_invalid():
    (f,) = list(check_cardinality(_rows((2, {"Cardinality": "many"})), {"Cardinality"}))
    assert f.check == "invalid-cardinality"


# --- pattern ---------------------------------------------------------------

def test_pattern_valid():
    assert list(check_pattern(_rows((2, {"Pattern": "^[0-9]+$"})), {"Pattern"})) == []


def test_pattern_malformed():
    (f,) = list(check_pattern(_rows((2, {"Pattern": "[a-z"})), {"Pattern"}))
    assert f.check == "malformed-pattern"


# --- enumeration / missing value codes -------------------------------------

def test_enumeration_valid():
    rows = _rows((2, {"Enumeration": '"0"=[No] | "1"=[Yes]'}))
    assert list(check_enumeration(rows, {"Enumeration"})) == []


def test_enumeration_malformed():
    (f,) = list(check_enumeration(_rows((2, {"Enumeration": '"0"=[No] | "1"'})), {"Enumeration"}))
    assert f.check == "malformed-enumeration"


def test_missing_value_codes_malformed():
    rows = _rows((2, {"MissingValueCodes": "garbage"}))
    (f,) = list(check_missing_value_codes(rows, {"MissingValueCodes"}))
    assert f.check == "malformed-missing-value-codes"


# --- see also --------------------------------------------------------------

def test_see_also_absolute_is_silent():
    rows = _rows((2, {"SeeAlso": "https://example.org/x"}))
    assert list(check_see_also(rows, {"SeeAlso"})) == []


def test_see_also_relative_is_error():
    (f,) = list(check_see_also(_rows((2, {"SeeAlso": "not-a-url"})), {"SeeAlso"}))
    assert f.check == "malformed-see-also"


# --- duplicate ids ---------------------------------------------------------

def test_duplicate_ids():
    rows = _rows((2, {"Id": "a"}), (3, {"Id": "b"}), (4, {"Id": "a"}))
    findings = list(check_duplicate_ids(rows, {"Id"}))
    assert [f.line for f in findings] == [4]
    assert "first seen on line 2" in findings[0].message


def test_no_duplicate_ids():
    rows = _rows((2, {"Id": "a"}), (3, {"Id": "b"}))
    assert list(check_duplicate_ids(rows, {"Id"})) == []
