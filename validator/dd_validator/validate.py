"""Run every check against a data dictionary and collect all findings."""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

from . import checks
from .model import Finding, Level
from .rows import RawRow, read_rows


def validate(
    source: str | Path | TextIO,
    *,
    check_duplicate_ids: bool = True,
) -> list[Finding]:
    """Validate a data dictionary CSV and return all findings, sorted.

    ``source`` may be a path or an open text file object. Findings are ordered
    by source line, then severity, then check name. Set ``check_duplicate_ids``
    to ``False`` to match the reference validator, which performs no cross-row
    checks.
    """
    header, rows = read_rows(source)
    findings = list(_run(header, rows, check_duplicate_ids=check_duplicate_ids))
    findings.sort(key=lambda f: f.sort_key)
    return findings


def _run(
    header: list[str], rows: list[RawRow], *, check_duplicate_ids: bool
) -> list[Finding]:
    if not header:
        return [Finding(Level.ERROR, "empty-file", "the file has no header record")]

    columns_present = set(header)
    findings: list[Finding] = []
    findings.extend(checks.check_required_headers(header))
    findings.extend(checks.check_id(rows, columns_present))
    findings.extend(checks.check_label(rows, columns_present))
    findings.extend(checks.check_datatype(rows, columns_present))
    findings.extend(checks.check_cardinality(rows, columns_present))
    findings.extend(checks.check_pattern(rows, columns_present))
    findings.extend(checks.check_enumeration(rows, columns_present))
    findings.extend(checks.check_missing_value_codes(rows, columns_present))
    findings.extend(checks.check_see_also(rows, columns_present))
    if check_duplicate_ids:
        findings.extend(checks.check_duplicate_ids(rows, columns_present))
    return findings
