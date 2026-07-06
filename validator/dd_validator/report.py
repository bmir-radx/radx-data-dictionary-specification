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
    prefix = f"{file}:" if file else ""
    lines = []
    for f in findings:
        loc = f"{prefix}{f.line}" if f.line is not None else (file or "<file>")
        line = f"{loc}: {f.level} {f.check} — {f.message}"
        lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


def _render_table(findings: Sequence[Finding], file: str, *, delimiter: str) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(_TABLE_HEADER)
    for f in findings:
        writer.writerow(
            [
                file,
                "" if f.line is None else f.line,
                f.level.name,
                f.check,
                f.message,
                f.value or "",
            ]
        )
    return buffer.getvalue()


def _render_json(findings: Sequence[Finding], file: str) -> str:
    payload = {
        "file": file,
        "findings": [
            {
                "level": f.level.name,
                "check": f.check,
                "message": f.message,
                "line": f.line,
                "column": f.column,
                "value": f.value,
            }
            for f in findings
        ],
    }
    return json.dumps(payload, indent=2) + "\n"
