# RADx Data Dictionary Specification

A specification for CSV data dictionaries in the RADx data hub.  You can view the specification [here](https://github.com/bmir-radx/radx-data-dictionary-specification/blob/main/radx-data-dictionary-specification.md).

## LinkML Representation

A [LinkML](https://linkml.io) rendering of the specification is available in the [`linkml/`](linkml/) folder:

- [`linkml/data-dictionary-csv.yaml`](linkml/data-dictionary-csv.yaml) — a CSV-faithful schema: one row per data element, with every column a single string cell (rich values such as enumerations and ontology terms remain encoded in-cell using the grammars defined in the specification).
- [`linkml/data-dictionary.yaml`](linkml/data-dictionary.yaml) — the parsed object model: the same information once the in-cell grammars have been decomposed into structured objects.
- [`linkml/CONVERTER_PLAN.md`](linkml/CONVERTER_PLAN.md) — a design plan for a tool that converts a RADx data dictionary CSV into a LinkML schema describing the target datafile.

The authoritative specification remains the Markdown document above; the LinkML schemas are a machine-processable rendering of it.
