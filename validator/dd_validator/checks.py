"""The individual validation checks.

Each check inspects the header or the data rows and yields :class:`Finding`
objects. The checks are independent and never raise on a data problem; they
report it. The per-cell parsing rules (datatype names, the enumeration and
missing-value-codes grammars) are reused from :mod:`dd_converter` so the
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

from dd_converter import (
    REQUIRED_COLUMNS,
    UnknownDatatypeError,
    resolve_datatype,
)
from dd_converter.grammar import (
    ParseError,
    parse_enumeration,
    parse_missing_value_codes,
)

from .model import Finding, Level
from .rows import RawRow

# Known datatype names, for the "did you mean" suggestion. Resolving a name is
# the source of truth for validity; this set is only used to find a
# case-insensitive near-match to suggest.
_DATATYPE_FIXES = {
    "bit": "boolean",
    "text": "string",
    "number": "decimal",
    "email": "string",
    "zipcode": "string",
    "phone": "string",
}


def _suggest_datatype(name: str) -> str | None:
    """Suggest a correct datatype name for an unknown ``name``, or ``None``.

    First a case-insensitive exact match against the known names (catches a
    miscased ``Integer``/``String``), then a small hardcoded fix map for common
    non-XSD names. Mirrors the reference validator's ``getSuggestedName``.
    """
    from dd_converter.datatypes import BUILTIN_RANGES, CUSTOM_TYPES

    known = {*BUILTIN_RANGES, *CUSTOM_TYPES}
    lowered = {n.lower(): n for n in known}
    if name.lower() in lowered:
        return lowered[name.lower()]
    return _DATATYPE_FIXES.get(name.lower())


# --- header ----------------------------------------------------------------

def check_required_headers(header: Sequence[str]) -> Iterable[Finding]:
    """Report each required column header that is absent.

    Suggests a rename when a header matches a required name case-insensitively
    (e.g. ``id`` for ``Id``).
    """
    present = set(header)
    lowered = {h.lower(): h for h in header}
    for required in REQUIRED_COLUMNS:
        if required in present:
            continue
        message = f"required column {required!r} is missing"
        near = lowered.get(required.lower())
        if near is not None:
            message += f" (did you mean the column {near!r}?)"
        yield Finding(Level.ERROR, "required-header", message, column=required)


# --- per-row helpers -------------------------------------------------------

def _cell(row: RawRow, column: str, columns_present: set[str]) -> str | None:
    """Return the (stripped) cell for ``column``, or ``None`` if the column is
    absent from the header entirely. A blank cell returns the empty string."""
    if column not in columns_present:
        return None
    return row.get(column)


def check_id(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Id" not in columns_present:
        return  # required-header check already reports the missing column
    for row in rows:
        raw = row.get("Id")
        if raw.strip() == "":
            yield Finding(Level.ERROR, "id-missing", "Id is missing", line=row.line, column="Id")
            continue
        if raw.startswith(" "):
            yield Finding(
                Level.ERROR, "id-leading-whitespace",
                "Id starts with whitespace", line=row.line, column="Id", value=raw,
            )
        if " " in raw:
            yield Finding(
                Level.INFO, "id-whitespace",
                "Id contains whitespace", line=row.line, column="Id", value=raw,
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
        name = row.get("Datatype").strip()
        if name == "":
            yield Finding(
                Level.ERROR, "datatype-missing",
                "Datatype is missing", line=row.line, column="Datatype",
            )
            continue
        try:
            resolve_datatype(name)
        except UnknownDatatypeError:
            message = f"{name!r} is not a known datatype name"
            suggestion = _suggest_datatype(name)
            if suggestion is not None:
                message += f" (did you mean {suggestion!r}?)"
            yield Finding(
                Level.ERROR, "unknown-datatype", message,
                line=row.line, column="Datatype", value=name,
            )


def check_cardinality(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Cardinality" not in columns_present:
        return
    for row in rows:
        value = row.get("Cardinality").strip()
        if value == "":
            continue
        if value not in ("single", "multiple"):
            yield Finding(
                Level.ERROR, "invalid-cardinality",
                f"invalid cardinality {value!r} (expected 'single' or 'multiple')",
                line=row.line, column="Cardinality", value=value,
            )


def check_pattern(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Pattern" not in columns_present:
        return
    for row in rows:
        value = row.get("Pattern")
        if value.strip() == "":
            continue
        try:
            re.compile(value)
        except re.error as exc:
            yield Finding(
                Level.ERROR, "malformed-pattern",
                f"pattern is not a valid regular expression: {exc}",
                line=row.line, column="Pattern", value=value,
            )


def check_enumeration(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Enumeration" not in columns_present:
        return
    for row in rows:
        value = row.get("Enumeration")
        if value.strip() == "":
            continue
        try:
            parse_enumeration(value)
        except ParseError as exc:
            yield Finding(
                Level.ERROR, "malformed-enumeration",
                f"enumeration is malformed: {exc}",
                line=row.line, column="Enumeration", value=value,
            )


def check_missing_value_codes(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    if "MissingValueCodes" not in columns_present:
        return
    for row in rows:
        value = row.get("MissingValueCodes")
        if value.strip() == "":
            continue
        try:
            parse_missing_value_codes(value)
        except ParseError as exc:
            yield Finding(
                Level.ERROR, "malformed-missing-value-codes",
                f"missing value codes are malformed: {exc}",
                line=row.line, column="MissingValueCodes", value=value,
            )


def check_see_also(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "SeeAlso" not in columns_present:
        return
    for row in rows:
        value = row.get("SeeAlso").strip()
        if value == "":
            continue
        # An absolute URL must have a scheme (e.g. https). urlsplit does not
        # raise on ordinary strings, so we check the parsed scheme directly.
        if not urlsplit(value).scheme:
            yield Finding(
                Level.ERROR, "malformed-see-also",
                "SeeAlso is not an absolute URL",
                line=row.line, column="SeeAlso", value=value,
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
    first_seen: dict[str, int] = {}
    for row in rows:
        row_id = row.get("Id").strip()
        if row_id == "":
            continue
        if row_id in first_seen:
            yield Finding(
                Level.ERROR, "duplicate-id",
                f"duplicate Id {row_id!r} (first seen on line {first_seen[row_id]})",
                line=row.line, column="Id", value=row_id,
            )
        else:
            first_seen[row_id] = row.line
