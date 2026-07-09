"""Convert a data dictionary between CSV and a LinkML schema.

The CSV→LinkML emitter (:func:`emit_schema`) and the LinkML→CSV reconstruction
(:func:`schema_to_rows` / :func:`schema_to_csv`), plus the ``dd-to-linkml`` and
``linkml-to-dd`` commands. Built on the sibling ``dd_core`` package, which does
the reading and cell-grammar parsing; this package adds only the LinkML mapping.

See ``CONVERTER_PLAN.md`` for the mapping decisions and ``schemas/`` for the
hand-written LinkML renderings of the specification.
"""

from .emit import EmitOptions, Emitter, emit_schema
from .reverse import schema_to_csv, schema_to_rows

__all__ = [
    "EmitOptions",
    "Emitter",
    "emit_schema",
    "schema_to_csv",
    "schema_to_rows",
]
