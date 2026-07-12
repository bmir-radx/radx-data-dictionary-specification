"""Tests for the individual checks."""

from dd_validator.checks import (
    check_cardinality,
    check_cell_whitespace,
    check_datatype,
    check_datatype_preferred,
    check_duplicate_ids,
    check_enumeration,
    check_enumeration_datatype,
    check_id,
    check_label,
    check_missing_value_codes,
    check_pattern,
    check_required_headers,
    check_see_also,
    check_units,
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
    assert checks == {"id-leading-whitespace": Level.ERROR, "id-characters": Level.INFO}


def test_id_interior_space_is_info_only():
    findings = list(check_id(_rows((2, {"Id": "a b"})), {"Id"}))
    assert [f.check for f in findings] == ["id-characters"]
    assert findings[0].level is Level.INFO
    assert findings[0].suggestion == "a_b"


def test_id_special_characters_flagged_with_schema_safe_suggestion():
    (finding,) = list(check_id(_rows((2, {"Id": "9-lives (total)"})), {"Id"}))
    assert finding.check == "id-characters"
    # The suggestion is exactly the emitter's rename (dd_core sanitize rule).
    assert finding.suggestion == "x_9_lives_total"


def test_id_clean_identifier_is_silent():
    assert list(check_id(_rows((2, {"Id": "age_years"})), {"Id"})) == []


# --- cell whitespace ----------------------------------------------------------

def test_padded_cell_warned_with_stripped_suggestion():
    row = {"Id": "age", "Label": " Age ", "Unit": "a"}
    (finding,) = list(check_cell_whitespace(_rows((2, row)), {"Id", "Label", "Unit"}))
    assert finding.check == "cell-whitespace" and finding.level is Level.WARNING
    assert finding.column == "Label" and finding.suggestion == "Age"


def test_cell_whitespace_skips_id_blank_and_whitespace_only_cells():
    row = {"Id": " age", "Label": "", "Notes": "   "}
    assert list(check_cell_whitespace(_rows((2, row)), {"Id", "Label", "Notes"})) == []


# --- advisory: datatype-preferred -------------------------------------------

def test_datatype_alias_prefers_semantic_name():
    (finding,) = list(check_datatype_preferred(_rows((2, {"Datatype": "int"})), {"Datatype"}))
    assert finding.check == "datatype-preferred" and finding.level is Level.INFO
    assert finding.suggestion == "integer"
    assert "storage width" in finding.message


def test_datatype_extension_format_prefers_native():
    (finding,) = list(
        check_datatype_preferred(_rows((2, {"Datatype": "date_mdy"})), {"Datatype"})
    )
    assert finding.suggestion == "date"
    assert "custom type" in finding.message


def test_datatype_semantic_and_deliberate_custom_names_are_silent():
    for name in ("integer", "string", "date", "dateTime", "anyURI", "gYear", "duration"):
        assert list(check_datatype_preferred(_rows((2, {"Datatype": name})), {"Datatype"})) == []


# --- advisory: missing-unit --------------------------------------------------

def test_numeric_field_without_unit_is_nudged():
    (finding,) = list(check_units(_rows((2, {"Datatype": "decimal"})), {"Datatype"}))
    assert finding.check == "missing-unit" and finding.level is Level.INFO
    assert finding.column == "Unit"


def test_unit_present_enumerated_or_non_numeric_is_silent():
    assert list(check_units(_rows((2, {"Datatype": "decimal", "Unit": "kg"})), {"Datatype"})) == []
    assert (
        list(
            check_units(
                _rows((2, {"Datatype": "integer", "Enumeration": '"0"=[No]'})), {"Datatype"}
            )
        )
        == []
    )
    assert list(check_units(_rows((2, {"Datatype": "string"})), {"Datatype"})) == []
    # timestamp is a custom type with implicit seconds — not nudged.
    assert list(check_units(_rows((2, {"Datatype": "timestamp"})), {"Datatype"})) == []


# --- advisory: enumeration-integer-datatype ----------------------------------

def test_all_integer_enumeration_with_text_datatype_is_nudged():
    row = {"Datatype": "string", "Enumeration": '"0"=[No] | "1"=[Yes]'}
    (finding,) = list(check_enumeration_datatype(_rows((2, row)), {"Datatype", "Enumeration"}))
    assert finding.check == "enumeration-integer-datatype"
    assert finding.suggestion == "integer"


def test_enumeration_datatype_silent_when_integerish_or_not_all_integers():
    ok = {"Datatype": "int", "Enumeration": '"0"=[No]'}  # int maps to integer
    assert list(check_enumeration_datatype(_rows((2, ok)), {"Datatype", "Enumeration"})) == []
    mixed = {"Datatype": "string", "Enumeration": '"0"=[No] | "U"=[Unknown]'}
    assert list(check_enumeration_datatype(_rows((2, mixed)), {"Datatype", "Enumeration"})) == []
    malformed = {"Datatype": "string", "Enumeration": "1=No|2=Yes"}  # REDCap grammar
    assert (
        list(check_enumeration_datatype(_rows((2, malformed)), {"Datatype", "Enumeration"})) == []
    )


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


# --- precondition / required ---------------------------------------------------

def _precondition_rows(*rows):
    return list(rows), {"Id", "Datatype", "Cardinality", "Precondition", "Required"}


def test_valid_precondition_is_silent():
    from dd_validator.checks import check_preconditions
    rows, cols = _precondition_rows(
        RawRow({"Id": "smoker", "Datatype": "integer", "Precondition": ""}, 2),
        RawRow({"Id": "packs", "Datatype": "decimal", "Precondition": 'smoker = "1"'}, 3),
    )
    assert list(check_preconditions(rows, cols)) == []


def test_malformed_precondition():
    from dd_validator.checks import check_preconditions
    rows, cols = _precondition_rows(
        RawRow({"Id": "x", "Precondition": "datediff(a) > 3"}, 2),
    )
    (f,) = list(check_preconditions(rows, cols))
    assert f.check == "malformed-precondition" and f.level is Level.ERROR


def test_unknown_precondition_field():
    from dd_validator.checks import check_preconditions
    rows, cols = _precondition_rows(
        RawRow({"Id": "x", "Precondition": 'ghost = "1"'}, 2),
    )
    (f,) = list(check_preconditions(rows, cols))
    assert f.check == "unknown-precondition-field" and "ghost" in f.message


def test_ordering_on_unordered_datatype():
    from dd_validator.checks import check_preconditions
    rows, cols = _precondition_rows(
        RawRow({"Id": "name", "Datatype": "string"}, 2),
        RawRow({"Id": "x", "Precondition": "name > 5"}, 3),
    )
    (f,) = list(check_preconditions(rows, cols))
    assert f.check == "invalid-precondition-comparison"


def test_ordering_on_ordered_datatype_is_fine():
    from dd_validator.checks import check_preconditions
    rows, cols = _precondition_rows(
        RawRow({"Id": "age", "Datatype": "integer"}, 2),
        RawRow({"Id": "x", "Precondition": "age >= 18"}, 3),
    )
    assert list(check_preconditions(rows, cols)) == []


def test_contains_on_single_valued_field():
    from dd_validator.checks import check_preconditions
    rows, cols = _precondition_rows(
        RawRow({"Id": "sym", "Datatype": "integer", "Cardinality": "single"}, 2),
        RawRow({"Id": "x", "Precondition": 'sym contains "3"'}, 3),
    )
    (f,) = list(check_preconditions(rows, cols))
    assert f.check == "invalid-precondition-contains"


def test_contains_on_multivalued_field_is_fine():
    from dd_validator.checks import check_preconditions
    rows, cols = _precondition_rows(
        RawRow({"Id": "sym", "Datatype": "integer", "Cardinality": "multiple"}, 2),
        RawRow({"Id": "x", "Precondition": 'sym contains "3"'}, 3),
    )
    assert list(check_preconditions(rows, cols)) == []


def test_invalid_required_value():
    from dd_validator.checks import check_required
    (f,) = list(check_required([RawRow({"Required": "maybe"}, 2)], {"Required"}))
    assert f.check == "invalid-required"
    assert list(check_required([RawRow({"Required": "y"}, 2)], {"Required"})) == []
    assert list(check_required([RawRow({"Required": ""}, 2)], {"Required"})) == []
