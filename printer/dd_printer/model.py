"""The printer's neutral data-dictionary model.

Plain dataclasses describing a dictionary for rendering: it has ordered
sections, each with numbered records (data elements), each of which may carry an
enumeration of choices. There is no dependency on any particular source format
and no RADx-specific concepts.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Choice:
    """One permissible value of an enumerated field."""

    value: str
    label: str = ""
    meaning: str | None = None  # ontology term identifier, if any
    is_missing_value_code: bool = False


@dataclass
class Record:
    """One data element (a field of the described datafile)."""

    number: int  # 1-based position across the whole dictionary
    id: str
    label: str = ""
    description: str = ""  # source Markdown (rendered to HTML at print time)
    section: str = ""
    datatype: str = ""
    cardinality: str = ""  # "single" / "multiple"
    unit: str = ""
    pattern: str = ""
    precondition: str = ""  # when the field applies (spec Precondition grammar)
    required: bool = False
    terms: list[str] = field(default_factory=list)
    choices: list[Choice] = field(default_factory=list)  # the enumeration, if any
    notes: str = ""
    provenance: str = ""
    see_also: str = ""

    @property
    def is_multivalued(self) -> bool:
        return self.cardinality.strip().lower() == "multiple"

    @property
    def has_enumeration(self) -> bool:
        return bool(self.choices)


@dataclass
class Section:
    """A named group of records (a dictionary Section)."""

    name: str
    records: list[Record] = field(default_factory=list)


@dataclass
class Dictionary:
    """A whole data dictionary, grouped into ordered sections."""

    title: str
    sections: list[Section] = field(default_factory=list)

    @property
    def records(self) -> list[Record]:
        return [r for s in self.sections for r in s.records]

    def ids(self) -> set[str]:
        return {r.id for r in self.records}
