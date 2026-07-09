"""Map XSD datatype names to LinkML ranges.

A ``Datatype`` value is either a LinkML built-in range (returned directly)
or a datatype with no LinkML built-in, for which the converter must emit a
custom ``type`` into the output schema's ``types:`` block so the schema is
self-contained (see ``CONVERTER_PLAN.md``).

Datatype names are case-sensitive per the specification; the maps below use
exact keys. An unknown / mis-cased name is a :class:`UnknownDatatypeError`.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Direct mappings: XSD name -> LinkML built-in range ---------------
#
# Grouped by target for readability. Every one of the 47 allowable datatype
# names is accounted for either here or in CUSTOM_TYPES below.

_STRING_LIKE = (
    "string",
    "normalizedString",
    "token",
    "language",
    "Name",
    "NCName",
    "NMTOKEN",
    "NMTOKENS",
    "QName",
)

_INTEGER_LIKE = (
    "integer",
    "int",
    "short",
    "byte",
    "long",
    "nonNegativeInteger",
    "nonPositiveInteger",
    "negativeInteger",
    "positiveInteger",
    "unsignedLong",
    "unsignedInt",
    "unsignedShort",
    "unsignedByte",
)

BUILTIN_RANGES: dict[str, str] = {
    **dict.fromkeys(_STRING_LIKE, "string"),
    **dict.fromkeys(_INTEGER_LIKE, "integer"),
    "decimal": "decimal",
    "float": "float",
    "double": "double",
    "boolean": "boolean",
    "date": "date",
    "dateTime": "datetime",
    "time": "time",
    "anyURI": "uri",
}

# Datatypes whose value space has a total order: the numeric datatypes plus
# dates and times. Only these support the Precondition ordering predicates
# (< <= > >=) -- see "Field: Precondition" in the specification.
ORDERED_DATATYPES: frozenset[str] = frozenset(
    (
        *_INTEGER_LIKE,
        "decimal",
        "float",
        "double",
        "date",
        "dateTime",
        "time",
        # Ordered extension datatypes (dates and Unix timestamps).
        "date_mdy",
        "date_dmy",
        "timestamp",
    )
)


@dataclass(frozen=True)
class CustomType:
    """A LinkML custom ``type`` the converter must emit for a datatype.

    ``name`` is both the datatype name and the emitted type name.
    ``typeof`` is the base LinkML type it derives from. ``pattern`` is an
    optional lexical constraint. ``uri`` records the type's provenance
    (typically ``xsd:<name>``) so the emitted type is self-describing.
    """

    name: str
    typeof: str
    pattern: str | None = None
    uri: str | None = None
    description: str | None = None


# --- Custom types: XSD name -> CustomType spec ------------------------
#
# XSD types with no LinkML built-in, plus three non-XSD extension names. The
# emitter adds each USED custom type to the output schema's `types:` block.

CUSTOM_TYPES: dict[str, CustomType] = {
    # Non-XSD extension datatypes.
    "date_mdy": CustomType(
        "date_mdy",
        typeof="date",
        pattern=r"^\d{2}/\d{2}/\d{4}$",
        description="US-formatted date with slashes (mm/dd/yyyy).",
    ),
    "date_dmy": CustomType(
        "date_dmy",
        typeof="date",
        pattern=r"^\d{2}/\d{2}/\d{4}$",
        description="International-formatted date with slashes (dd/mm/yyyy).",
    ),
    "timestamp": CustomType(
        "timestamp",
        typeof="integer",
        pattern=r"^[0-9]+$",
        description="A long integer representing a Unix timestamp.",
    ),
    # XSD gregorian date/time fragments (no LinkML built-in).
    "gYearMonth": CustomType(
        "gYearMonth", typeof="string",
        pattern=r"^-?\d{4}-\d{2}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gYearMonth",
    ),
    "gYear": CustomType(
        "gYear", typeof="string",
        pattern=r"^-?\d{4}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gYear",
    ),
    "gMonthDay": CustomType(
        "gMonthDay", typeof="string",
        pattern=r"^--\d{2}-\d{2}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gMonthDay",
    ),
    "gDay": CustomType(
        "gDay", typeof="string",
        pattern=r"^---\d{2}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gDay",
    ),
    "gMonth": CustomType(
        "gMonth", typeof="string",
        pattern=r"^--\d{2}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gMonth",
    ),
    # XSD types with no LinkML built-in; kept as string but with xsd provenance.
    "duration": CustomType("duration", typeof="string", uri="xsd:duration"),
    "hexBinary": CustomType(
        "hexBinary", typeof="string",
        pattern=r"^([0-9a-fA-F]{2})*$", uri="xsd:hexBinary",
    ),
    "base64Binary": CustomType("base64Binary", typeof="string", uri="xsd:base64Binary"),
    "NOTATION": CustomType("NOTATION", typeof="string", uri="xsd:NOTATION"),
    "ID": CustomType("ID", typeof="string", uri="xsd:ID"),
    "IDREF": CustomType("IDREF", typeof="string", uri="xsd:IDREF"),
    "IDREFS": CustomType("IDREFS", typeof="string", uri="xsd:IDREFS"),
    "ENTITY": CustomType("ENTITY", typeof="string", uri="xsd:ENTITY"),
    "ENTITIES": CustomType("ENTITIES", typeof="string", uri="xsd:ENTITIES"),
}


class UnknownDatatypeError(ValueError):
    """Raised when a Datatype value is not a recognised XSD datatype name."""


def resolve_datatype(name: str) -> str | CustomType:
    """Resolve a ``Datatype`` name.

    Returns either a LinkML built-in range name (``str``) that can be used
    directly as a slot ``range``, or a :class:`CustomType` that the emitter must
    add to the schema's ``types:`` block (and whose ``name`` is then used as the
    slot ``range``).

    Raises :class:`UnknownDatatypeError` for an unrecognised or mis-cased name.
    """
    if name in BUILTIN_RANGES:
        return BUILTIN_RANGES[name]
    if name in CUSTOM_TYPES:
        return CUSTOM_TYPES[name]
    raise UnknownDatatypeError(
        f"Unknown datatype name {name!r}. Datatype names are case-sensitive and "
        f"must be an XML Schema datatype name or a non-XSD extension "
        f"(date_mdy, date_dmy, timestamp)."
    )
