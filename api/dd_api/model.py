"""A high-level, typed object model for data dictionaries.

This is the programmatic front door to the toolkit. Where
:func:`~dd_converter.reader.read_data_dictionary` returns rows of raw cell
strings, this module parses every cell up front and hands back plain, typed
objects::

    from dd_api import DataDictionary

    dd = DataDictionary.load("my_dictionary.csv")

    for element in dd:                     # elements, in file order
        print(element.id, element.label, element.datatype)
        for choice in element.enumeration: # parsed "value"=[label](iri) pairs
            print(" ", choice.value, choice.label)

    age = dd["age"]                        # lookup by id (KeyError if absent)
    "weight" in dd                         # membership test by id
    dd.sections                            # section names, in order

Round-tripping — a dictionary can be read from, and written to, both of the
toolkit's formats::

    dd = DataDictionary.load("my_dictionary.csv")     # CSV in
    dd = DataDictionary.from_linkml("my_schema.yaml") # LinkML schema in
    csv_text = dd.to_csv()                            # canonical CSV out
    schema_yaml = dd.to_linkml()                      # LinkML out

Loading is **fail-fast**: every cell is parsed eagerly, and the first problem
raises :class:`~dd_converter.reader.ReadError`. Row-level problems carry the
line number in the message; header-level problems (a missing or duplicated
column) have no single line and carry none. Where the problem comes from a
lower-level parser (an unknown datatype name, a malformed enumeration), that
error is chained as the cause. An object you get back is therefore known-good
— no deferred surprises when an attribute is first touched. To list *all*
problems in a dictionary instead of stopping at the first, use the validator
tool (``dd-validate``), which exists for exactly that.
"""

from __future__ import annotations

import io
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TextIO

import yaml
from dd_converter import (
    KNOWN_COLUMNS,
    EmitOptions,
    ReadError,
    Row,
    UnitOfMeasure,
    emit_schema,
    lookup_unit,
    read_data_dictionary,
    resolve_datatype,
    schema_to_rows,
)
from dd_converter.grammar import (
    EnumItem,
    parse_enumeration,
    parse_missing_value_codes,
    parse_terms,
)
from dd_converter.reverse import write_csv


@dataclass(frozen=True)
class DataElement:
    """One data element (row) of a data dictionary, fully parsed.

    Blank optional cells become ``None`` (for single values) or an empty tuple
    (for lists), so ``if element.description:`` and ``for term in
    element.terms:`` both read naturally.

    Elements are immutable and hashable. Equality is by **content** — the
    provenance fields (:attr:`line`, :attr:`row`) do not participate, so the
    same element loaded twice, or from two copies of a file, compares equal.
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

    cardinality: Literal["single", "multiple"] = "single"
    """``"single"`` (one value per cell — the default) or ``"multiple"``."""

    terms: tuple[str, ...] = ()
    """Ontology term identifiers attached to the field: full IRIs or compact
    OBO ids like ``UBERON:0001836``."""

    pattern: str | None = None
    """The XSD regular expression values must match, or ``None``. Kept as
    written — XSD regex syntax is not Python's, so it is not compiled here."""

    unit: str | None = None
    """The unit of measure **exactly as written** in the CSV, or ``None``.
    See :attr:`resolved_unit` for the structured form."""

    resolved_unit: UnitOfMeasure | None = None
    """The structured unit (name, symbol, UCUM code) that :attr:`unit`
    resolves to when it is in the specification's unit table; ``None`` for an
    unrecognised (or absent) unit."""

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

    line: int | None = field(default=None, compare=False)
    """The 1-based line number of this element in the source CSV, or ``None``
    for a hand-built element. Provenance only — not part of equality."""

    row: Row | None = field(default=None, repr=False, compare=False)
    """The underlying raw :class:`~dd_converter.reader.Row` — the escape hatch
    for anything the typed fields do not cover (e.g. non-standard columns).
    ``None`` only when a :class:`DataElement` is constructed by hand.
    Provenance only — not part of equality."""

    @property
    def is_enumerated(self) -> bool:
        """Whether the element restricts values to an enumeration."""
        return bool(self.enumeration)

    @property
    def is_multivalued(self) -> bool:
        """Whether a cell may hold multiple values (cardinality ``multiple``).

        Named after the LinkML property this maps to (``multivalued``).
        """
        return self.cardinality == "multiple"


class DataDictionary:
    """A data dictionary: an ordered, id-indexed collection of data elements.

    Create one with :meth:`load` (from a CSV file), :meth:`from_linkml` (from
    a LinkML schema), or :meth:`from_rows` (from rows already read some other
    way). The collection protocol works the way you would expect::

        len(dd)                 # number of data elements
        for element in dd: ...  # iterate in file order
        "age" in dd             # is there an element with this id?
        dd["age"]               # element by id (KeyError if absent)
        dd.get("age")           # element by id (None if absent)

    **Membership is by id**: ``x in dd`` accepts an id string or a
    :class:`DataElement` (tested via its id), so ``element in dd`` holds for
    every element that iteration yields.
    """

    def __init__(self, elements: Sequence[DataElement]):
        """Build a dictionary from elements directly.

        Ids must be unique — a duplicate raises :class:`ValueError`. (This is
        the backstop for every constructor; :meth:`load` additionally rejects
        duplicates while reading, with the line numbers in its message.)
        """
        self._elements = tuple(elements)
        self._by_id: dict[str, DataElement] = {}
        for element in self._elements:
            if element.id in self._by_id:
                raise ValueError(f"duplicate data element id {element.id!r}")
            self._by_id[element.id] = element

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
        unknown datatype name, or a malformed cell. Row-level problems name
        the line; header-level problems have no single line to name. When
        ``allow_duplicates`` is true, rows repeating an earlier ``Id`` are
        skipped (with a logged warning) instead of raising.
        """
        return cls.from_rows(read_data_dictionary(source, allow_duplicates=allow_duplicates))

    @classmethod
    def from_rows(cls, rows: Sequence[Row | Mapping[str, str]]) -> DataDictionary:
        """Build a dictionary from rows read some other way.

        Each row may be a :class:`~dd_converter.reader.Row` (as
        :func:`~dd_converter.read_data_dictionary` returns) or a plain mapping
        of column name to cell text (as
        :func:`~dd_converter.schema_to_rows` returns for a generated LinkML
        schema). A mapping is given the line number its row would have in a
        CSV file (the first data row is line 2). Same fail-fast parsing and
        errors as :meth:`load`.
        """
        normalised = [
            row if isinstance(row, Row) else Row(cells=dict(row), line=index + 2)
            for index, row in enumerate(rows)
        ]
        return cls([_element_from_row(row) for row in normalised])

    @classmethod
    def from_linkml(cls, source: str | Path | TextIO | dict) -> DataDictionary:
        """Load a dictionary from a LinkML schema.

        ``source`` may be a path to the schema YAML, an open text file, or an
        already-parsed schema (a ``dict``). This inverts what
        :meth:`to_linkml` / ``dd-to-linkml`` produce, and also accepts the
        common hand-authored shapes: fields as class ``attributes:`` or as a
        ``slots:`` list with ``slot_usage:`` refinements, and enumerations as
        named enums (via ``any_of`` or directly as the ``range:``) or inline
        ``enum_range:``. Only information the schema carries can come back:
        without the converter's annotations, an enumerated field's underlying
        datatype defaults to ``"string"`` and units are not recovered. Same
        fail-fast parsing and errors as :meth:`load`.
        """
        if isinstance(source, dict):
            schema = source
        elif isinstance(source, (str, Path)):
            schema = yaml.safe_load(Path(source).read_text(encoding="utf-8"))
        else:
            schema = yaml.safe_load(source.read())
        return cls.from_rows(schema_to_rows(schema))

    # --- collection protocol -------------------------------------------------

    def __len__(self) -> int:
        return len(self._elements)

    def __iter__(self) -> Iterator[DataElement]:
        return iter(self._elements)

    def __contains__(self, key: object) -> bool:
        """Membership by id: accepts an id string or a :class:`DataElement`."""
        if isinstance(key, DataElement):
            key = key.id
        return key in self._by_id

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
        distinct_in_order = dict.fromkeys(
            element.section for element in self._elements if element.section is not None
        )
        return tuple(distinct_in_order)

    def elements_in_section(self, section: str | None) -> tuple[DataElement, ...]:
        """The elements of one section, in file order.

        Pass ``None`` for the elements that have no section.
        """
        return tuple(e for e in self._elements if e.section == section)

    # --- serialisation --------------------------------------------------------

    def to_csv(self) -> str:
        """Serialise this dictionary as data dictionary CSV text.

        Cells are written in **canonical form**: columns in the
        specification's order, enumerations as ``"value"=[label](iri)`` with
        single spaces around ``|``, terms joined with single spaces, and
        cardinality always explicit (``single``/``multiple``). Loading a CSV
        and writing it back therefore preserves the information but not the
        original file's incidental formatting. Works for hand-built elements
        too — no underlying rows are needed.
        """
        buffer = io.StringIO()
        write_csv([_element_to_cells(element) for element in self._elements], buffer)
        return buffer.getvalue()

    def to_linkml(self, options: EmitOptions | None = None) -> str:
        """Render this dictionary as a LinkML schema (YAML text).

        Produces the same output as the ``dd-to-linkml`` command; ``options``
        controls the schema's name, id, and class name. Only available for
        dictionaries built by the loaders (:meth:`load`, :meth:`from_linkml`,
        :meth:`from_rows`), which is how they are normally made.
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


def _parse_cardinality(cell: str, line: int) -> Literal["single", "multiple"]:
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
        resolved_unit=lookup_unit(unit) if unit else None,
        enumeration=enumeration,
        missing_value_codes=missing_value_codes,
        examples=_split_pipe(row.get("Examples")),
        notes=_blank_to_none(row.get("Notes")),
        provenance=_blank_to_none(row.get("Provenance")),
        see_also=_blank_to_none(row.get("SeeAlso")),
        line=row.line,
        row=row,
    )


# --- element -> cells serialisation --------------------------------------------

def _enum_items_to_cell(items: Sequence[EnumItem]) -> str:
    """Serialise enumeration items back to the ``"value"=[label](iri)`` cell
    notation (canonical spacing, matching the converter's round-trip form).

    Values are written as-is, without escaping: a hand-built value containing
    a double quote would not re-parse (parsed values never contain one).
    """
    parts = []
    for item in items:
        text = f'"{item.value}"=[{item.label}]'
        if item.iri:
            text += f"({item.iri})"
        parts.append(text)
    return " | ".join(parts)


def _element_to_cells(element: DataElement) -> dict[str, str]:
    """Serialise one element to a dict of column name -> cell text."""
    cells = dict.fromkeys(KNOWN_COLUMNS, "")
    cells["Id"] = element.id
    cells["Aliases"] = "|".join(element.aliases)
    cells["Label"] = element.label
    cells["Description"] = element.description or ""
    cells["Section"] = element.section or ""
    cells["Cardinality"] = element.cardinality
    cells["Terms"] = " ".join(element.terms)
    cells["Datatype"] = element.datatype
    cells["Pattern"] = element.pattern or ""
    cells["Unit"] = element.unit or ""
    cells["Enumeration"] = _enum_items_to_cell(element.enumeration)
    cells["MissingValueCodes"] = _enum_items_to_cell(element.missing_value_codes)
    cells["Examples"] = "|".join(element.examples)
    cells["Notes"] = element.notes or ""
    cells["Provenance"] = element.provenance or ""
    cells["SeeAlso"] = element.see_also or ""
    return cells
