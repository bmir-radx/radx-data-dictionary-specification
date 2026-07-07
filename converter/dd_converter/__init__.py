"""Read, convert, and work with data dictionaries.

Two ways in:

* **High-level** — :class:`DataDictionary` / :class:`DataElement` (see
  ``model.py`` and ``API_PLAN.md``): load a dictionary and get typed, parsed
  objects. Start here for programmatic access::

      from dd_converter import DataDictionary
      dd = DataDictionary.load("my_dictionary.csv")

* **Low-level** — the pieces the model is built from: ``read_data_dictionary``
  (raw rows), the ``grammar`` subpackage (the in-cell mini-grammars for
  enumerations, missing-value codes, and term lists), ``resolve_datatype``,
  and the LinkML conversion functions (``emit_schema``, ``schema_to_csv``).

The CSV↔LinkML conversion is described in ``linkml/CONVERTER_PLAN.md``.
"""

from .datatypes import (
    BUILTIN_RANGES,
    CUSTOM_TYPES,
    CustomType,
    UnknownDatatypeError,
    resolve_datatype,
)
from .emit import EmitOptions, Emitter, emit_schema
from .grammar import EnumItem
from .model import DataDictionary, DataElement
from .reverse import schema_to_csv, schema_to_rows
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
from .units import UnitOfMeasure, lookup_unit

__all__ = [
    "DataDictionary",
    "DataElement",
    "EnumItem",
    "BUILTIN_RANGES",
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
    "KNOWN_COLUMNS",
    "REQUIRED_COLUMNS",
    "ReadError",
    "Row",
    "read_data_dictionary",
]
