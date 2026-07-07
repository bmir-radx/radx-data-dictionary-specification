"""The REDCap column vocabulary, and reading a REDCap sheet by column name.

REDCap exports name their columns verbosely (``Variable / Field Name``,
``Choices, Calculations, OR Slider Labels``), and hand-edited copies often
shorten them. Each column here carries its synonyms; matching is
case-insensitive on the trimmed header text.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TextIO

# Canonical REDCap column name -> accepted spellings (all compared lowercase).
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "Variable / Field Name": ("variable", "field name"),
    "Form Name": (),
    "Section Header": ("section",),
    "Field Type": ("type",),
    "Field Label": ("label", "prompt"),
    "Choices, Calculations, OR Slider Labels": ("choices",),
    "Field Note": (),
    "Text Validation Type OR Show Slider Number": ("text validation",),
    "Text Validation Min": (),
    "Text Validation Max": (),
    "Identifier?": (),
    "Branching Logic (Show field only if...)": ("branching logic",),
    "Required Field?": (),
    "Custom Alignment": (),
    "Question Number (surveys only)": (),
    "Matrix Group Name": (),
    "Matrix Ranking?": (),
    "Field Annotation": (),
}

# Short names used throughout the package, mapped to the canonical header.
VARIABLE = "Variable / Field Name"
SECTION_HEADER = "Section Header"
FIELD_TYPE = "Field Type"
FIELD_LABEL = "Field Label"
CHOICES = "Choices, Calculations, OR Slider Labels"
FIELD_NOTE = "Field Note"
TEXT_VALIDATION = "Text Validation Type OR Show Slider Number"
BRANCHING_LOGIC = "Branching Logic (Show field only if...)"
FIELD_ANNOTATION = "Field Annotation"


class ConversionError(ValueError):
    """Raised when a file cannot be converted (e.g. no Variable column)."""


class RedCapSheet:
    """A parsed REDCap data dictionary CSV, addressable by canonical column.

    ``sheet.get(row, VARIABLE)`` returns the cell for the Variable column of
    ``row`` (an index into :attr:`rows`), or ``""`` when the column is absent
    or the cell blank — sparse, hand-edited exports are the norm.
    """

    def __init__(self, header: list[str], rows: list[list[str]]):
        self.rows = rows
        self._column_index: dict[str, int] = {}
        normalised = [cell.strip().lower() for cell in header]
        for canonical, synonyms in _SYNONYMS.items():
            accepted = {canonical.lower(), *synonyms}
            for index, header_cell in enumerate(normalised):
                if header_cell in accepted:
                    self._column_index[canonical] = index
                    break

    def has_column(self, canonical: str) -> bool:
        return canonical in self._column_index

    def get(self, row: list[str], canonical: str) -> str:
        """The (stripped) cell of ``row`` for a canonical column, else ``""``."""
        index = self._column_index.get(canonical)
        if index is None or index >= len(row):
            return ""
        return row[index].strip()

    def row_with_id(self, field_id: str) -> list[str] | None:
        """The first data row whose Variable cell equals ``field_id``."""
        for row in self.rows:
            if self.get(row, VARIABLE) == field_id:
                return row
        return None


def read_sheet(source: str | Path | TextIO) -> RedCapSheet:
    """Read a REDCap data dictionary CSV into a :class:`RedCapSheet`.

    Raises :class:`ConversionError` if the file is empty or has no
    recognisable Variable / Field Name column (it is not a REDCap dictionary).
    """
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8-sig", newline="") as handle:
            return _read(handle)
    return _read(source)


def _read(handle: TextIO) -> RedCapSheet:
    reader = csv.reader(handle)
    try:
        header = next(reader)
    except StopIteration:
        raise ConversionError("The file is empty (no header record).") from None
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    sheet = RedCapSheet(header, rows)
    if not sheet.has_column(VARIABLE):
        raise ConversionError(
            "No 'Variable / Field Name' column found — this does not look "
            "like a REDCap data dictionary."
        )
    return sheet
