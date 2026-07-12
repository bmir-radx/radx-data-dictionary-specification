"""The individual validation checks.

Each check inspects the header or the data rows and yields :class:`Finding`
objects. The checks are independent and never raise on a data problem; they
report it. The per-cell parsing rules (datatype names, the enumeration and
missing-value-codes grammars) are reused from :mod:`dd_core` so the
validator stays in lockstep with the converter and the specification.

Conventions, mirrored from the reference Java validator:

* A per-field check whose column is absent from the header does nothing (a
  missing *optional* column is not itself a problem; missing *required* columns
  are reported by :func:`check_required_headers`).
* Per-field checks skip blank cells, except the required-field checks.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from urllib.parse import urlsplit

from dd_core import (
    BUILTIN_RANGES,
    CUSTOM_TYPES,
    ORDERED_DATATYPES,
    REQUIRED_COLUMNS,
    UnknownDatatypeError,
    resolve_datatype,
    sanitize_identifier,
)
from dd_core.grammar import (
    Comparison,
    Contains,
    ParseError,
    parse_enumeration,
    parse_missing_value_codes,
    parse_precondition,
)
from dd_core.grammar import atoms as precondition_atoms

from .model import Finding, Level
from .rows import RawRow

# Case-insensitive index of the valid datatype names, used to recover the
# correctly-cased name from a near-miss (e.g. "Integer" -> "integer").
# resolve_datatype() remains the source of truth for what is valid.
_DATATYPES_BY_LOWERCASE = {
    name.lower(): name for name in (*BUILTIN_RANGES, *CUSTOM_TYPES)
}

# Datatype names people commonly write that are not in the specification, and
# the valid name each one usually means. From the reference Java validator.
_DATATYPE_FIXES = {
    "bit": "boolean",
    "text": "string",
    "number": "decimal",
    "email": "string",
    "zipcode": "string",
    "phone": "string",
}


def _suggest_datatype(unknown_name: str) -> str | None:
    """Suggest a valid datatype name for an unknown one, or ``None``.

    Tries a case-insensitive match against the valid names first (catches a
    miscased ``Integer``), then the common-mistake fix map.
    """
    lowered = unknown_name.lower()
    return _DATATYPES_BY_LOWERCASE.get(lowered) or _DATATYPE_FIXES.get(lowered)


# --- header ----------------------------------------------------------------

def check_required_headers(header: Sequence[str]) -> Iterable[Finding]:
    """Report each required column header that is absent.

    Suggests a rename when a header matches a required name case-insensitively
    (e.g. ``id`` for ``Id``).
    """
    present = set(header)
    headers_by_lowercase = {h.lower(): h for h in header}
    for required in REQUIRED_COLUMNS:
        if required in present:
            continue
        message = f"required column {required!r} is missing"
        miscased = headers_by_lowercase.get(required.lower())
        if miscased is not None:
            message += f" (did you mean the column {miscased!r}?)"
        yield Finding(Level.ERROR, "required-header", message, column=required)


# --- per-row checks ---------------------------------------------------------

def check_id(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Id" not in columns_present:
        return  # required-header check already reports the missing column
    for row in rows:
        # Deliberately unstripped: the whitespace checks below inspect it.
        id_cell = row.get("Id")
        if id_cell.strip() == "":
            yield Finding(Level.ERROR, "id-missing", "Id is missing", line=row.line, column="Id")
            continue
        if id_cell.startswith(" "):
            yield Finding(
                Level.ERROR, "id-leading-whitespace",
                "Id starts with whitespace", line=row.line, column="Id", value=id_cell,
            )
        # Spaces and special characters are legal per the specification, but
        # they degrade the id elsewhere: schema renderings rename it (the
        # shared sanitisation rule) and preconditions cannot reference it.
        # Broadens the earlier id-whitespace check; the suggestion is exactly
        # the name a schema rendering would use.
        safe = sanitize_identifier(id_cell)
        if safe != id_cell:
            yield Finding(
                Level.INFO, "id-characters",
                f"Id contains spaces or special characters; schema renderings "
                f"rename it to {safe!r} and preconditions cannot reference it "
                f"as written",
                line=row.line, column="Id", value=id_cell, suggestion=safe,
            )


def check_label(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Label" not in columns_present:
        return
    for row in rows:
        if row.get("Label").strip() == "":
            yield Finding(
                Level.WARNING, "label-missing",
                "Label is missing (a label is strongly recommended)",
                line=row.line, column="Label",
            )


def check_datatype(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Datatype" not in columns_present:
        return
    for row in rows:
        datatype_name = row.get("Datatype").strip()
        if datatype_name == "":
            yield Finding(
                Level.ERROR, "datatype-missing",
                "Datatype is missing", line=row.line, column="Datatype",
            )
            continue
        try:
            resolve_datatype(datatype_name)
        except UnknownDatatypeError:
            message = f"{datatype_name!r} is not a known datatype name"
            suggestion = _suggest_datatype(datatype_name)
            if suggestion is not None:
                message += f" (did you mean {suggestion!r}?)"
            yield Finding(
                Level.ERROR, "unknown-datatype", message,
                line=row.line, column="Datatype", value=datatype_name,
            )


def check_cardinality(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Cardinality" not in columns_present:
        return
    for row in rows:
        cardinality = row.get("Cardinality").strip()
        if cardinality == "":
            continue
        if cardinality not in ("single", "multiple"):
            yield Finding(
                Level.ERROR, "invalid-cardinality",
                f"invalid cardinality {cardinality!r} (expected 'single' or 'multiple')",
                line=row.line, column="Cardinality", value=cardinality,
            )


def check_pattern(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Pattern" not in columns_present:
        return
    for row in rows:
        pattern = row.get("Pattern")
        if pattern.strip() == "":
            continue
        try:
            re.compile(pattern)
        except re.error as exc:
            yield Finding(
                Level.ERROR, "malformed-pattern",
                f"pattern is not a valid regular expression: {exc}",
                line=row.line, column="Pattern", value=pattern,
            )


def check_enumeration(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Enumeration" not in columns_present:
        return
    for row in rows:
        enumeration = row.get("Enumeration")
        if enumeration.strip() == "":
            continue
        try:
            parse_enumeration(enumeration)
        except ParseError as exc:
            yield Finding(
                Level.ERROR, "malformed-enumeration",
                f"enumeration is malformed: {exc}",
                line=row.line, column="Enumeration", value=enumeration,
            )


def check_cell_whitespace(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Leading/trailing whitespace in a cell (WARNING).

    Padding survives serialisation and breaks exact-value matching — an
    enumeration code ``' 1'`` is not ``'1'``. The suggestion is the stripped
    value. ``Id`` is covered by its own checks (leading whitespace is an
    ERROR there); wholly-blank cells are the missing-value checks' business.
    """
    for row in rows:
        for column, cell in row.cells.items():
            if column == "Id" or cell == "":
                continue
            stripped = cell.strip()
            if stripped == cell or stripped == "":
                continue
            yield Finding(
                Level.WARNING, "cell-whitespace",
                f"{column} has leading or trailing whitespace",
                line=row.line, column=column, value=cell, suggestion=stripped,
            )


# Datatype names with a preferred semantic equivalent: the storage-width /
# lexical aliases of the builtins (int, short, token, …), plus the extension
# date formats with a clear native counterpart. The g*/duration/binary custom
# types are deliberate rendering choices and stay unflagged.
_PREFERRED_DATATYPE: dict[str, str] = {
    **{
        name: range_
        for name, range_ in BUILTIN_RANGES.items()
        if name != range_ and range_ in ("string", "integer")
    },
    "date_mdy": "date",
    "date_dmy": "date",
    "timestamp": "dateTime",
}


def check_datatype_preferred(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Advisory: prefer the semantic datatype name (INFO; the value is valid).

    ``int``/``short``/``token`` name a storage width or lexical class and map
    silently onto the semantic builtin anyway; the extension date formats
    (``date_mdy``, ``timestamp``) render as generated custom types where the
    native ``date``/``dateTime`` is usually meant.
    """
    if "Datatype" not in columns_present:
        return
    for row in rows:
        name = row.get("Datatype").strip()
        preferred = _PREFERRED_DATATYPE.get(name)
        if preferred is None:
            continue
        if name in CUSTOM_TYPES:
            message = (
                f"datatype {name!r} renders as a generated custom type; prefer "
                f"the native {preferred!r} unless the datafile really stores "
                f"that format"
            )
        else:
            message = (
                f"datatype {name!r} names a storage width, not a meaning; "
                f"the semantic type is {preferred!r}"
            )
        yield Finding(
            Level.INFO, "datatype-preferred", message,
            line=row.line, column="Datatype", value=name, suggestion=preferred,
        )


_NUMERIC_RANGES = frozenset({"integer", "decimal", "float", "double"})


def check_units(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    """Advisory: a numeric, non-enumerated field with no Unit (INFO).

    Counts and scores are legitimately unitless (UCUM ``1``), so this is a
    nudge rather than a warning — and exactly why it is INFO and ignorable.
    """
    if "Datatype" not in columns_present:
        return
    for row in rows:
        if row.get("Unit").strip() != "" or row.get("Enumeration").strip() != "":
            continue
        if BUILTIN_RANGES.get(row.get("Datatype").strip()) not in _NUMERIC_RANGES:
            continue
        yield Finding(
            Level.INFO, "missing-unit",
            "numeric field has no Unit — a UCUM unit (or '1' for dimensionless "
            "counts and scores) makes values interpretable",
            line=row.line, column="Unit",
        )


_INTEGER_VALUE = re.compile(r"^-?\d+$")


def check_enumeration_datatype(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Advisory: every enumeration value is an integer but Datatype is not.

    All-integer value sets usually mean the underlying datatype should be
    ``integer`` (INFO, with that as the suggestion).
    """
    if "Enumeration" not in columns_present or "Datatype" not in columns_present:
        return
    for row in rows:
        cell = row.get("Enumeration")
        if cell.strip() == "":
            continue
        try:
            items = parse_enumeration(cell)
        except ParseError:
            continue  # malformed-enumeration reports it
        if not items or not all(_INTEGER_VALUE.match(item.value.strip()) for item in items):
            continue
        datatype = row.get("Datatype").strip()
        if BUILTIN_RANGES.get(datatype) == "integer":
            continue
        yield Finding(
            Level.INFO, "enumeration-integer-datatype",
            f"every enumeration value is an integer but Datatype is {datatype!r}",
            line=row.line, column="Datatype", value=datatype, suggestion="integer",
        )


def check_missing_value_codes(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    if "MissingValueCodes" not in columns_present:
        return
    for row in rows:
        codes = row.get("MissingValueCodes")
        if codes.strip() == "":
            continue
        try:
            parse_missing_value_codes(codes)
        except ParseError as exc:
            yield Finding(
                Level.ERROR, "malformed-missing-value-codes",
                f"missing value codes are malformed: {exc}",
                line=row.line, column="MissingValueCodes", value=codes,
            )


def check_see_also(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "SeeAlso" not in columns_present:
        return
    for row in rows:
        url = row.get("SeeAlso").strip()
        if url == "":
            continue
        # An absolute URL must have a scheme (e.g. https). urlsplit does not
        # raise on ordinary strings, so we check the parsed scheme directly.
        if not urlsplit(url).scheme:
            yield Finding(
                Level.ERROR, "malformed-see-also",
                "SeeAlso is not an absolute URL",
                line=row.line, column="SeeAlso", value=url,
            )


def check_required(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Required" not in columns_present:
        return
    for row in rows:
        value = row.get("Required").strip()
        if value and value.lower() != "y":
            yield Finding(
                Level.ERROR, "invalid-required",
                f"invalid Required {value!r} (expected 'y' or blank)",
                line=row.line, column="Required", value=value,
            )


def check_preconditions(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Check every Precondition cell: grammar, references, and predicate typing.

    Per the specification: referenced fields must exist in this dictionary;
    ordering predicates (< <= > >=) are only valid on fields with an ordered
    Datatype; `contains` is only valid on fields with Cardinality `multiple`.
    """
    if "Precondition" not in columns_present:
        return
    rows = list(rows)
    fields = {
        row.get("Id").strip(): row for row in rows if row.get("Id").strip()
    }
    for row in rows:
        cell = row.get("Precondition")
        if cell.strip() == "":
            continue
        try:
            condition = parse_precondition(cell)
        except ParseError as exc:
            yield Finding(
                Level.ERROR, "malformed-precondition",
                f"precondition is malformed: {exc}",
                line=row.line, column="Precondition", value=cell,
            )
            continue
        for atom in precondition_atoms(condition):
            referenced = fields.get(atom.field)
            if referenced is None:
                yield Finding(
                    Level.ERROR, "unknown-precondition-field",
                    f"precondition refers to {atom.field!r}, which is not a "
                    "field in this dictionary",
                    line=row.line, column="Precondition", value=atom.field,
                )
                continue
            if isinstance(atom, Comparison) and atom.op in ("<", "<=", ">", ">="):
                datatype = referenced.get("Datatype").strip()
                if datatype and datatype not in ORDERED_DATATYPES:
                    yield Finding(
                        Level.ERROR, "invalid-precondition-comparison",
                        f"precondition compares {atom.field!r} with "
                        f"{atom.op!r}, but its datatype {datatype!r} is not ordered",
                        line=row.line, column="Precondition", value=atom.field,
                    )
            if isinstance(atom, Contains):
                cardinality = referenced.get("Cardinality").strip().lower()
                if cardinality != "multiple":
                    yield Finding(
                        Level.ERROR, "invalid-precondition-contains",
                        f"precondition uses 'contains' on {atom.field!r}, "
                        "which is not a multivalued field",
                        line=row.line, column="Precondition", value=atom.field,
                    )


def check_duplicate_ids(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Report Ids that appear on more than one row.

    Not present in the reference Java validator, but the specification treats an
    Id as the unique identifier of a data element, and the converter refuses a
    dictionary with duplicate Ids. Reported against the *second and subsequent*
    occurrences, naming the first.
    """
    if "Id" not in columns_present:
        return
    first_seen_line: dict[str, int] = {}
    for row in rows:
        row_id = row.get("Id").strip()
        if row_id == "":
            continue
        if row_id in first_seen_line:
            yield Finding(
                Level.ERROR, "duplicate-id",
                f"duplicate Id {row_id!r} (first seen on line {first_seen_line[row_id]})",
                line=row.line, column="Id", value=row_id,
            )
        else:
            first_seen_line[row_id] = row.line
