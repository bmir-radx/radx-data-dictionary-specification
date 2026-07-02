# RADx Data Dictionary Specification

A specification for the CSV **data dictionaries** used in the RADx data hub. A
data dictionary is a CSV file that describes the structure of another CSV file
(a *datafile*): one row per field, giving each field's identifier, label,
datatype, permissible values, units, ontology terms, and more.

📄 **[Read the specification →](radx-data-dictionary-specification.md)**

The Markdown specification is the authoritative document. The LinkML schemas and
the converter below are machine-processable renderings and tooling built on top
of it.

## Repository contents

| Path | What it is |
| --- | --- |
| [`radx-data-dictionary-specification.md`](radx-data-dictionary-specification.md) | The authoritative specification. |
| [`linkml/`](linkml/) | [LinkML](https://linkml.io) renderings of the specification (see below). |
| [`converter/`](converter/) | `radx-dd-to-linkml` — a Python tool that converts a data dictionary CSV into a LinkML schema. |

## LinkML representation

The [`linkml/`](linkml/) folder holds two LinkML renderings of the
specification, plus the converter's design notes:

- [`linkml/data-dictionary-csv.yaml`](linkml/data-dictionary-csv.yaml) — a
  **CSV-faithful** schema: one row per data element, every column a single
  string cell. Rich values (enumerations, ontology terms) stay encoded in-cell
  using the grammars defined in the specification.
- [`linkml/data-dictionary.yaml`](linkml/data-dictionary.yaml) — the **parsed
  object model**: the same information once the in-cell grammars have been
  decomposed into structured objects.
- [`linkml/CONVERTER_PLAN.md`](linkml/CONVERTER_PLAN.md) — the design record for
  the converter.

## Converter

[`converter/`](converter/) contains `radx-dd-to-linkml`, which reads a RADx data
dictionary CSV and emits a LinkML schema describing the *target datafile* (one
slot per data element):

```sh
pip install ./converter
radx-dd-to-linkml my_dictionary.csv -o my_schema.yaml
```

See the [converter README](converter/README.md) for the full set of options
(ontology term-name lookup, enum-value annotations, and more).

## License

Released under the [BSD 2-Clause License](LICENSE).
