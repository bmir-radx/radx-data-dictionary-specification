# RADx Data Dictionary → LinkML Converter

A Python tool that converts a RADx data dictionary CSV into a LinkML schema
describing the target datafile. See [`../linkml/CONVERTER_PLAN.md`](../linkml/CONVERTER_PLAN.md)
for the design.

## Status

Feature-complete for v1. Components:

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
- **Emitter** (`radx_dd_converter/emit.py`) — `emit_schema(rows, options)`
  assembles rows + parsed cells into a `linkml_runtime` `SchemaDefinition` and
  dumps readable YAML (multi-line descriptions as literal `|` blocks; section
  comments and blank lines between slots/enums/types). Implements the full
  mapping: `Datatype` → range / custom type,
  `Enumeration` → generated enum wired via slot `any_of` with the shared
  `StandardMissingValueCodes` (and per-field codes), `Provenance` →
  `source:`/annotation, `Section` → `in_subset`, `Unit` → native `unit:`
  (lookup-assisted, raw preserved), CURIEs kept with OBO prefixes auto-
  registered. A test lints the generated schema and asserts zero errors.

- **CLI** (`radx_dd_converter/cli.py`) — the `radx-dd-to-linkml` console script
  ties the pipeline together: read CSV → emit schema → write YAML. Schema
  name/id/class default from the input filename and can be overridden with
  flags. Reports read/parse/datatype errors cleanly (no traceback). A duplicate
  `Id` is fatal by default; `--allow-duplicates` keeps the first occurrence,
  skips later ones, and warns.

The converter is feature-complete for v1.

## Usage (CLI)

```sh
radx-dd-to-linkml my_dictionary.csv -o my_schema.yaml
# override the derived identifiers:
radx-dd-to-linkml my_dictionary.csv -o my_schema.yaml \
    --name my_data --id https://example.org/my_data --class-name Record
# default output is stdout:
radx-dd-to-linkml my_dictionary.csv | head
# look up ontology term names (via OLS4) and add them as YAML comments
# (requires network; unresolved terms are skipped):
radx-dd-to-linkml my_dictionary.csv -o my_schema.yaml --annotate-terms
```

With `--annotate-terms`, ontology CURIEs are annotated with their labels, e.g.
`- MONDO:0004979  # asthma`. Lookups are de-duplicated, run concurrently, and any
term that cannot be resolved is left as a bare CURIE.

The resolver is selectable with `--resolver`:

- `ols4` (default) — the EBI Ontology Lookup Service; open, no key required.
- `bioportal` — BioPortal; requires an API key via `BIOPORTAL_API_KEY` (or
  `--bioportal-apikey`).

```sh
radx-dd-to-linkml my_dictionary.csv -o out.yaml --annotate-terms --resolver ols4
BIOPORTAL_API_KEY=... radx-dd-to-linkml my_dictionary.csv -o out.yaml \
    --annotate-terms --resolver bioportal
```

`--annotate-enum-values` adds a comment after each field enum's `range:` listing
its `value=label` pairs (capped, with a `(+N more)` overflow), so the allowed
values are visible at the point of use without scrolling to the `enums:` section:

```yaml
- range: SampleTypeEnum  # 0=Saliva | 1=Blood
```

Comment blocks are placed above entries (always on) to make the schema easier
to scan:

- **Field enums** and **sections** get a 3-line block: its number, how many data
  elements use it, and the referencing ids (capped) — useful for spotting a
  shared enum or a large section.
- **Data elements** get a 1-line block: `# Data element n of m`.

```yaml
# Enum 8 of 16
# Used by 111 data elements
# nih_disability | nih_deaf | nih_blind | ... (+105 more)
NoYesOtherEtcEnum:
```

The shared `StandardMissingValueCodes` enum is always emitted last in the
`enums:` section.

## Usage (library)

```python
from radx_dd_converter import read_data_dictionary, emit_schema, EmitOptions

rows = read_data_dictionary("my_dictionary.csv")
print(emit_schema(rows, EmitOptions(schema_name="my_data", class_name="Record")))
```

## Development

```sh
# from the repository root, using the project's virtualenv
.venv/bin/pip install -e converter[test]
.venv/bin/pytest converter
```
