"""Map RADx / XSD datatype names to LinkML ranges.

A RADx ``Datatype`` value is either a LinkML built-in range (returned directly)
or a datatype with no LinkML built-in, for which the converter must emit a
custom ``type`` into the output schema's ``types:`` block so the schema is
self-contained (see ``linkml/CONVERTER_PLAN.md``).

Datatype names are case-sensitive per the specification; the maps below use
exact keys. An unknown / mis-cased name is a :class:`UnknownDatatypeError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Union

# --- Direct mappings: RADx/XSD name -> LinkML built-in range ---------------
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

BUILTIN_RANGES: Dict[str, str] = {
    **{name: "string" for name in _STRING_LIKE},
    **{name: "integer" for name in _INTEGER_LIKE},
    "decimal": "decimal",
    "float": "float",
    "double": "double",
    "boolean": "boolean",
    "date": "date",
    "dateTime": "datetime",
    "time": "time",
    "anyURI": "uri",
}


@dataclass(frozen=True)
class CustomType:
    """A LinkML custom ``type`` the converter must emit for a datatype.

    ``name`` is both the RADx datatype name and the emitted type name.
    ``typeof`` is the base LinkML type it derives from. ``pattern`` is an
    optional lexical constraint. ``uri`` records the type's provenance
    (typically ``xsd:<name>``) so the emitted type is self-describing.
    """

    name: str
    typeof: str
    pattern: Optional[str] = None
    uri: Optional[str] = None
    description: Optional[str] = None


# --- Custom types: RADx/XSD name -> CustomType spec ------------------------
#
# XSD types with no LinkML built-in, plus the three RADx-specific names. The
# emitter adds each USED custom type to the output schema's `types:` block.

CUSTOM_TYPES: Dict[str, CustomType] = {
    # RADx-specific datatypes.
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
    "gYearMonth": CustomType("gYearMonth", typeof="string", pattern=r"^-?\d{4}-\d{2}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gYearMonth"),
    "gYear": CustomType("gYear", typeof="string", pattern=r"^-?\d{4}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gYear"),
    "gMonthDay": CustomType("gMonthDay", typeof="string", pattern=r"^--\d{2}-\d{2}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gMonthDay"),
    "gDay": CustomType("gDay", typeof="string", pattern=r"^---\d{2}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gDay"),
    "gMonth": CustomType("gMonth", typeof="string", pattern=r"^--\d{2}(Z|[+-]\d{2}:\d{2})?$", uri="xsd:gMonth"),
    # XSD types with no LinkML built-in; kept as string but with xsd provenance.
    "duration": CustomType("duration", typeof="string", uri="xsd:duration"),
    "hexBinary": CustomType("hexBinary", typeof="string", pattern=r"^([0-9a-fA-F]{2})*$", uri="xsd:hexBinary"),
    "base64Binary": CustomType("base64Binary", typeof="string", uri="xsd:base64Binary"),
    "NOTATION": CustomType("NOTATION", typeof="string", uri="xsd:NOTATION"),
    "ID": CustomType("ID", typeof="string", uri="xsd:ID"),
    "IDREF": CustomType("IDREF", typeof="string", uri="xsd:IDREF"),
    "IDREFS": CustomType("IDREFS", typeof="string", uri="xsd:IDREFS"),
    "ENTITY": CustomType("ENTITY", typeof="string", uri="xsd:ENTITY"),
    "ENTITIES": CustomType("ENTITIES", typeof="string", uri="xsd:ENTITIES"),
}


class UnknownDatatypeError(ValueError):
    """Raised when a Datatype value is not a recognised RADx/XSD datatype name."""


def resolve_datatype(name: str) -> Union[str, CustomType]:
    """Resolve a RADx ``Datatype`` name.

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
        f"must be an XML Schema datatype name or a RADx extension "
        f"(date_mdy, date_dmy, timestamp)."
    )
