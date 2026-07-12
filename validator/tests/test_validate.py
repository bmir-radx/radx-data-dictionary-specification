"""Tests for the orchestrator and the raw-row reader."""

import io

from dd_validator import validate
from dd_validator.model import Level
from dd_validator.rows import read_rows

# Clean means clean under every check, the advisory ones included — the
# numeric fields carry units, so missing-unit stays silent.
CLEAN = "Id,Label,Datatype,Unit\nage,Age,integer,a\nweight,Weight,decimal,kg\n"


def _validate(text, **kwargs):
    return validate(io.StringIO(text), **kwargs)


def test_clean_dictionary_has_no_findings():
    assert _validate(CLEAN) == []


def test_empty_file_reports_empty_file():
    (f,) = _validate("")
    assert f.check == "empty-file" and f.level is Level.ERROR


def test_findings_sorted_by_line_then_severity():
    text = (
        "Id,Label,Datatype\n"
        "a,,integer\n"        # line 2: label warning
        " b,B,Nope\n"          # line 3: id error + info, datatype error
    )
    findings = _validate(text)
    # sorted: line 2 first, then line 3 errors before info
    assert findings[0].line == 2
    lines_levels = [(f.line, f.level) for f in findings]
    assert lines_levels == sorted(lines_levels, key=lambda x: (x[0], x[1].order))


def test_duplicate_check_toggle():
    text = CLEAN + "age,Age2,integer\n"
    with_dup = [f for f in _validate(text) if f.check == "duplicate-id"]
    without = [f for f in _validate(text, check_duplicate_ids=False) if f.check == "duplicate-id"]
    assert len(with_dup) == 1 and without == []


def test_missing_required_header():
    text = "Id,Datatype\na,integer\n"
    checks = {f.check for f in _validate(text)}
    assert "required-header" in checks


def test_optional_column_absent_is_not_flagged():
    # No Cardinality/Pattern/SeeAlso columns: their checks must stay silent.
    findings = _validate(CLEAN)
    assert findings == []


def test_findings_carry_format_independent_address():
    text = (
        "Id,Label,Datatype,Unit\n"
        "age,Age,integer,a\n"
        "bmi,,decimal,kg/m2\n"  # line 3 = element index 1: label warning
    )
    (finding,) = _validate(text)
    assert finding.check == "label-missing"
    assert finding.line == 3
    assert (finding.element_index, finding.element_id) == (1, "bmi")


def test_addressing_survives_blank_lines():
    # A blank line shifts CSV line numbers but not element indexes.
    text = "Id,Label,Datatype,Unit\nage,Age,integer,a\n\nbmi,,decimal,kg/m2\n"
    (finding,) = _validate(text)
    assert finding.line == 4
    assert (finding.element_index, finding.element_id) == (1, "bmi")


def test_whole_file_findings_have_no_element_address():
    (finding,) = _validate("")
    assert finding.element_index is None and finding.element_id is None


def test_ignore_drops_findings_by_check_name():
    text = "Id,Label,Datatype\nage,Age,integer\n"  # numeric, no Unit column
    assert any(f.check == "missing-unit" for f in _validate(text))
    remaining = _validate(text, ignore={"missing-unit"})
    assert all(f.check != "missing-unit" for f in remaining)


def test_read_rows_skips_blank_lines_and_strips_bom():
    text = "﻿Id,Label,Datatype\nage,Age,integer\n\n\nweight,Weight,decimal\n"
    header, rows = read_rows(io.StringIO(text))
    assert header == ["Id", "Label", "Datatype"]
    assert [r.get("Id") for r in rows] == ["age", "weight"]
    assert [r.line for r in rows] == [2, 5]  # line numbers reflect the blank gaps
