"""Read a RADx data dictionary CSV into ordered rows.

The reader parses the CSV per RFC 4180 (via the standard library ``csv``
module), validates the header record, and returns an ordered list of
:class:`Row` objects. Row order is preserved because the specification says the
order of data-dictionary records is significant: it corresponds to the order of
the fields in the target datafile.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, TextIO, Union

logger = logging.getLogger(__name__)

# The canonical header sequence from the specification. Order here is the
# recommended order; the reader does not require this order (columns are keyed
# by name), but uses the set to distinguish known from extra columns.
KNOWN_COLUMNS: Sequence[str] = (
    "Id",
    "Aliases",
    "Label",
    "Description",
    "Section",
    "Cardinality",
    "Terms",
    "Datatype",
    "Pattern",
    "Unit",
    "Enumeration",
    "MissingValueCodes",
    "Examples",
    "Notes",
    "Provenance",
    "SeeAlso",
)

# Fields whose value must be present and non-empty (Value Status: REQUIRED).
REQUIRED_COLUMNS: Sequence[str] = ("Id", "Label", "Datatype")


class ReadError(ValueError):
    """Raised when a data dictionary CSV cannot be read or is invalid."""


@dataclass(frozen=True)
class Row:
    """One data element (non-header record) of a data dictionary.

    ``cells`` maps column header -> raw cell string (empty string for blank
    cells). ``line`` is the 1-based line number in the source file, for error
    messages. Extra (non-canonical) columns are preserved in ``cells`` and
    listed in ``extra_columns``.
    """

    cells: Dict[str, str]
    line: int
    extra_columns: Sequence[str] = field(default_factory=tuple)

    def get(self, column: str) -> str:
        """Return the raw cell for ``column`` (empty string if absent/blank)."""
        return self.cells.get(column, "")

    @property
    def id(self) -> str:
        return self.get("Id")


def _validate_header(header: Sequence[str]) -> List[str]:
    """Validate the header record; return the list of extra (non-canonical) columns."""
    columns = [h.strip() for h in header]
    # Duplicate headers make column-by-name access ambiguous.
    duplicates = {c for c in columns if columns.count(c) > 1}
    if duplicates:
        raise ReadError(f"Duplicate column header(s): {', '.join(sorted(duplicates))}")
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise ReadError(
            "Missing required column header(s): " + ", ".join(missing)
        )
    return [c for c in columns if c and c not in KNOWN_COLUMNS]


def read_data_dictionary(
    source: Union[str, Path, TextIO],
    *,
    allow_duplicates: bool = False,
) -> List[Row]:
    """Read a data dictionary CSV and return its rows in order.

    ``source`` may be a path (``str``/``Path``) or an open text file object.

    Raises :class:`ReadError` on a malformed header, a blank required cell, or a
    duplicate ``Id``. When ``allow_duplicates`` is true, a duplicate ``Id`` is
    not fatal: the first occurrence is kept, later occurrences are skipped, and
    a warning is logged for each.
    """
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8-sig", newline="") as handle:
            return _read(handle, allow_duplicates)
    return _read(source, allow_duplicates)


def _read(handle: TextIO, allow_duplicates: bool = False) -> List[Row]:
    reader = csv.reader(handle)  # RFC 4180 defaults: comma, double-quote
    try:
        header = next(reader)
    except StopIteration:
        raise ReadError("Data dictionary is empty (no header record).")

    # Strip a UTF-8 BOM from the first header cell. Opening a path uses
    # encoding="utf-8-sig" which removes it, but a caller-supplied stream may
    # still carry one (e.g. a file opened as plain utf-8).
    if header and header[0].startswith("﻿"):
        header[0] = header[0].lstrip("﻿")

    header = [h.strip() for h in header]
    extra_columns = tuple(_validate_header(header))

    rows: List[Row] = []
    seen_ids: Dict[str, int] = {}
    for offset, raw_cells in enumerate(reader):
        line = offset + 2  # +1 for header, +1 for 1-based
        if not any(cell.strip() for cell in raw_cells):
            continue  # skip wholly blank lines

        cells = {
            header[i]: (raw_cells[i] if i < len(raw_cells) else "")
            for i in range(len(header))
        }

        for required_column in REQUIRED_COLUMNS:
            if cells.get(required_column, "").strip() == "":
                raise ReadError(
                    f"Line {line}: required column {required_column!r} is blank."
                )

        row_id = cells["Id"].strip()
        if row_id in seen_ids:
            if allow_duplicates:
                logger.warning(
                    "Line %d: duplicate Id %r (first seen on line %d); skipping "
                    "this occurrence.",
                    line,
                    row_id,
                    seen_ids[row_id],
                )
                continue
            raise ReadError(
                f"Line {line}: duplicate Id {row_id!r} "
                f"(first seen on line {seen_ids[row_id]})."
            )
        seen_ids[row_id] = line

        rows.append(Row(cells=cells, line=line, extra_columns=extra_columns))

    return rows
