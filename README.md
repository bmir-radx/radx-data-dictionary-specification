# Data Dictionary Specification

A specification for CSV **data dictionaries**. A data dictionary is a CSV file
that describes the structure of another CSV file (a *datafile*): one row per
field, giving each field's identifier, label, datatype, permissible values,
units, ontology terms, and more.

> **Origin:** This specification and toolkit were originally developed for the
> [RADx](https://github.com/canopy-datahub) data hub (which has since evolved
> into [Canopy](https://github.com/canopy-datahub), an open-source platform for
> FAIR-aligned scientific data hubs). Some default value sets reflect that
> origin, but the format itself is general-purpose and not specific to RADx.

📄 **[Read the specification →](radx-data-dictionary-specification.md)**

The Markdown specification is the authoritative document. The LinkML schemas and
the tools below (a converter and a printer) are machine-processable renderings
and tooling built on top of it.

## Repository contents

| Path | What it is |
| --- | --- |
| [`radx-data-dictionary-specification.md`](radx-data-dictionary-specification.md) | The authoritative specification. |
| [`converter/`](converter/) | A Python tool that converts between a data dictionary CSV and a LinkML schema, in both directions. |
| [`printer/`](printer/) | A Python tool that renders a data dictionary to a human-readable HTML page (or JSON). |
| [`linkml/`](linkml/) | Hand-written [LinkML](https://linkml.io) renderings of the specification. |

## Converter

[`converter/`](converter/) is a Python tool that translates **both directions**
between a data dictionary and a [LinkML](https://linkml.io) schema:

Install it straight from this repository (no clone needed):

```sh
pip install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=converter"
```

Then convert in either direction:

```sh
# Data dictionary CSV -> LinkML schema
dd-to-linkml my_dictionary.csv -o my_schema.yaml

# LinkML schema -> data dictionary CSV
linkml-to-dd my_schema.yaml -o my_dictionary.csv
```

The generated schema describes the *target datafile* — one slot per data
element — so datafiles can be validated and documented with standard LinkML
tooling. The round-trip is *semantic* (the same information is preserved), not
byte-exact. See the [converter README](converter/README.md) for the full set of
options and the mapping details.

### Worked examples

Two real data dictionaries and the LinkML schemas the converter produces from
them:

| Data dictionary (input) | Generated LinkML schema (output) |
| --- | --- |
| [`gcb.dd.csv`](converter/examples/gcb.dd.csv) | [`gcb.yaml`](converter/examples/gcb.yaml) |
| [`rad.dd.csv`](converter/examples/rad.dd.csv) | [`rad.yaml`](converter/examples/rad.yaml) |

## Printer

[`printer/`](printer/) renders a data dictionary into a human-readable,
self-contained **HTML** page (or JSON) — grouped by section, with each data
element shown as a card (id, label, facets, description, and enumeration). It
reads a data dictionary CSV or a generated LinkML schema.

```sh
pipx install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=printer"

dd-print my_dictionary.csv -o my_dictionary.html
```

See the [printer README](printer/README.md) for options and details.

## Hand-written LinkML schemas

Alongside the converter, [`linkml/`](linkml/) holds two hand-written LinkML
renderings of the specification itself — one **CSV-faithful** (every column a
single string cell) and one **parsed object model** (in-cell grammars decomposed
into structured objects) — plus [`CONVERTER_PLAN.md`](linkml/CONVERTER_PLAN.md),
the converter's design record.

## License

Released under the [BSD 2-Clause License](LICENSE).
