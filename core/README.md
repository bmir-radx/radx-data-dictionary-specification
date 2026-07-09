# Data Dictionary Core

`dd_core` is the shared foundation the toolkit's tools are built on. It reads a
[data dictionary](../SPECIFICATION.md) CSV into rows and
parses the notations hidden inside its cells, turning bespoke strings into
Python objects. It knows nothing about LinkML — the CSV↔LinkML conversion lives
in the sibling [`dd_linkml`](../linkml/) package, which depends on this one.

## What it provides

- **`read_data_dictionary`** — parse a dictionary CSV (RFC 4180, BOM handling,
  header validation, duplicate detection) into ordered `Row` objects, plus
  `KNOWN_COLUMNS` / `REQUIRED_COLUMNS` and the `ReadError` it raises.
- **`grammar`** — the cell mini-grammars: `parse_enumeration`,
  `parse_missing_value_codes`, `parse_terms`, and `parse_precondition` (with
  the `EnumItem` / `Comparison` / `InSet` / `Contains` / `And` / `Or` node
  types), all raising `ParseError` on malformed input.
- **`resolve_datatype`** and the datatype tables (`BUILTIN_RANGES`,
  `CUSTOM_TYPES`, `ORDERED_DATATYPES`), raising `UnknownDatatypeError`.
- **`lookup_unit`** / `UnitOfMeasure` — the built-in unit table.
- **`lookup_labels`** — resolve ontology term identifiers to names (OLS4 /
  BioPortal), and the standard missing-value codes.

It depends only on `lark` (for the cell grammars) — deliberately light, so
tools that just read dictionaries do not pull in the LinkML stack.

## Use it

```python
from dd_core import read_data_dictionary
from dd_core.grammar import parse_enumeration

rows = read_data_dictionary("my_dictionary.csv")
choices = parse_enumeration('"0"=[No] | "1"=[Yes]')
```

Most users want the higher-level typed model in [`dd_api`](../api/), which is
built on this package.

## Development

```
pip install -e "./core[test]"
pytest core
```
