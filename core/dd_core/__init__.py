"""Core library for reading and understanding data dictionaries.

The shared foundation the toolkit's tools build on: it reads a data
dictionary CSV into rows, parses the in-cell mini-grammars (enumerations,
missing-value codes, ontology term lists, preconditions), resolves datatype
names and units, and carries the standard missing-value codes. It knows
nothing about LinkML — the CSV↔LinkML conversion lives in the sibling
``dd_linkml`` package, which is built on this one.

The ``grammar`` subpackage is the parser layer: it turns the bespoke string
notations hidden inside dictionary cells into Python objects.
"""

from .datatypes import (
    BUILTIN_RANGES,
    CUSTOM_TYPES,
    ORDERED_DATATYPES,
    CustomType,
    UnknownDatatypeError,
    resolve_datatype,
)
from .missing_values import (
    STANDARD_ENUM_NAME,
    STANDARD_MISSING_VALUE_CODES,
    STANDARD_MISSING_VALUE_CODES_TEXT,
    parse_missing_value_codes_file,
)
from .naming import sanitize_identifier
from .reader import (
    KNOWN_COLUMNS,
    REQUIRED_COLUMNS,
    ReadError,
    Row,
    read_data_dictionary,
)
from .terms_lookup import LookupError_, lookup_labels
from .ucum import UCUM_UNITS, UcumUnit, suggest_ucum, ucum_unit
from .units import UnitOfMeasure, lookup_unit

__all__ = [
    "BUILTIN_RANGES",
    "ORDERED_DATATYPES",
    "CUSTOM_TYPES",
    "CustomType",
    "UnknownDatatypeError",
    "resolve_datatype",
    "STANDARD_ENUM_NAME",
    "STANDARD_MISSING_VALUE_CODES",
    "STANDARD_MISSING_VALUE_CODES_TEXT",
    "parse_missing_value_codes_file",
    "UnitOfMeasure",
    "lookup_unit",
    "UCUM_UNITS",
    "UcumUnit",
    "suggest_ucum",
    "ucum_unit",
    "lookup_labels",
    "LookupError_",
    "KNOWN_COLUMNS",
    "REQUIRED_COLUMNS",
    "ReadError",
    "Row",
    "read_data_dictionary",
    "sanitize_identifier",
]
