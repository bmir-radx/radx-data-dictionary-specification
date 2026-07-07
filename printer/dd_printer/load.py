"""Load a data dictionary into the printer model.

Input may be a data dictionary **CSV** or a **LinkML schema** — both are
loaded through the high-level ``dd_api`` model and then mapped onto the
printer's presentation model (:class:`Dictionary` / :class:`Section` /
:class:`Record`), which is shaped for rendering rather than for general use.
"""

from __future__ import annotations

import io
from pathlib import Path

import yaml
from dd_api import DataDictionary, DataElement

from .model import Choice, Dictionary, Record, Section


def _looks_like_schema(text: str) -> bool:
    """A LinkML schema has top-level ``classes:`` (a dictionary CSV starts
    with an ``Id,...`` header)."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    return isinstance(data, dict) and "classes" in data


def _build_dictionary(dd: DataDictionary, title: str) -> Dictionary:
    """Group the model's elements into sections of numbered records."""
    sections: dict[str, Section] = {}  # section name -> Section (insertion order)
    for position, element in enumerate(dd, start=1):
        record = _record_from_element(element, position)
        section = sections.setdefault(record.section, Section(name=record.section))
        section.records.append(record)
    return Dictionary(title=title, sections=list(sections.values()))


def _record_from_element(element: DataElement, number: int) -> Record:
    """Map one model element onto a presentation record.

    The model's ``None`` blanks become empty strings (what the templates
    expect), and enumeration choices that are also missing-value codes are
    flagged so the renderer can style them distinctly.
    """
    missing_code_values = {code.value for code in element.missing_value_codes}
    choices = [
        Choice(
            value=item.value,
            label=item.label or "",
            meaning=item.iri,
            is_missing_value_code=item.value in missing_code_values,
        )
        for item in element.enumeration
    ]
    return Record(
        number=number,
        id=element.id,
        label=element.label,
        description=element.description or "",
        section=element.section or "",
        datatype=element.datatype,
        cardinality=element.cardinality,
        unit=element.unit or "",
        pattern=element.pattern or "",
        precondition=element.precondition or "",
        required=element.required,
        terms=list(element.terms),
        choices=choices,
        notes=element.notes or "",
        provenance=element.provenance or "",
        see_also=element.see_also or "",
    )


def load_dictionary(source, title: str | None = None) -> Dictionary:
    """Load a :class:`Dictionary` from a path (CSV or LinkML schema) or text stream.

    The input kind is detected from the content (LinkML schemas have a top-level
    ``classes:`` key); CSV is assumed otherwise. ``title`` defaults to the input
    filename stem. Duplicate ids are tolerated (first occurrence wins), so real
    dictionaries render even when imperfect.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        text = path.read_text(encoding="utf-8-sig")
        resolved_title = title or path.stem
    else:  # a text stream
        text = source.read()
        resolved_title = title or "Data Dictionary"

    if _looks_like_schema(text):
        dd = DataDictionary.from_linkml(io.StringIO(text))
    else:
        dd = DataDictionary.load(io.StringIO(text), allow_duplicates=True)
    return _build_dictionary(dd, resolved_title)
