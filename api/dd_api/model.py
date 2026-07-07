"""A high-level, typed object model for data dictionaries.

This is the programmatic front door to the toolkit. A data dictionary on disk
is a CSV file where every cell is a string, and several columns hide little
notations inside those strings (enumerations, ontology term lists). This
module does all of that decoding for you: load a dictionary and get back
plain Python objects whose attributes are already parsed and checked.

Getting started — load a file and look around::

    from dd_api import DataDictionary

    dd = DataDictionary.load("my_dictionary.csv")

    for element in dd:                     # elements, in file order
        print(element.id, element.label, element.datatype)
        for choice in element.enumeration: # parsed "value"=[label](iri) pairs
            print(" ", choice.value, choice.label)

    age = dd["age"]                        # lookup by id (KeyError if absent)
    "weight" in dd                         # membership test by id
    dd.sections                            # section names, in order

Every method below carries a small runnable example (they are tested as
doctests, so they cannot drift from reality). For task-oriented recipes —
"find every enumerated field", "build a dictionary from scratch" — see
``COOKBOOK.md`` next to this package.

A dictionary reads from, and writes to, both of the toolkit's formats::

    dd = DataDictionary.load("my_dictionary.csv")     # CSV in
    dd = DataDictionary.from_linkml("my_schema.yaml") # LinkML schema in
    csv_text = dd.to_csv()                            # canonical CSV out
    schema_yaml = dd.to_linkml()                      # LinkML out

One design rule to know: loading is **fail-fast**. Every cell is parsed up
front, and the first problem raises :class:`~dd_converter.reader.ReadError`,
so an object you get back is known-good — attributes never surprise you
later. The finer print: row-level problems name their line in the message;
header-level problems (a missing or duplicated column) have no single line to
name; and where the problem came from a lower-level parser (an unknown
datatype name, a malformed enumeration), that error is chained as the cause.
If you want *all* of a file's problems listed rather than the first one, that
is the validator tool's job (``dd-validate``).
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
    """One data element of a data dictionary — one row, fully parsed.

    A data element describes one field of the datafile the dictionary is
    about: its identifier, its human-readable label, what values it may hold.
    You normally never construct one yourself; loading a dictionary produces
    them::

        >>> import io
        >>> from dd_api import DataDictionary
        >>> dd = DataDictionary.load(io.StringIO(
        ...     "Id,Label,Datatype,Unit\\n"
        ...     "weight,Body weight,decimal,kg\\n"
        ... ))
        >>> element = dd["weight"]
        >>> element.label
        'Body weight'
        >>> element.datatype
        'decimal'
        >>> element.resolved_unit.ucum_code
        'kg'

    Two conventions to know:

    * **Blank cells** become ``None`` (for single values) or an empty tuple
      (for lists), so ``if element.description:`` and ``for term in
      element.terms:`` both read naturally.
    * Elements are **immutable and hashable**, and equality is by *content*:
      the provenance fields (:attr:`line`, :attr:`row`) do not participate,
      so the same element loaded twice, or from two copies of a file,
      compares equal.
    """

    id: str
    """The field's unique identifier — the name used for it in the datafile
    (the ``Id`` column), e.g. ``"age"`` or ``"nih_record_id"``."""

    label: str
    """The field's human-readable name (the ``Label`` column), e.g.
    ``"Age in years"``. What a person would put as a column heading."""

    datatype: str
    """The name of the field's datatype (the ``Datatype`` column), e.g.
    ``"integer"``, ``"string"``, ``"date_mdy"``. Always a valid name —
    unknown or miscased names are rejected at load time."""

    aliases: tuple[str, ...] = ()
    """Other identifiers this field is known by. Written pipe-delimited in
    the CSV (``years_old|age_years`` becomes ``("years_old",
    "age_years")``); empty tuple when the field has none."""

    description: str | None = None
    """What the field means, in prose (may contain Markdown), or ``None``
    when the cell is blank."""

    section: str | None = None
    """The name of the group of related fields this element belongs to,
    e.g. ``"Demographics"`` — or ``None`` when the dictionary does not use
    sections."""

    cardinality: Literal["single", "multiple"] = "single"
    """How many values one datafile cell may hold: ``"single"`` (one value —
    the default, used when the cell is blank) or ``"multiple"`` (a list).
    See also :attr:`is_multivalued`."""

    terms: tuple[str, ...] = ()
    """Ontology terms attached to the field, saying what it *means* in a
    controlled vocabulary. Each is a full IRI or a compact OBO id, e.g.
    ``("UBERON:0001836",)``. Empty tuple when the field has none."""

    pattern: str | None = None
    """A regular expression (XSD flavour) that valid values must match, e.g.
    ``"^[0-9]{5}$"`` for a zip code — or ``None``. Kept exactly as written:
    XSD regex syntax is not Python's, so it is not compiled here."""

    unit: str | None = None
    """The field's unit of measure **exactly as written** in the CSV, e.g.
    ``"kg"`` or ``"mmHg"`` — or ``None`` when blank. See
    :attr:`resolved_unit` for the structured form."""

    resolved_unit: UnitOfMeasure | None = None
    """The structured unit (descriptive name, symbol, UCUM code) that
    :attr:`unit` resolves to when it is one the specification's unit table
    recognises — e.g. ``"kg"`` resolves to *kilogram* with UCUM code
    ``kg``. ``None`` for an unrecognised (or absent) unit; the raw
    :attr:`unit` text is still there either way."""

    enumeration: tuple[EnumItem, ...] = ()
    """The field's permissible values, when it is restricted to a fixed
    choice list. Each item has a ``value`` (what appears in the datafile),
    a ``label`` (what it means), and an optional ``iri`` (an ontology term
    for the choice). Parsed from the CSV's ``"0"=[No] | "1"=[Yes]``
    notation; empty tuple when the field is not enumerated."""

    missing_value_codes: tuple[EnumItem, ...] = ()
    """Special codes that mean "no data here" (refused, not collected, …),
    same item shape as :attr:`enumeration`. E.g. a ``"-9096"=[Refused]``
    cell becomes one item with value ``"-9096"`` and label ``"Refused"``."""

    examples: tuple[str, ...] = ()
    """Example values for the field, e.g. ``("42", "7")``. Written
    pipe-delimited in the CSV; empty tuple when none are given."""

    notes: str | None = None
    """Free-text notes about the field, e.g. ``"Collected pre-2021 only"``
    — or ``None`` when blank."""

    provenance: str | None = None
    """Where the field came from (a study name, an instrument, a URL…), or
    ``None`` when blank."""

    see_also: str | None = None
    """A URL with more information about the field, or ``None``."""

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
        """Whether the field restricts values to a fixed choice list.

        True exactly when :attr:`enumeration` is non-empty — this is just the
        readable way to ask.
        """
        return bool(self.enumeration)

    @property
    def is_multivalued(self) -> bool:
        """Whether one datafile cell may hold multiple values.

        True when :attr:`cardinality` is ``"multiple"``. Named after the
        LinkML property this maps to (``multivalued``).
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

        This is the usual way in. ``source`` may be a file path or an open
        text stream::

            >>> import io
            >>> from dd_api import DataDictionary
            >>> dd = DataDictionary.load(io.StringIO(
            ...     "Id,Label,Datatype\\n"
            ...     "age,Age,integer\\n"
            ...     "name,Name,string\\n"
            ... ))
            >>> dd
            DataDictionary(2 elements)
            >>> dd.ids
            ('age', 'name')

        A file that breaks the specification's rules — a missing required
        column, a blank required cell, a duplicate ``Id``, an unknown
        datatype name, a malformed enumeration — raises
        :class:`~dd_converter.reader.ReadError` describing the first problem
        found (row-level problems name their line; header-level problems have
        no single line to name)::

            >>> DataDictionary.load(io.StringIO(
            ...     "Id,Label,Datatype\\n"
            ...     "age,Age,Integer\\n"          # miscased datatype name
            ... ))
            Traceback (most recent call last):
            ...
            dd_converter.reader.ReadError: Line 2: Unknown datatype name 'Integer'. ...

        When ``allow_duplicates`` is true, rows repeating an earlier ``Id``
        are skipped (with a logged warning) instead of raising — useful for
        exploring an imperfect dictionary you did not author.
        """
        return cls.from_rows(read_data_dictionary(source, allow_duplicates=allow_duplicates))

    @classmethod
    def from_rows(cls, rows: Sequence[Row | Mapping[str, str]]) -> DataDictionary:
        """Build a dictionary from rows you already have in memory.

        This is the lower-level way in, for when the rows did not come from a
        CSV file you can hand to :meth:`load`. Each row may be a
        :class:`~dd_converter.reader.Row` (what
        :func:`~dd_converter.read_data_dictionary` returns) or simply a dict
        of column name to cell text::

            >>> from dd_api import DataDictionary
            >>> dd = DataDictionary.from_rows([
            ...     {"Id": "age", "Label": "Age", "Datatype": "integer"},
            ...     {"Id": "name", "Label": "Name", "Datatype": "string"},
            ... ])
            >>> dd["name"].label
            'Name'

        Cell text uses the same notations as the CSV format (so an
        ``"Enumeration"`` key takes ``'"0"=[No] | "1"=[Yes]'``, and so on).
        A plain dict is given the line number its row would have had in a CSV
        file — the first data row is line 2 — so error messages stay
        meaningful. Parsing is fail-fast, exactly as in :meth:`load`.
        """
        normalised = [
            row if isinstance(row, Row) else Row(cells=dict(row), line=index + 2)
            for index, row in enumerate(rows)
        ]
        return cls([_element_from_row(row) for row in normalised])

    @classmethod
    def from_linkml(cls, source: str | Path | TextIO | dict) -> DataDictionary:
        """Load a dictionary from a LinkML schema.

        The inverse of :meth:`to_linkml`: a schema generated by this toolkit
        loads back with full fidelity::

            >>> import io
            >>> from dd_api import DataDictionary
            >>> original = DataDictionary.load(io.StringIO(
            ...     "Id,Label,Datatype\\n"
            ...     "age,Age,integer\\n"
            ... ))
            >>> schema_yaml = original.to_linkml()
            >>> reloaded = DataDictionary.from_linkml(io.StringIO(schema_yaml))
            >>> reloaded["age"].label
            'Age'

        ``source`` may be a path to the schema YAML, an open text file, or an
        already-parsed schema (a ``dict``).

        Schemas written by hand load too — the schema is read through
        LinkML's own ``SchemaView``, so the usual representation choices all
        work: fields as class ``attributes:`` or as a ``slots:`` list with
        ``slot_usage:`` refinements (inheritance and imports included), and
        enumerations as named enums (referenced through ``any_of`` or used
        directly as the ``range:``) or inline ``enum_range:``. The caveat is
        that only information the schema actually carries can come back:
        without the converter's machine annotations, an enumerated field's
        underlying datatype defaults to ``"string"`` and units are not
        recovered. Parsing is fail-fast, exactly as in :meth:`load`.
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
        """Return the element with this id; raise ``KeyError`` if absent.

        ::

            >>> import io
            >>> from dd_api import DataDictionary
            >>> dd = DataDictionary.load(io.StringIO("Id,Label,Datatype\\nage,Age,integer\\n"))
            >>> dd["age"].label
            'Age'
            >>> dd["zzz"]
            Traceback (most recent call last):
            ...
            KeyError: "no data element with id 'zzz'"
        """
        try:
            return self._by_id[element_id]
        except KeyError:
            raise KeyError(f"no data element with id {element_id!r}") from None

    def get(self, element_id: str, default: DataElement | None = None) -> DataElement | None:
        """Return the element with this id, or ``default`` (``None``) if absent.

        The forgiving counterpart of ``dd[element_id]``, mirroring
        ``dict.get``::

            >>> import io
            >>> from dd_api import DataDictionary
            >>> dd = DataDictionary.load(io.StringIO("Id,Label,Datatype\\nage,Age,integer\\n"))
            >>> dd.get("age").label
            'Age'
            >>> dd.get("zzz") is None
            True
        """
        return self._by_id.get(element_id, default)

    def __repr__(self) -> str:
        return f"DataDictionary({len(self._elements)} elements)"

    # --- views ---------------------------------------------------------------

    @property
    def elements(self) -> tuple[DataElement, ...]:
        """All data elements as a tuple, in file order.

        The same things iteration yields — use this when you need indexing
        (``dd.elements[0]``) or a stable snapshot.
        """
        return self._elements

    @property
    def ids(self) -> tuple[str, ...]:
        """Every element's id, in file order — a quick table of contents."""
        return tuple(element.id for element in self._elements)

    @property
    def sections(self) -> tuple[str, ...]:
        """The distinct section names, in order of first appearance.

        ::

            >>> import io
            >>> from dd_api import DataDictionary
            >>> dd = DataDictionary.load(io.StringIO(
            ...     "Id,Label,Datatype,Section\\n"
            ...     "age,Age,integer,Demographics\\n"
            ...     "hr,Heart rate,integer,Vitals\\n"
            ...     "sex,Sex,string,Demographics\\n"
            ... ))
            >>> dd.sections
            ('Demographics', 'Vitals')

        Elements without a section do not contribute a name here; fetch them
        with ``elements_in_section(None)``.
        """
        distinct_in_order = dict.fromkeys(
            element.section for element in self._elements if element.section is not None
        )
        return tuple(distinct_in_order)

    def elements_in_section(self, section: str | None) -> tuple[DataElement, ...]:
        """The elements of one section, in file order.

        Pass a section name, or ``None`` for the elements that have no
        section::

            >>> import io
            >>> from dd_api import DataDictionary
            >>> dd = DataDictionary.load(io.StringIO(
            ...     "Id,Label,Datatype,Section\\n"
            ...     "age,Age,integer,Demographics\\n"
            ...     "misc,Misc,string,\\n"
            ... ))
            >>> [e.id for e in dd.elements_in_section("Demographics")]
            ['age']
            >>> [e.id for e in dd.elements_in_section(None)]
            ['misc']
        """
        return tuple(e for e in self._elements if e.section == section)

    # --- serialisation --------------------------------------------------------

    def to_csv(self) -> str:
        """Write this dictionary out as data dictionary CSV text.

        ::

            >>> from dd_api import DataDictionary
            >>> dd = DataDictionary.from_rows([
            ...     {"Id": "age", "Label": "Age", "Datatype": "integer"},
            ... ])
            >>> dd.to_csv().splitlines()[1]
            'age,,Age,,,single,,integer,,,,,,,,'

        Cells are written in **canonical form**: columns in the
        specification's order, enumerations as ``"value"=[label](iri)`` with
        single spaces around ``|``, terms joined with single spaces, and
        cardinality always explicit (``single``/``multiple``). So loading a
        CSV and writing it back preserves the information, but not the
        original file's incidental formatting. Works for hand-built elements
        too — no underlying rows are needed.
        """
        buffer = io.StringIO()
        write_csv([_element_to_cells(element) for element in self._elements], buffer)
        return buffer.getvalue()

    def to_linkml(self, options: EmitOptions | None = None) -> str:
        """Render this dictionary as a LinkML schema (YAML text).

        Produces exactly what the ``dd-to-linkml`` command would::

            >>> import io
            >>> from dd_api import DataDictionary
            >>> dd = DataDictionary.load(io.StringIO(
            ...     "Id,Label,Datatype\\n"
            ...     "age,Age,integer\\n"
            ... ))
            >>> schema_yaml = dd.to_linkml()
            >>> "age:" in schema_yaml
            True

        ``options`` (an :class:`~dd_converter.EmitOptions`) controls the
        schema's name, id, and root class name. Only available for
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
