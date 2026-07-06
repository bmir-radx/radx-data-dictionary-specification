"""Tests for the orchestrator and the raw-row reader."""

import io

from dd_validator import validate
from dd_validator.model import Level
from dd_validator.rows import read_rows

CLEAN = "Id,Label,Datatype\nage,Age,integer\nweight,Weight,decimal\n"


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


def test_read_rows_skips_blank_lines_and_strips_bom():
    text = "﻿Id,Label,Datatype\nage,Age,integer\n\n\nweight,Weight,decimal\n"
    header, rows = read_rows(io.StringIO(text))
    assert header == ["Id", "Label", "Datatype"]
    assert [r.get("Id") for r in rows] == ["age", "weight"]
    assert [r.line for r in rows] == [2, 5]  # line numbers reflect the blank gaps
