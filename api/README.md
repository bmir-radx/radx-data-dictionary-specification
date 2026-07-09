# Data Dictionary Python API

`dd_api` is an API for programmatic access to a data dictionary: load a
[data dictionary](../SPECIFICATION.md) and work with
**typed, parsed objects** instead of raw CSV cells.

If you are new to this start with the **[Cookbook](COOKBOOK.md)** — ten pasteable recipes
with their output, from "load a file and look around" to "build a dictionary
from scratch". Every docstring in the package also carries a runnable example
(`help(DataDictionary.load)` shows one), and those examples run as doctests,
so they are always accurate.

```python
from dd_api import DataDictionary

dd = DataDictionary.load("my_dictionary.csv")

len(dd)                      # number of data elements
"age" in dd                  # membership test by id
age = dd["age"]              # element by id (dd.get("age") -> None if absent)

for element in dd:           # elements, in file order
    element.id               # "age"
    element.label            # "Age"
    element.datatype         # "integer" (name checked against the spec)
    element.cardinality      # "single" or "multiple"
    element.terms            # ("http://purl.obolibrary.org/obo/NCIT_C25150",)
    element.unit             # "kg" — as written; element.resolved_unit is the
                             # structured unit (name, symbol, UCUM code)
    for choice in element.enumeration:      # parsed "value"=[label](iri) pairs
        choice.value, choice.label, choice.iri
    element.missing_value_codes             # same shape as enumeration
    element.precondition     # 'smoker = "1"' — when the field applies
    element.required         # True when a value must be present

dd.sections                  # section names, in order of first appearance
dd.elements_in_section("Demographics")
```

## Reading and writing

A dictionary round-trips through all three of the toolkit's formats:

```python
dd = DataDictionary.load("my_dictionary.csv")      # CSV in
dd = DataDictionary.from_linkml("my_schema.yaml")  # LinkML schema in
dd = DataDictionary.from_json(payload)             # canonical JSON in

csv_text = dd.to_csv()       # CSV out (canonical formatting)
schema_yaml = dd.to_linkml() # LinkML out, as dd-to-linkml would emit it
json_text = dd.to_json()     # canonical JSON out (for REST APIs)
```

### JSON for REST APIs

`to_json` / `from_json` are the canonical machine-readable representation —
the parsed model as JSON, meant for serving and accepting dictionaries over an
HTTP API. The payload is a versioned wrapper around a list of data-element
objects that mirror the model (blank single values are `null`, list values are
arrays, enumeration items are `{"value", "label", "iri"}` objects):

```json
{
  "format": "dd-json",
  "version": 1,
  "elements": [
    {"id": "sex", "label": "Sex", "datatype": "integer", "cardinality": "single",
     "enumeration": [{"value": "0", "label": "Female", "iri": null},
                     {"value": "1", "label": "Male", "iri": null}],
     "required": true, "...": "..."}
  ]
}
```

The `format`/`version` wrapper lets the contract evolve. (This is distinct
from the printer's JSON, which serialises the printer's *presentation* model
for rendering, not for interchange.)

A [JSON Schema](dd_api/dd-json.schema.json) (Draft 2020-12) describes the
payload, so a REST service can validate requests and responses against it. The
test suite checks that `to_json` output always conforms to it, so the schema
cannot drift from the model.

### The `dd-json` command

Installing `dd-api` also provides a `dd-json` command that converts a
dictionary between formats from the shell — handy for feeding a web API or a
build step. Input format (CSV / LinkML / dd-json) is detected automatically;
output defaults to dd-json:

```sh
dd-json my_dictionary.csv                # -> dd-json on stdout
dd-json my_schema.yaml -o out.json       # LinkML in, dd-json out
dd-json data.json --format csv           # dd-json in, CSV out (also: linkml)
```

`from_linkml` works best with schemas this toolkit generated: those load back
with full fidelity. Schemas written by hand load too — the schema is read
with LinkML's own tooling, so it does not matter which of LinkML's equivalent
styles the author happened to use. The one caveat with a hand-written schema
is that only what it actually records can come back: generated schemas carry
extra annotations (a field's underlying datatype, its unit), and without
those the datatype of an enumerated field falls back to `"string"` and the
unit is left empty. The exact shapes recognised are listed in the
`from_linkml` docstring.

`to_csv` writes canonical formatting (spec column order, `"value"=[label](iri)`
enumerations with single spaces, explicit `single` cardinality), so load →
write preserves the information but not a file's incidental formatting. It
works for hand-built elements too.

## Conventions

- **Blank cells**: optional single values come back as `None`; list-like values
  come back as empty tuples. `if element.description:` and
  `for term in element.terms:` both read naturally.
- **Fail-fast loading**: every cell is parsed eagerly, and the first problem —
  bad header, blank required cell, duplicate id, unknown datatype, malformed
  cell — raises `ReadError`. Row-level problems name the line; where a
  lower-level parser raised, that error is chained as the cause. An object you
  hold is known-good. To list *all* problems in a dictionary instead of
  stopping at the first, use the sibling [validator](../validator/) — that is
  its job.
- **Membership is by id**: `"age" in dd` and `element in dd` (tested via the
  element's id) both work, so `x in dd` holds for everything iteration yields.
- **Escape hatch**: `element.row` is the underlying raw row, for anything the
  typed fields do not cover (e.g. non-standard columns).

Every type the model hands back or raises is importable from `dd_api`
directly: `DataDictionary`, `DataElement`, `EnumItem` (one enumeration
choice), `UnitOfMeasure`, `Row` (the raw row behind an element), `ReadError`,
and `EmitOptions` (for `to_linkml`).

## Install

```
pip install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=api"
```

This pulls in the sibling [converter](../converter/) package automatically —
the API is built on its reader, datatype table, and in-cell grammar parsers,
so the model always agrees with the converter and the specification.

## Design and development

The design decisions are recorded in [`API_PLAN.md`](API_PLAN.md). To run the
tests:

```
pip install -e "./api[test]"
pytest api
```
