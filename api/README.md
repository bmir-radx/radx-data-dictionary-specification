# Data Dictionary Python API

`dd_api` is the toolkit's programmatic front door: load a
[data dictionary](../radx-data-dictionary-specification.md) and work with
**typed, parsed objects** instead of raw CSV cells.

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

dd.sections                  # section names, in order of first appearance
dd.elements_in_section("Demographics")
```

## Reading and writing

A dictionary round-trips through both of the toolkit's formats:

```python
dd = DataDictionary.load("my_dictionary.csv")      # CSV in
dd = DataDictionary.from_linkml("my_schema.yaml")  # LinkML schema in

csv_text = dd.to_csv()       # CSV out (canonical formatting)
schema_yaml = dd.to_linkml() # LinkML out, as dd-to-linkml would emit it
```

`from_linkml` primarily inverts what `to_linkml` produces, but also accepts
the common hand-authored LinkML shapes: fields as class `attributes:` or as a
`slots:` list with `slot_usage:` refinements, and enumerations as named enums
(referenced through `any_of` or directly as the `range:`) or inline
`enum_range:`. Only information the schema actually carries can come back —
without the converter's machine annotations, an enumerated field's underlying
datatype defaults to `"string"` and units are not recovered.

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
