# RADx Data Dictionary → LinkML Converter

`radx-dd-to-linkml` converts a [RADx data dictionary](../radx-data-dictionary-specification.md)
CSV into a [LinkML](https://linkml.io) schema. The data dictionary *describes* a
datafile; the generated schema is a formal, machine-processable description of
that datafile that you can validate data against, generate documentation from,
or transform with the wider LinkML tool ecosystem.

## Install

From the repository root:

```sh
pip install ./converter
```

This installs the `radx-dd-to-linkml` command and its dependencies
(`linkml`, `lark`).

## Use it

Convert a data dictionary to a schema file:

```sh
radx-dd-to-linkml my_dictionary.csv -o my_schema.yaml
```

With no `-o`, the schema is written to standard output, so you can pipe it:

```sh
radx-dd-to-linkml my_dictionary.csv | less
```

### Naming the schema

By default the schema's name, id, and root class are derived from the input
filename (`patient_data.csv` → name `patient_data`, class `PatientData`).
Override any of them:

```sh
radx-dd-to-linkml my_dictionary.csv -o my_schema.yaml \
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

```sh
radx-dd-to-linkml my_dictionary.csv -o out.yaml --annotate-terms
BIOPORTAL_API_KEY=… radx-dd-to-linkml my_dictionary.csv -o out.yaml \
    --annotate-terms --resolver bioportal
```

### Other options

| Option | Effect |
| --- | --- |
| `--annotate-enum-values` | After a field enum's `range:`, add a comment listing its `value=label` pairs. |
| `--allow-duplicates` | Tolerate a repeated `Id` (keep the first, skip later ones) instead of failing. |
| `-v`, `--verbose` | Show warnings (unresolved term lookups, non-OBO prefixes, skipped duplicates). |

Run `radx-dd-to-linkml --help` for the complete list.

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
accepts **either** one of that enum's values **or** a standard RADx
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

## Worked examples

The [`examples/`](examples/) folder contains real data dictionaries and the
schemas produced from them: [`gcb.dd.csv`](examples/gcb.dd.csv) →
[`gcb.yaml`](examples/gcb.yaml), and [`rad.dd.csv`](examples/rad.dd.csv) →
[`rad.yaml`](examples/rad.yaml).

## Library use

The pipeline is also importable:

```python
from radx_dd_converter import read_data_dictionary, emit_schema, EmitOptions

rows = read_data_dictionary("my_dictionary.csv")
print(emit_schema(rows, EmitOptions(schema_name="my_data", class_name="Record")))
```

## Design and development

The design decisions behind the mapping are recorded in
[`../linkml/CONVERTER_PLAN.md`](../linkml/CONVERTER_PLAN.md). To run the tests:

```sh
pip install -e "./converter[test]"
pytest converter
```
