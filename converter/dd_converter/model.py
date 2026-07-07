"""A high-level, typed object model for data dictionaries.

This is the programmatic front door to the toolkit. Where
:func:`~dd_converter.reader.read_data_dictionary` returns rows of raw cell
strings, this module parses every cell up front and hands back plain, typed
objects::

    from dd_converter import DataDictionary

    dd = DataDictionary.load("my_dictionary.csv")

    for element in dd:                     # elements, in file order
        print(element.id, element.label, element.datatype)
        for choice in element.enumeration: # parsed "value"=[label](iri) pairs
            print(" ", choice.value, choice.label)

    age = dd["age"]                        # lookup by id (KeyError if absent)
    "weight" in dd                         # membership test by id
    dd.sections                            # section names, in order
    schema_yaml = dd.to_linkml()           # the LinkML rendering

Loading is **fail-fast**: every cell is parsed eagerly, and the first problem
raises :class:`~dd_converter.reader.ReadError` with the line number in the
message (the specific parse error is chained as the cause). An object you get
back is therefore known-good — no deferred surprises when an attribute is
first touched. To list *all* problems in a dictionary instead of stopping at
the first, use the validator tool (``dd-validate``), which exists for exactly
that.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from .datatypes import resolve_datatype
from .emit import EmitOptions, emit_schema
from .grammar import (
    EnumItem,
    parse_enumeration,
    parse_missing_value_codes,
    parse_terms,
)
from .reader import ReadError, Row, read_data_dictionary
from .units import UnitOfMeasure, lookup_unit


@dataclass(frozen=True)
class DataElement:
    """One data element (row) of a data dictionary, fully parsed.

    Blank optional cells become ``None`` (for single values) or an empty tuple
    (for lists), so ``if element.description:`` and ``for term in
    element.terms:`` both read naturally.
    """

    id: str
    """The unique field identifier (the ``Id`` column)."""

    label: str
    """The human-readable field name (the ``Label`` column)."""

    datatype: str
    """The datatype name, e.g. ``"integer"`` — validated against the
    specification's datatype set at load time."""

    aliases: tuple[str, ...] = ()
    """Alternative identifiers for the field (pipe-delimited in the CSV)."""

    description: str | None = None
    """What the field means, or ``None`` when not given."""

    section: str | None = None
    """The section (group of related fields) this element belongs to, or
    ``None`` when the dictionary does not use sections."""

    cardinality: str = "single"
    """``"single"`` (one value per cell — the default) or ``"multiple"``."""

    terms: tuple[str, ...] = ()
    """Ontology term identifiers attached to the field: full IRIs or compact
    OBO ids like ``UBERON:0001836``."""

    pattern: str | None = None
    """The XSD regular expression values must match, or ``None``. Kept as
    written — XSD regex syntax is not Python's, so it is not compiled here."""

    unit: str | None = None
    """The unit of measure exactly as written in the CSV, or ``None``."""

    unit_of_measure: UnitOfMeasure | None = None
    """The structured unit (name, symbol, UCUM code) when :attr:`unit` is one
    the specification's unit table recognises; otherwise ``None``."""

    enumeration: tuple[EnumItem, ...] = ()
    """The permissible values, parsed from the ``"value"=[label](iri)``
    notation. Empty when the field is not enumerated."""

    missing_value_codes: tuple[EnumItem, ...] = ()
    """Codes that mean "no data" (same notation as :attr:`enumeration`)."""

    examples: tuple[str, ...] = ()
    """Example values (pipe-delimited in the CSV)."""

    notes: str | None = None
    """Free-text notes, or ``None``."""

    provenance: str | None = None
    """Where the field came from, or ``None``."""

    see_also: str | None = None
    """A URL with more information, or ``None``."""

    line: int = 0
    """The 1-based line number of this element in the source CSV."""

    row: Row | None = field(default=None, repr=False)
    """The underlying raw :class:`~dd_converter.reader.Row` — the escape hatch
    for anything the typed fields do not cover (e.g. non-standard columns).
    ``None`` only when a :class:`DataElement` is constructed by hand."""

    @property
    def is_enumerated(self) -> bool:
        """Whether the element restricts values to an enumeration."""
        return len(self.enumeration) > 0

    @property
    def is_multiple(self) -> bool:
        """Whether a cell may hold multiple values (cardinality ``multiple``)."""
        return self.cardinality == "multiple"


class DataDictionary:
    """A data dictionary: an ordered, id-indexed collection of data elements.

    Create one with :meth:`load` (from a CSV file) or :meth:`from_rows` (from
    rows already read some other way). The collection protocol works the way
    you would expect::

        len(dd)                 # number of data elements
        for element in dd: ...  # iterate in file order
        "age" in dd             # is there an element with this id?
        dd["age"]               # element by id (KeyError if absent)
        dd.get("age")           # element by id (None if absent)
    """

    def __init__(self, elements: Sequence[DataElement]):
        self._elements = tuple(elements)
        self._by_id = {element.id: element for element in self._elements}

    # --- construction -------------------------------------------------------

    @classmethod
    def load(
        cls,
        source: str | Path | TextIO,
        *,
        allow_duplicates: bool = False,
    ) -> DataDictionary:
        """Load a data dictionary from a CSV file.

        ``source`` may be a path or an open text file. Raises
        :class:`~dd_converter.reader.ReadError` on the first problem found —
        a malformed header, a blank required cell, a duplicate ``Id``, an
        unknown datatype name, or a malformed cell — with the line number in
        the message. When ``allow_duplicates`` is true, rows repeating an
        earlier ``Id`` are skipped (with a logged warning) instead of raising.
        """
        return cls.from_rows(read_data_dictionary(source, allow_duplicates=allow_duplicates))

    @classmethod
    def from_rows(cls, rows: Sequence[Row]) -> DataDictionary:
        """Build a dictionary from already-read :class:`Row` objects.

        Useful with :func:`~dd_converter.reverse.schema_to_rows` to build the
        model from a generated LinkML schema. Same fail-fast parsing and
        errors as :meth:`load`.
        """
        return cls([_element_from_row(row) for row in rows])

    # --- collection protocol -------------------------------------------------

    def __len__(self) -> int:
        return len(self._elements)

    def __iter__(self) -> Iterator[DataElement]:
        return iter(self._elements)

    def __contains__(self, element_id: str) -> bool:
        return element_id in self._by_id

    def __getitem__(self, element_id: str) -> DataElement:
        try:
            return self._by_id[element_id]
        except KeyError:
            raise KeyError(f"no data element with id {element_id!r}") from None

    def get(self, element_id: str, default: DataElement | None = None) -> DataElement | None:
        """Return the element with ``element_id``, or ``default`` if absent."""
        return self._by_id.get(element_id, default)

    def __repr__(self) -> str:
        return f"DataDictionary({len(self._elements)} elements)"

    # --- views ---------------------------------------------------------------

    @property
    def elements(self) -> tuple[DataElement, ...]:
        """All data elements, in file order."""
        return self._elements

    @property
    def ids(self) -> tuple[str, ...]:
        """The element ids, in file order."""
        return tuple(element.id for element in self._elements)

    @property
    def sections(self) -> tuple[str, ...]:
        """The distinct section names, in order of first appearance.

        Elements without a section are not represented here; fetch them with
        ``elements_in_section(None)``.
        """
        seen: dict[str, None] = {}  # a dict preserves insertion order
        for element in self._elements:
            if element.section is not None:
                seen.setdefault(element.section, None)
        return tuple(seen)

    def elements_in_section(self, section: str | None) -> tuple[DataElement, ...]:
        """The elements of one section, in file order.

        Pass ``None`` for the elements that have no section.
        """
        return tuple(e for e in self._elements if e.section == section)

    # --- conversion ----------------------------------------------------------

    def to_linkml(self, options: EmitOptions | None = None) -> str:
        """Render this dictionary as a LinkML schema (YAML text).

        Produces the same output as the ``dd-to-linkml`` command; ``options``
        controls the schema's name, id, and class name. Only available for
        dictionaries built from rows (:meth:`load` / :meth:`from_rows`), which
        is how they are normally made.
        """
        rows = [element.row for element in self._elements]
        if any(row is None for row in rows):
            raise ValueError(
                "to_linkml() needs the underlying rows; this dictionary contains "
                "hand-built DataElements with no row."
            )
        return emit_schema(rows, options)


# --- row -> element parsing ---------------------------------------------------

def _blank_to_none(cell: str) -> str | None:
    """A stripped cell, with blank collapsing to ``None``."""
    stripped = cell.strip()
    return stripped if stripped else None


def _split_pipe(cell: str) -> tuple[str, ...]:
    """Split a pipe-delimited cell (``Aliases``, ``Examples``) into items."""
    return tuple(item.strip() for item in cell.split("|") if item.strip())


def _parse_cardinality(cell: str, line: int) -> str:
    """Normalise a ``Cardinality`` cell to ``"single"`` or ``"multiple"``.

    Blank means ``single`` (the specification's default). Case is forgiven
    (``Multiple`` works); any other value raises — silently coercing an
    unrecognised cardinality to ``single`` would misrepresent the dictionary.
    """
    cardinality = cell.strip().lower()
    if cardinality == "":
        return "single"
    if cardinality in ("single", "multiple"):
        return cardinality
    raise ReadError(
        f"Line {line}: invalid Cardinality {cell.strip()!r} "
        "(expected 'single' or 'multiple')."
    )


def _element_from_row(row: Row) -> DataElement:
    """Parse one raw row into a :class:`DataElement`.

    Raises :class:`ReadError` (with the line number, and the underlying parse
    error as the cause) on the first malformed cell.
    """
    datatype = row.get("Datatype").strip()
    try:
        resolve_datatype(datatype)  # unknown names raise; result not needed here
        enumeration = tuple(parse_enumeration(row.get("Enumeration")))
        missing_value_codes = tuple(parse_missing_value_codes(row.get("MissingValueCodes")))
    except ValueError as exc:  # UnknownDatatypeError and ParseError
        raise ReadError(f"Line {row.line}: {exc}") from exc

    unit = _blank_to_none(row.get("Unit"))
    return DataElement(
        id=row.get("Id").strip(),
        label=row.get("Label").strip(),
        datatype=datatype,
        aliases=_split_pipe(row.get("Aliases")),
        description=_blank_to_none(row.get("Description")),
        section=_blank_to_none(row.get("Section")),
        cardinality=_parse_cardinality(row.get("Cardinality"), row.line),
        terms=tuple(parse_terms(row.get("Terms"))),
        pattern=_blank_to_none(row.get("Pattern")),
        unit=unit,
        unit_of_measure=lookup_unit(unit) if unit else None,
        enumeration=enumeration,
        missing_value_codes=missing_value_codes,
        examples=_split_pipe(row.get("Examples")),
        notes=_blank_to_none(row.get("Notes")),
        provenance=_blank_to_none(row.get("Provenance")),
        see_also=_blank_to_none(row.get("SeeAlso")),
        line=row.line,
        row=row,
    )
