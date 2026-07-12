"""Render findings in one of several formats.

``text`` is the human-friendly default. ``csv`` and ``tsv`` are tabular (the
header and data columns agree — a single ``File`` column, unlike the reference
validator's writer which emitted a header column with no data). ``json`` is the
machine-readable path, consistent with the other tools in this repository.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence

from .model import Finding

FORMATS = ("text", "csv", "tsv", "json")

_TABLE_HEADER = ("File", "Row", "Level", "Check", "Message", "Value")


def render(findings: Sequence[Finding], fmt: str = "text", *, file: str = "") -> str:
    """Render ``findings`` as ``fmt`` (one of :data:`FORMATS`).

    ``file`` names the source, used in the ``text`` prefix and the ``File``
    table column.
    """
    if fmt == "text":
        return _render_text(findings, file)
    if fmt in ("csv", "tsv"):
        return _render_table(findings, file, delimiter="\t" if fmt == "tsv" else ",")
    if fmt == "json":
        return _render_json(findings, file)
    raise ValueError(f"unknown report format: {fmt!r}")


def _render_text(findings: Sequence[Finding], file: str) -> str:
    lines = []
    for finding in findings:
        # "file.csv:12" for a row finding; just the file name for a
        # whole-file finding (e.g. a missing header) with no line number.
        if finding.line is not None:
            location = f"{file}:{finding.line}" if file else str(finding.line)
        else:
            location = file or "<file>"
        lines.append(f"{location}: {finding.level} {finding.check} — {finding.message}")
    return "\n".join(lines) + ("\n" if lines else "")


def _render_table(findings: Sequence[Finding], file: str, *, delimiter: str) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(_TABLE_HEADER)
    for finding in findings:
        writer.writerow(
            [
                file,
                "" if finding.line is None else finding.line,
                finding.level.name,
                finding.check,
                finding.message,
                finding.value or "",
            ]
        )
    return buffer.getvalue()


def _render_json(findings: Sequence[Finding], file: str) -> str:
    payload = {
        "file": file,
        "findings": [
            {
                "level": finding.level.name,
                "check": finding.check,
                "message": finding.message,
                "line": finding.line,
                "column": finding.column,
                "value": finding.value,
                # The format-independent address (document-order position and
                # Id) and the machine-usable fix, when the check has one.
                "elementIndex": finding.element_index,
                "elementId": finding.element_id,
                "suggestion": finding.suggestion,
            }
            for finding in findings
        ],
    }
    return json.dumps(payload, indent=2) + "\n"
