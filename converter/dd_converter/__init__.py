"""Converter from data dictionary CSV to a LinkML schema.

This package is described in ``CONVERTER_PLAN.md``. The ``grammar``
subpackage is the parser layer: it turns the in-cell mini-grammars used by
data dictionaries (enumerations, missing-value codes, ontology term lists) into
Python objects. It is the one piece that standard LinkML tooling cannot provide,
because the structure is hidden inside string cells in a bespoke notation.
"""

from .datatypes import (
    BUILTIN_RANGES,
    CUSTOM_TYPES,
    ORDERED_DATATYPES,
    CustomType,
    UnknownDatatypeError,
    resolve_datatype,
)
from .emit import EmitOptions, Emitter, emit_schema
from .missing_values import (
    STANDARD_ENUM_NAME,
    STANDARD_MISSING_VALUE_CODES,
    STANDARD_MISSING_VALUE_CODES_TEXT,
    parse_missing_value_codes_file,
)
from .reader import (
    KNOWN_COLUMNS,
    REQUIRED_COLUMNS,
    ReadError,
    Row,
    read_data_dictionary,
)
from .reverse import schema_to_csv, schema_to_rows
from .terms_lookup import LookupError_, lookup_labels
from .units import UnitOfMeasure, lookup_unit

__all__ = [
    "BUILTIN_RANGES",
    "ORDERED_DATATYPES",
    "CUSTOM_TYPES",
    "CustomType",
    "UnknownDatatypeError",
    "resolve_datatype",
    "EmitOptions",
    "Emitter",
    "emit_schema",
    "schema_to_csv",
    "schema_to_rows",
    "STANDARD_ENUM_NAME",
    "STANDARD_MISSING_VALUE_CODES",
    "STANDARD_MISSING_VALUE_CODES_TEXT",
    "parse_missing_value_codes_file",
    "UnitOfMeasure",
    "lookup_unit",
    "lookup_labels",
    "LookupError_",
    "KNOWN_COLUMNS",
    "REQUIRED_COLUMNS",
    "ReadError",
    "Row",
    "read_data_dictionary",
]
