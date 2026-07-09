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
the tools below (a converter, a printer, and a validator) are machine-processable
renderings and tooling built on top of it.

## Repository contents

| Path | What it is |
| --- | --- |
| [`radx-data-dictionary-specification.md`](radx-data-dictionary-specification.md) | The authoritative specification. |
| [`converter/`](converter/) | A Python tool that converts between a data dictionary CSV and a LinkML schema, in both directions. |
| [`printer/`](printer/) | A Python tool that renders a data dictionary to a human-readable HTML page (or JSON). |
| [`validator/`](validator/) | A Python tool that checks a data dictionary against the specification and reports violations. |
| [`api/`](api/) | A high-level Python API: load a data dictionary and work with typed, parsed objects. |
| [`redcap/`](redcap/) | A Python tool that converts a REDCap data dictionary export into this format. |
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

Five real data dictionaries and the LinkML schemas the converter produces from
them:

| Data dictionary (input) | Generated LinkML schema (output) | Rendered page |
| --- | --- | --- |
| [`gcb.dd.csv`](converter/examples/gcb.dd.csv) | [`gcb.yaml`](converter/examples/gcb.yaml) | [`gcb.html`](converter/examples/gcb.html) |
| [`rad.dd.csv`](converter/examples/rad.dd.csv) | [`rad.yaml`](converter/examples/rad.yaml) | [`rad.html`](converter/examples/rad.html) |
| [`dht.dd.csv`](converter/examples/dht.dd.csv) | [`dht.yaml`](converter/examples/dht.yaml) | [`dht.html`](converter/examples/dht.html) |
| [`tech.dd.csv`](converter/examples/tech.dd.csv) | [`tech.yaml`](converter/examples/tech.yaml) | [`tech.html`](converter/examples/tech.html) |
| [`up.dd.csv`](converter/examples/up.dd.csv) | [`up.yaml`](converter/examples/up.yaml) | [`up.html`](converter/examples/up.html) |

The `up` and `rad` examples show the complete REDCap pipeline: a raw export (`<name>.redcap.csv`) → `redcap-to-dd` → the dictionary (`<name>.dd.csv`) → `dd-to-linkml` → the schema (`<name>.yaml`), whose class `rules` come from the export's branching logic via the `Precondition` field (50 rules for `up`, 5 for `rad`).

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

## Validator

[`validator/`](validator/) checks a data dictionary CSV against the specification
and reports every violation it finds — missing required columns, unknown datatype
names, malformed enumerations and patterns, invalid cardinality, duplicate ids,
and more — each with a severity (ERROR / WARNING / INFO) and a line number. It
does not transform the dictionary; it tells you what is wrong.

```sh
pipx install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=validator"

dd-validate my_dictionary.csv
```

It exits non-zero when any error is found, so it can gate a CI build. See the
[validator README](validator/README.md) for the full set of checks and options.

## Python API

[`api/`](api/) is the toolkit's programmatic front door: load a data dictionary
and work with typed, parsed objects — elements with their enumerations, units,
ontology terms, and missing-value codes already decomposed. A dictionary reads
from, and writes to, both of the toolkit's formats (`load`/`from_linkml` in,
`to_csv`/`to_linkml` out).

```python
from dd_api import DataDictionary

dd = DataDictionary.load("my_dictionary.csv")
age = dd["age"]
for choice in age.enumeration:
    print(choice.value, choice.label)
```

See the [API README](api/README.md) for the conventions and the full surface,
and the [Cookbook](api/COOKBOOK.md) for ten pasteable recipes with their
output.

## REDCap converter

[`redcap/`](redcap/) converts a **REDCap data dictionary export** into this
specification's format — field names, labels, sections, choices, datatypes,
and generated prose descriptions (including plain-English explanations of
REDCap branching logic). The result works with every tool above.

```sh
pipx install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=redcap"

redcap-to-dd redcap_export.csv -o my_dictionary.csv
```

See the [REDCap README](redcap/README.md) for the full mapping.

## Hand-written LinkML schemas

Alongside the converter, [`linkml/`](linkml/) holds two hand-written LinkML
renderings of the specification itself — one **CSV-faithful** (every column a
single string cell) and one **parsed object model** (in-cell grammars decomposed
into structured objects) — plus [`CONVERTER_PLAN.md`](converter/CONVERTER_PLAN.md),
the converter's design record.

## License

Released under the [BSD 2-Clause License](LICENSE).
