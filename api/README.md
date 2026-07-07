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
    element.unit             # "kg" — and element.unit_of_measure for the
                             # structured unit (name, symbol, UCUM code)
    for choice in element.enumeration:      # parsed "value"=[label](iri) pairs
        choice.value, choice.label, choice.iri
    element.missing_value_codes             # same shape as enumeration

dd.sections                  # section names, in order of first appearance
dd.elements_in_section("Demographics")
dd.to_linkml()               # the LinkML schema, as dd-to-linkml would emit it
```

## Conventions

- **Blank cells**: optional single values come back as `None`; list-like values
  come back as empty tuples. `if element.description:` and
  `for term in element.terms:` both read naturally.
- **Fail-fast loading**: every cell is parsed eagerly, and the first problem —
  bad header, blank required cell, duplicate id, unknown datatype, malformed
  cell — raises `ReadError` with the line number in the message and the
  specific parse error chained as the cause. An object you hold is known-good.
  To list *all* problems in a dictionary instead of stopping at the first, use
  the sibling [validator](../validator/) — that is its job.
- **Escape hatch**: `element.row` is the underlying raw row, for anything the
  typed fields do not cover (e.g. non-standard columns).

Everything a caller touches is importable from `dd_api` directly:
`DataDictionary`, `DataElement`, `EnumItem` (one enumeration choice),
`UnitOfMeasure`, `ReadError`, and `EmitOptions` (for `to_linkml`).

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
