"""Run every check against a data dictionary and collect all findings."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from . import checks
from .model import Finding, Level
from .rows import RawRow, read_rows


def validate(
    source: str | Path | TextIO,
    *,
    check_duplicate_ids: bool = True,
    ignore: Collection[str] = (),
) -> list[Finding]:
    """Validate a data dictionary CSV and return all findings, sorted.

    ``source`` may be a path or an open text file object. Findings are ordered
    by source line, then severity, then check name. Set ``check_duplicate_ids``
    to ``False`` to match the reference validator, which performs no cross-row
    checks. ``ignore`` drops findings by check name (e.g. ``{"missing-unit"}``)
    so a pipeline can tune out advisory checks it disagrees with.
    """
    header, rows = read_rows(source)
    findings = _run_all_checks(header, rows, check_duplicate_ids=check_duplicate_ids)
    if ignore:
        ignored = set(ignore)
        findings = [f for f in findings if f.check not in ignored]
    findings = _address_findings(findings, rows)
    findings.sort(key=lambda finding: finding.sort_key)
    return findings


def _address_findings(findings: list[Finding], rows: list[RawRow]) -> list[Finding]:
    """Fill each row finding's format-independent address from its line.

    Checks report the CSV line they are looking at; this single pass maps the
    line to (``element_index``, ``element_id``) — the 0-based document-order
    position and the row's Id — so every check, present and future, becomes
    addressable without touching its construction sites.
    """
    by_line = {
        row.line: (index, row.get("Id").strip() or None) for index, row in enumerate(rows)
    }
    return [
        replace(f, element_index=by_line[f.line][0], element_id=by_line[f.line][1])
        if f.line in by_line
        else f
        for f in findings
    ]


def _run_all_checks(
    header: list[str], rows: list[RawRow], *, check_duplicate_ids: bool
) -> list[Finding]:
    """Run every check and return the unsorted findings.

    A file with no header record at all cannot be checked further, so that is
    the single finding it produces.
    """
    if not header:
        return [Finding(Level.ERROR, "empty-file", "the file has no header record")]

    columns_present = set(header)
    findings: list[Finding] = []
    findings.extend(checks.check_required_headers(header))
    findings.extend(checks.check_id(rows, columns_present))
    findings.extend(checks.check_label(rows, columns_present))
    findings.extend(checks.check_datatype(rows, columns_present))
    findings.extend(checks.check_datatype_preferred(rows, columns_present))
    findings.extend(checks.check_cardinality(rows, columns_present))
    findings.extend(checks.check_pattern(rows, columns_present))
    findings.extend(checks.check_enumeration(rows, columns_present))
    findings.extend(checks.check_enumeration_datatype(rows, columns_present))
    findings.extend(checks.check_units(rows, columns_present))
    findings.extend(checks.check_cell_whitespace(rows, columns_present))
    findings.extend(checks.check_missing_value_codes(rows, columns_present))
    findings.extend(checks.check_preconditions(rows, columns_present))
    findings.extend(checks.check_required(rows, columns_present))
    findings.extend(checks.check_see_also(rows, columns_present))
    if check_duplicate_ids:
        findings.extend(checks.check_duplicate_ids(rows, columns_present))
    return findings
