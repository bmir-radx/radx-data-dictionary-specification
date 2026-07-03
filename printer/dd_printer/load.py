"""Load a data dictionary into the printer model.

Input may be a data dictionary **CSV** or a generated **LinkML schema** — both
are read via the sibling ``radx_dd_converter`` package and normalised to the same
list of column dicts, then grouped into the printer's :class:`Dictionary` model.
"""

from __future__ import annotations

import io
from pathlib import Path

import yaml

from radx_dd_converter import read_data_dictionary, schema_to_rows
from radx_dd_converter.grammar import parse_enumeration, parse_missing_value_codes, parse_terms

from .model import Choice, Dictionary, Record, Section


def _rows_from_csv(source) -> list[dict]:
    """Read a data dictionary CSV into a list of column dicts."""
    rows = read_data_dictionary(source, allow_duplicates=True)
    return [dict(r.cells) for r in rows]


def _rows_from_schema(text: str) -> list[dict]:
    """Read a generated LinkML schema (YAML text) into a list of column dicts."""
    return schema_to_rows(yaml.safe_load(text))


def _looks_like_schema(text: str) -> bool:
    """A generated LinkML schema has top-level ``classes:`` (a dictionary CSV
    starts with an ``Id,...`` header)."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    return isinstance(data, dict) and "classes" in data


def _build_dictionary(rows: list[dict], title: str) -> Dictionary:
    """Group column dicts into sections of numbered records."""
    sections: dict[str, Section] = {}  # section name -> Section (insertion order)
    for position, cells in enumerate(rows, start=1):
        record = _record_from_cells(cells, position)
        section = sections.setdefault(record.section, Section(name=record.section))
        section.records.append(record)
    return Dictionary(title=title, sections=list(sections.values()))


def _record_from_cells(cells: dict, number: int) -> Record:
    def cell(name: str) -> str:
        return (cells.get(name) or "").strip()

    # Missing-value-code values, to flag them among the choices.
    mvc_values = {c.value for c in parse_missing_value_codes(cells.get("MissingValueCodes") or "")}
    choices = [
        Choice(
            value=item.value,
            label=item.label or "",
            meaning=item.iri,
            is_missing_value_code=item.value in mvc_values,
        )
        for item in parse_enumeration(cells.get("Enumeration") or "")
    ]
    return Record(
        number=number,
        id=cell("Id"),
        label=cell("Label"),
        description=cells.get("Description") or "",
        section=cell("Section"),
        datatype=cell("Datatype"),
        cardinality=cell("Cardinality"),
        unit=cell("Unit"),
        pattern=cells.get("Pattern") or "",
        terms=parse_terms(cells.get("Terms") or ""),
        choices=choices,
        notes=cells.get("Notes") or "",
        provenance=cell("Provenance"),
        see_also=cell("SeeAlso"),
    )


def load_dictionary(source, title: str | None = None) -> Dictionary:
    """Load a :class:`Dictionary` from a path (CSV or LinkML schema) or text stream.

    The input kind is detected from the content (LinkML schemas have a top-level
    ``classes:`` key); CSV is assumed otherwise. ``title`` defaults to the input
    filename stem.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        text = path.read_text(encoding="utf-8-sig")
        resolved_title = title or path.stem
    else:  # a text stream
        text = source.read()
        resolved_title = title or "Data Dictionary"

    if _looks_like_schema(text):
        rows = _rows_from_schema(text)
    else:
        rows = _rows_from_csv(io.StringIO(text))
    return _build_dictionary(rows, resolved_title)
