"""Convert a REDCap data dictionary into the toolkit's model.

One REDCap row becomes one :class:`~dd_api.DataElement` (rows of Field Type
``descriptive`` are display text, not fields, and are skipped). The result is
a :class:`~dd_api.DataDictionary`, so writing the converted dictionary out is
just ``dd.to_csv()`` and everything downstream (printer, validator, LinkML)
works on it directly.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TextIO

from dd_api import DataDictionary, DataElement, EnumItem

from . import headers
from .branching import explain_branching_logic
from .choices import parse_choices
from .datatypes import extract_datatype
from .headers import RedCapSheet, read_sheet

logger = logging.getLogger(__name__)

# A @NONEOFTHEABOVE field-annotation action names the choice values that are
# mutually exclusive with all others, e.g. @NONEOFTHEABOVE = '98,99'.
_NONE_OF_THE_ABOVE = re.compile(r"@NONEOFTHEABOVE\s*=\s*['\"](\d+)((?:,\d+)*)['\"]")


def convert_redcap(source: str | Path | TextIO, *, provenance: str = "") -> DataDictionary:
    """Convert a REDCap data dictionary CSV into a :class:`DataDictionary`.

    ``source`` may be a path or an open text file; ``provenance`` fills every
    element's Provenance column (e.g. the study or instrument name). Raises
    :class:`~dd_redcap.ConversionError` when the file is not a REDCap
    dictionary, and ``ValueError`` when two rows share a Variable name.
    """
    sheet = read_sheet(source)
    elements: list[DataElement] = []
    current_section = ""
    for row in sheet.rows:
        field_type = sheet.get(row, headers.FIELD_TYPE)
        if field_type == "descriptive":
            continue  # display text on the form, not a data field
        # Section headers are not filled down in REDCap exports: a blank cell
        # means "still in the previous section".
        if sheet.get(row, headers.SECTION_HEADER):
            current_section = sheet.get(row, headers.SECTION_HEADER)
        field_id = sheet.get(row, headers.VARIABLE)
        if not field_id:
            logger.warning("Skipping a row with no Variable / Field Name value.")
            continue
        elements.append(_element_from_row(sheet, row, field_id, current_section, provenance))
    return DataDictionary(elements)


def _element_from_row(
    sheet: RedCapSheet, row: list[str], field_id: str, section: str, provenance: str
) -> DataElement:
    label = _build_label(sheet, row)
    choices = parse_choices(sheet.get(row, headers.CHOICES))
    datatype = extract_datatype(sheet, row)
    return DataElement(
        id=field_id,
        label=label,
        datatype=datatype,
        description=_build_description(sheet, row, field_id, label, choices, datatype),
        section=section or None,
        cardinality="multiple" if sheet.get(row, headers.FIELD_TYPE) == "checkbox" else "single",
        enumeration=tuple(
            EnumItem(value=value, label=choice_label) for value, choice_label in choices.items()
        ),
        notes=_notes_from_annotations(sheet, row) or None,
        provenance=provenance or None,
    )


def _build_label(sheet: RedCapSheet, row: list[str]) -> str:
    """The Field Label, with a non-blank Field Note appended in parentheses."""
    label = sheet.get(row, headers.FIELD_LABEL)
    note = sheet.get(row, headers.FIELD_NOTE)
    return f"{label} ({note})" if note else label


def _build_description(
    sheet: RedCapSheet,
    row: list[str],
    field_id: str,
    label: str,
    choices: dict[str, str],
    datatype: str,
) -> str:
    """Generated prose: the prompt, the permissible values, the branching logic."""
    paragraphs = [
        f'The `{field_id}` variable records response to the prompt, _"{label}"_.',
        _describe_values(sheet, row, choices, datatype),
        explain_branching_logic(sheet, row),
    ]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _describe_values(
    sheet: RedCapSheet, row: list[str], choices: dict[str, str], datatype: str
) -> str:
    """A sentence about the permissible values, for enumerated fields."""
    if not choices:
        return ""
    sentence = (
        f"Values for this variable are {datatype}s that are restricted to the "
        f"list of {len(choices)} permissible {datatype} values."
    )
    exclusive = _mutually_exclusive_values(sheet, row)
    if exclusive:
        listed = ",".join(f"`{value}`" for value in exclusive)
        word, verb = ("value", "is") if len(exclusive) == 1 else ("values", "are")
        sentence += (
            f"  The {word} {listed} {verb} mutually exclusive with any other values."
        )
    return sentence


def _mutually_exclusive_values(sheet: RedCapSheet, row: list[str]) -> list[str]:
    """Choice values named by @NONEOFTHEABOVE actions in the Field Annotation."""
    values: list[str] = []
    for annotation in sheet.get(row, headers.FIELD_ANNOTATION).split("|"):
        match = _NONE_OF_THE_ABOVE.search(annotation)
        if match:
            values.extend(v.strip() for v in (match.group(1) + match.group(2)).split(","))
    return values


def _notes_from_annotations(sheet: RedCapSheet, row: list[str]) -> str:
    """Field Annotation entries as Notes paragraphs.

    ``@NONEOFTHEABOVE`` actions are dropped — they are already explained in
    the generated description.
    """
    annotations = sheet.get(row, headers.FIELD_ANNOTATION).split("|")
    kept = [a.strip() for a in annotations if a.strip() and not _NONE_OF_THE_ABOVE.search(a)]
    return "\n\n".join(kept)
