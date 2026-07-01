# RADx Data Dictionary → LinkML Converter

A Python tool that converts a RADx data dictionary CSV into a LinkML schema
describing the target datafile. See [`../linkml/CONVERTER_PLAN.md`](../linkml/CONVERTER_PLAN.md)
for the design.

## Status

Work in progress. Implemented so far:

- **Reader** (`radx_dd_converter/reader.py`) — `read_data_dictionary` parses a
  data dictionary CSV per RFC 4180, validates the header (required columns
  `Id`/`Label`/`Datatype`, duplicate detection), and returns ordered `Row`
  objects (row order is significant). Errors on blank required cells and
  duplicate `Id`s; preserves extra (non-canonical) columns.
- **Parser layer** (`radx_dd_converter/grammar/`) — parses the in-cell
  mini-grammars used by RADx data dictionaries:
  - `parse_enumeration` / `parse_missing_value_codes` — the
    `"value"=[label](iri) | ...` syntax, driven by a Lark grammar
    (`grammar/enumeration.lark`) that mirrors the EBNF in the specification.
  - `parse_terms` — splits a `Terms` cell into IRI/CURIE tokens.
- **Datatype mapping** (`radx_dd_converter/datatypes.py`) — `resolve_datatype`
  maps a RADx/XSD datatype name to either a LinkML built-in range or a
  `CustomType` the emitter must add to the schema's `types:` block. Covers all
  47 allowable names (a test checks this against the schema's `DatatypeEnum`);
  case-sensitive, unknown names raise.
- **Constant tables** — `missing_values.py` holds the 25 standard
  missing-value codes (stored as the spec's verbatim default string and parsed
  by the converter's own parser); `units.py` provides `lookup_unit`, mapping a
  raw `Unit` cell (by name or symbol) to a structured `UnitOfMeasure`.

Not yet implemented: the schema emitter and the CLI.

## Development

```sh
# from the repository root, using the project's virtualenv
.venv/bin/pip install -e converter[test]
.venv/bin/pytest converter
```
