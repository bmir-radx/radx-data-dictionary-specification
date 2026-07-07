# Data Dictionary → LinkML Converter

`dd-to-linkml` converts a [data dictionary](../radx-data-dictionary-specification.md)
CSV into a [LinkML](https://linkml.io) schema. The data dictionary *describes* a
datafile; the generated schema is a formal, machine-processable description of
that datafile that you can validate data against, generate documentation from,
or transform with the wider LinkML tool ecosystem.

## Install

Install directly from the repository — no clone required:

```
pip install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=converter"
```

For a CLI tool, [`pipx`](https://pipx.pypa.io) installs it into its own isolated
environment and puts the commands on your `PATH`:

```
pipx install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=converter"
```

On first use of pipx, its bin directory may not be on your `PATH` (pipx warns
if so). Run `pipx ensurepath` once — then open a new terminal — to add it, after
which the commands are available everywhere.

Either way this installs the `dd-to-linkml` and `linkml-to-dd`
commands and their dependencies (`linkml`, `lark`). If you have cloned the
repository, `pip install ./converter` from the repo root works too.

## Use it

Convert a data dictionary to a schema file:

```
dd-to-linkml my_dictionary.csv -o my_schema.yaml
```

With no `-o`, the schema is written to standard output, so you can pipe it:

```
dd-to-linkml my_dictionary.csv | less
```

### Naming the schema

By default the schema's name, id, and root class are derived from the input
filename (`patient_data.csv` → name `patient_data`, class `PatientData`).
Override any of them:

```
dd-to-linkml my_dictionary.csv -o my_schema.yaml \
    --name my_data --id https://example.org/my_data --class-name Record
```

### Adding ontology term names

Data dictionaries reference ontology terms by identifier (e.g. `MONDO:0004979`).
With `--annotate-terms`, the converter looks each up and adds its human-readable
name as a comment, so the schema is easier to read:

```yaml
related_mappings:
- MONDO:0004979  # asthma
```

Lookups require network access and are de-duplicated; any term that cannot be
resolved is left as a bare identifier. Choose the lookup service with
`--resolver`:

- `ols4` (default) — the EBI Ontology Lookup Service; open, no key required.
- `bioportal` — requires an API key via the `BIOPORTAL_API_KEY` environment
  variable (or `--bioportal-apikey`).

```
dd-to-linkml my_dictionary.csv -o out.yaml --annotate-terms
BIOPORTAL_API_KEY=… dd-to-linkml my_dictionary.csv -o out.yaml \
    --annotate-terms --resolver bioportal
```

### Other options

| Option | Effect |
| --- | --- |
| `--annotate-enum-values` | After a field enum's `range:`, add a comment listing its `value=label` pairs. |
| `--allow-duplicates` | Tolerate a repeated `Id` (keep the first, skip later ones) instead of failing. |
| `-v`, `--verbose` | Show warnings (unresolved term lookups, non-OBO prefixes, skipped duplicates). |

Run `dd-to-linkml --help` for the complete list.

## What gets generated

The output is a LinkML schema with a single class — the *datafile* — whose
**slots are the data dictionary's data elements, in order**. Each dictionary
column maps to a LinkML feature of the slot:

| Data dictionary column | In the generated schema |
| --- | --- |
| `Id` | slot name |
| `Label` | slot `title` |
| `Description` | slot `description` |
| `Datatype` | slot `range` (a LinkML built-in, or a generated custom `type` for datatypes like `date_mdy` / `timestamp`) |
| `Pattern` | slot `pattern` |
| `Cardinality` | `multivalued: true` when `multiple` |
| `Enumeration` | a generated enum, referenced from the slot (see below) |
| `Unit` | native `unit:` (matched to a known unit where possible; the raw value is always kept) |
| `Terms` | `related_mappings` (ontology CURIEs; their prefixes are declared in the schema) |
| `Aliases` / `Examples` | slot `aliases` / `examples` |
| `Provenance` / `SeeAlso` | slot `source` / `see_also` |
| `Section` | a LinkML `subset`, referenced from the slot via `in_subset` |
| `MissingValueCodes` | folded into the enum union (see below) |

### Enumerations and missing-value codes

A data element with an `Enumeration` becomes a generated enum, and the slot
accepts **either** one of that enum's values **or** a standard
missing-value code. For example, this data dictionary row:

```csv
Id,Label,Datatype,Enumeration
sample_type,Sample Type,integer,"""0""=[Saliva] | ""1""=[Blood]"
```

produces (comment lines elided for brevity):

```yaml
classes:
  Record:
    attributes:
      sample_type:
        title: Sample Type
        any_of:
        - range: SampleTypeEnum
        - range: StandardMissingValueCodes
        annotations:
          value_datatype: integer
enums:
  SampleTypeEnum:
    permissible_values:
      '0':
        title: Saliva
      '1':
        title: Blood
```

Identical enumerations are collapsed into one shared enum. An enum used by a
single data element is named after it (`SampleTypeEnum` above); an enum shared
by several is named after its values instead (e.g. a reused `No`/`Yes` set
becomes `NoYesEnum`), since no single field owns it. The 25 standard
missing-value codes are emitted once as `StandardMissingValueCodes`.

### Readability

The generated YAML is formatted to be read by humans as well as tools:
multi-line descriptions use block (`|`) style, and each enum, section, and data
element carries a short comment block noting its position and (for enums and
sections) which data elements reference it.

## Reconstructing the dictionary (round-trip)

The reverse tool `linkml-to-dd` rebuilds a data dictionary CSV from a
generated schema:

```
linkml-to-dd my_schema.yaml -o my_dictionary.csv
```

The round-trip (CSV → LinkML → CSV) is **semantic, not byte-exact**: the forward
conversion normalises some things for readability — it strips trailing
whitespace and blank lines from descriptions, re-joins `Terms` with single
spaces, treats a blank `Cardinality` as the default `single`, and re-serialises
the `Enumeration` cell in a canonical `"value"=[label](iri)` form. The
reconstructed dictionary carries the same information (verified field-by-field
on the worked examples) but a cell may not match the original character for
character.

## Worked examples

The [`examples/`](examples/) folder contains real data dictionaries and the
schemas produced from them: [`gcb.dd.csv`](examples/gcb.dd.csv) →
[`gcb.yaml`](examples/gcb.yaml), and [`rad.dd.csv`](examples/rad.dd.csv) →
[`rad.yaml`](examples/rad.yaml).

## Python API

For programmatic access, load a dictionary into the high-level object model:
every cell is parsed for you, and you get typed objects rather than raw
strings.

```python
from dd_converter import DataDictionary

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

Blank optional cells come back as `None` (single values) or empty tuples
(lists). Loading is fail-fast: the first problem — bad header, blank required
cell, duplicate id, unknown datatype, malformed cell — raises `ReadError` with
the line number. To list *all* problems in a dictionary instead, use the
sibling [validator](../validator/).

The lower-level pieces the model is built from are importable too:

```python
from dd_converter import read_data_dictionary, emit_schema, EmitOptions

rows = read_data_dictionary("my_dictionary.csv")   # raw rows (cell strings)
print(emit_schema(rows, EmitOptions(schema_name="my_data", class_name="Record")))
```

The API's design is recorded in [`API_PLAN.md`](API_PLAN.md).

## Design and development

The design decisions behind the mapping are recorded in
[`../linkml/CONVERTER_PLAN.md`](../linkml/CONVERTER_PLAN.md). To run the tests:

```
pip install -e "./converter[test]"
pytest converter
```
