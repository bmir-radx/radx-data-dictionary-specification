"""Read a data dictionary CSV into raw rows, without validating.

The converter's :func:`dd_core.read_data_dictionary` is *fail-fast*: it
raises on the first duplicate Id, blank required cell, or bad header. A
validator must instead collect *every* problem, so it cannot use that reader as
its front door. This module reads the CSV at the same raw level the converter's
reader does (stdlib :mod:`csv`, ``utf-8-sig``, RFC 4180), but performs no
validation — every data problem is left for the checks to report.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True)
class RawRow:
    """One data record, exactly as read (no validation).

    ``cells`` maps column header -> raw cell string (empty string for a blank or
    absent cell). ``line`` is the 1-based line number in the source file.
    """

    cells: dict[str, str]
    line: int

    def get(self, column: str) -> str:
        """Return the raw cell for ``column`` (empty string if absent/blank)."""
        return self.cells.get(column, "")


def read_rows(source: str | Path | TextIO) -> tuple[list[str], list[RawRow]]:
    """Read a CSV into ``(header, rows)`` without raising on data problems.

    Returns the header as a list of (stripped) column names and the data rows in
    file order. An empty file yields ``([], [])``. Wholly blank lines are
    skipped, matching the converter's reader.
    """
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8-sig", newline="") as handle:
            return _read(handle)
    return _read(source)


def _read(handle: TextIO) -> tuple[list[str], list[RawRow]]:
    reader = csv.reader(handle)  # RFC 4180 defaults: comma, double-quote
    try:
        raw_header = next(reader)
    except StopIteration:
        return [], []

    # Strip a UTF-8 BOM from the first header cell if a caller-supplied stream
    # carried one (a path opened above uses utf-8-sig, which removes it).
    if raw_header and raw_header[0].startswith("﻿"):
        raw_header[0] = raw_header[0].lstrip("﻿")
    header = [h.strip() for h in raw_header]

    rows: list[RawRow] = []
    for offset, raw_cells in enumerate(reader):
        line = offset + 2  # +1 for header, +1 for 1-based
        if not any(cell.strip() for cell in raw_cells):
            continue  # skip wholly blank lines
        cells = {
            header[i]: (raw_cells[i] if i < len(raw_cells) else "")
            for i in range(len(header))
        }
        rows.append(RawRow(cells=cells, line=line))

    return header, rows
