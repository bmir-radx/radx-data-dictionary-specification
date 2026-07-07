# High-Level API — Plan

A clean, well-documented programmatic API for data dictionaries: load a
dictionary and get **typed, parsed objects** instead of raw cell strings.

## Motivation

The toolkit's programmatic surface is currently spread across three packages
and is low-level: `read_data_dictionary` returns `Row` objects that are just
dicts of raw cell strings, and callers must glue the per-cell parsers
(`parse_enumeration`, `parse_terms`, `resolve_datatype`, `lookup_unit`)
together themselves. The printer built its own parsed model, but it is
presentation-scoped and lives in the printer.

This adds the missing piece: a first-class object model, so that:

```python
from dd_api import DataDictionary

dd = DataDictionary.load("my_dictionary.csv")

for element in dd:
    print(element.id, element.label, element.datatype)
    for choice in element.enumeration:
        print(" ", choice.value, choice.label)

age = dd["age"]          # lookup by id
"weight" in dd           # membership test
dd.sections              # section names, in order of first appearance
```

## Where it lives

A top-level `api/` folder — package `dd_api` — following the repo's
one-folder-per-tool layout (`converter/`, `printer/`, `validator/`). This
keeps the converter focused on converting; the API is its own deliverable
with its own README and plan. It depends on `dd_converter` (the same
direct-git dependency pattern the printer and validator use) for the parsing
it is built on, and re-exports every type the model hands back or raises
(`DataDictionary`, `DataElement`, `EnumItem`, `UnitOfMeasure`, `Row`,
`ReadError`, `EmitOptions`) so day-to-day use needs only `dd_api`.

## The model

Two classes, both plain frozen dataclasses (easy to read, print, and test):

### `DataElement`

One row of the dictionary, fully parsed. Field-by-field:

| Field | Type | Source column & parsing |
| --- | --- | --- |
| `id` | `str` | `Id` (stripped; required) |
| `label` | `str` | `Label` (stripped; required) |
| `aliases` | `tuple[str, ...]` | `Aliases`, pipe-delimited (as the emitter parses it) |
| `description` | `str \| None` | `Description`; `None` when blank |
| `section` | `str \| None` | `Section`; `None` when blank |
| `cardinality` | `str` | `Cardinality`: `"single"` (default when blank) or `"multiple"`; any other value is an error |
| `terms` | `tuple[str, ...]` | `Terms`, via `grammar.parse_terms` |
| `datatype` | `str` | `Datatype` (required); the name is checked with `resolve_datatype` |
| `pattern` | `str \| None` | `Pattern`; `None` when blank (not compiled — it is an XSD regex) |
| `unit` | `str \| None` | `Unit`, the raw text; `None` when blank |
| `resolved_unit` | `UnitOfMeasure \| None` | the structured unit when `unit` is in the built-in table |
| `enumeration` | `tuple[EnumItem, ...]` | `Enumeration`, via `grammar.parse_enumeration` |
| `missing_value_codes` | `tuple[EnumItem, ...]` | `MissingValueCodes`, via `grammar.parse_missing_value_codes` |
| `examples` | `tuple[str, ...]` | `Examples`, pipe-delimited |
| `notes` | `str \| None` | `Notes`; `None` when blank |
| `provenance` | `str \| None` | `Provenance`; `None` when blank |
| `see_also` | `str \| None` | `SeeAlso`; `None` when blank |
| `line` | `int \| None` | 1-based line in the source CSV; `None` for a hand-built element; not part of equality |
| `row` | `Row` | the underlying raw row (escape hatch for extra columns; excluded from `repr`) |

Convenience: `is_enumerated` (has enumeration choices), `is_multivalued`
(cardinality is `"multiple"`; named after the LinkML property it maps to).

Reused types, not new ones: `EnumItem` (value/label/iri) from the grammar and
`UnitOfMeasure` (descriptive_name/symbol/ucum_code) from `units` are already
exactly the right shapes.

### `DataDictionary`

An ordered, id-indexed collection of `DataElement`s:

- `DataDictionary.load(source, *, allow_duplicates=False)` — from a CSV path
  or open file (delegates to `read_data_dictionary`, so all its guarantees
  hold: RFC 4180, BOM handling, header validation, duplicate detection).
- `DataDictionary.from_linkml(source)` — from a LinkML schema (path, open
  file, or parsed dict). Read through LinkML's own `SchemaView`, so the
  representation variety is normalised: `attributes:` or `slots:` +
  `slot_usage:` (including `is_a`/`mixins` inheritance and imports), and
  enumerations as named enums (via `any_of` or directly as the `range:`) or
  inline `enum_range:`. Without the converter's annotations, an enumerated
  field's datatype defaults to `string` and units are not recovered.
- `DataDictionary.from_rows(rows)` — from already-read `Row`s or plain
  column-name → cell mappings (what `schema_to_rows` returns).
- `dd.to_csv()` — canonical data dictionary CSV text (spec column order,
  canonical enumeration spacing, explicit `single` cardinality); works for
  hand-built elements too.
- `len(dd)`, `iter(dd)` (file order), `x in dd` (an id string or an element,
  tested by id), `dd["age"]` (`KeyError` if absent), `dd.get("age")` (`None`
  if absent). The constructor itself rejects duplicate ids (`ValueError`).
- `dd.elements` — the elements as a tuple.
- `dd.ids` — the ids, in order.
- `dd.sections` — unique section names, in order of first appearance
  (`None` never appears in this list).
- `dd.elements_in_section(section)` — the elements of one section; pass
  `None` for elements with no section.
- `dd.to_linkml(options=None)` — the LinkML schema YAML for this dictionary
  (wraps `emit_schema`; keeps the original rows so output is identical to
  `dd-to-linkml`).

## Error handling: fail-fast, one exception type

`load` **parses every cell eagerly** and raises `ReadError` (the converter's
existing exception) on the first problem, with the line number in the message
and the original exception chained as the cause. Rationale:

- A high-level API should hand back objects that are *known good* — no
  deferred surprises when an attribute is first touched.
- One documented exception type (`ReadError`) is easy to catch; the cause
  chain preserves the specific `ParseError`/`UnknownDatatypeError` detail.
- Callers who want *all* problems listed, not just the first, use the
  validator (`dd-validate` / `dd_validator.validate`) — that is its job.

This makes the model deliberately **stricter than the emitter** in one place:
an invalid `Cardinality` value (anything other than blank/`single`/`multiple`)
raises, where the emitter silently treats it as `single`. Silent coercion is
wrong for an API whose purpose is comprehension.

## Documentation

- Full docstrings on both classes and every method (the module docstring
  carries a worked example).
- A "Python API" section in `converter/README.md` with the same example.
- A pointer from the top-level README.

## Adoption by the other tools

- **Printer** — refactored onto this model: its loader maps `DataElement`s
  onto the presentation model (`Record`/`Section`), and both input kinds (CSV
  and LinkML) come through `dd_api`. Rendered output verified byte-identical
  on the worked examples (JSON differs only in stripped trailing whitespace).
- **Converter** — *not* refactored: it is the layer this model is built on;
  depending on `dd_api` from `dd_converter` would be circular.
- **Validator** — *not* refactored, deliberately: it must accept invalid
  dictionaries that this fail-fast model refuses to represent. Its whole
  purpose is the inputs `DataDictionary.load` rejects; it shares the same
  underlying `dd_converter` parsers instead.

## Non-goals (v1)

- Lookup by alias, mutation of loaded elements, or a datafile-validation API.

## Tests

`api/tests/test_model.py`: attribute parsing for every field (blank →
`None`/empty-tuple conventions), cardinality default/multiple/invalid,
eager errors carry line numbers and chain the cause, collection protocol
(`len`/`iter`/`in`/`[]`/`get`), section ordering and filtering,
`to_linkml` parity with `emit_schema`, unit resolution, `from_rows`.
