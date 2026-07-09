# Data Dictionary Specification

A specification for **data dictionaries**. A data dictionary describes the
structure of a tabular *datafile* as an ordered list of *data elements* where each 
data element represents a column in the data file, defining its field's identifier (variable name), 
label, datatype, permissible values, units, ontology terms, etc. The specification defines two 
interchangeable serializations, a CSV format (the primary, human-editable one) and an equivalent
[LinkML](https://linkml.io) YAML rendering, and the tooling here converts
between them.

> **Origin:** This specification and toolkit were originally developed for the
> [RADx](https://github.com/canopy-datahub) data hub (which has since evolved
> into [Canopy](https://github.com/canopy-datahub), an open-source platform for
> FAIR-aligned scientific data hubs). Some default value sets reflect that
> origin, but the format itself is general-purpose and not specific to RADx.

📄 **[Read the specification →](SPECIFICATION.md)**

The Markdown specification is the authoritative document. The packages below
are machine-processable renderings and tooling built on top of it: a core
library, a LinkML converter, a printer, a validator, a REDCap converter, and a
high-level Python API.

## Repository contents

| Path | What it is |
| --- | --- |
| [`SPECIFICATION.md`](SPECIFICATION.md) | The authoritative specification. |
| [`core/`](core/) | The core library: reads a data dictionary CSV and parses its in-cell grammars. The foundation the other packages build on. |
| [`linkml/`](linkml/) | Converts between a data dictionary CSV and a [LinkML](https://linkml.io) schema, in both directions; also holds hand-written LinkML renderings of the spec under `schemas/`. |
| [`printer/`](printer/) | Renders a data dictionary to a human-readable HTML page (or JSON). |
| [`validator/`](validator/) | Checks a data dictionary against the specification and reports violations. |
| [`api/`](api/) | A high-level Python API: load a data dictionary and work with typed, parsed objects. |
| [`redcap/`](redcap/) | Converts a REDCap data dictionary export into this format. |

## LinkML converter

[`linkml/`](linkml/) is a Python tool that translates **both directions**
between a data dictionary and a [LinkML](https://linkml.io) schema:

Install it straight from this repository (no clone needed):

```sh
pip install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=linkml"
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
byte-exact. See the [LinkML converter README](linkml/README.md) for the full set of
options and the mapping details.

### Worked examples

Five real data dictionaries and the LinkML schemas the tool produces from
them:

| Data dictionary (input) | Generated LinkML schema (output) | Rendered page |
| --- | --- | --- |
| [`gcb.dd.csv`](examples/gcb.dd.csv) | [`gcb.yaml`](examples/gcb.yaml) | [`gcb.html`](https://htmlpreview.github.io/?https://github.com/bmir-radx/radx-data-dictionary-specification/blob/main/examples/gcb.html) |
| [`rad.dd.csv`](examples/rad.dd.csv) | [`rad.yaml`](examples/rad.yaml) | [`rad.html`](https://htmlpreview.github.io/?https://github.com/bmir-radx/radx-data-dictionary-specification/blob/main/examples/rad.html) |
| [`dht.dd.csv`](examples/dht.dd.csv) | [`dht.yaml`](examples/dht.yaml) | [`dht.html`](https://htmlpreview.github.io/?https://github.com/bmir-radx/radx-data-dictionary-specification/blob/main/examples/dht.html) |
| [`tech.dd.csv`](examples/tech.dd.csv) | [`tech.yaml`](examples/tech.yaml) | [`tech.html`](https://htmlpreview.github.io/?https://github.com/bmir-radx/radx-data-dictionary-specification/blob/main/examples/tech.html) |
| [`up.dd.csv`](examples/up.dd.csv) | [`up.yaml`](examples/up.yaml) | [`up.html`](https://htmlpreview.github.io/?https://github.com/bmir-radx/radx-data-dictionary-specification/blob/main/examples/up.html) |

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
etc. — each with a severity (ERROR / WARNING / INFO) and a line number. It
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
from, and writes to, all three of the toolkit's formats (`load` / `from_linkml`
/ `from_json` in, `to_csv` / `to_linkml` / `to_json` out).

```python
from dd_api import DataDictionary

dd = DataDictionary.load("my_dictionary.csv")
age = dd["age"]
for choice in age.enumeration:
    print(choice.value, choice.label)
```

### The `dd-json` command

Installing the API package also provides `dd-json`, a command that converts a
dictionary between CSV, LinkML, and the canonical JSON from the shell — useful
for feeding a web API. For a command-line tool,
[`pipx`](https://pipx.pypa.io) installs it into its own isolated environment
and puts it on your `PATH`:

```sh
pipx install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=api"

dd-json my_dictionary.csv                # -> canonical JSON on stdout
dd-json my_dictionary.csv --compact      # ...omitting null / empty-list fields
dd-json my_schema.yaml -o out.json       # LinkML in, JSON out
dd-json data.json --format csv           # JSON in, CSV out (also: linkml)
```

The input format (CSV / LinkML / dd-json) is detected automatically; `--format`
chooses the output (default `json`). Use `pip` in place of `pipx` to install
into an existing environment.

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

Alongside the converter, [`linkml/schemas/`](linkml/schemas/) holds two
hand-written LinkML renderings of the specification itself — one
**CSV-faithful** (every column a single string cell) and one **parsed object
model** (in-cell grammars decomposed into structured objects) — plus
[`CONVERTER_PLAN.md`](linkml/CONVERTER_PLAN.md), the converter's design record.

## Releases and upgrading

Every merge to `main` creates a release: a GitHub Action bumps the shared version
of all packages, tags it `vX.Y.Z`, and publishes a
[GitHub release](https://github.com/bmir-radx/radx-data-dictionary-specification/releases).
The bump size follows the merged PR's labels — `release:major` or
`release:minor`, defaulting to a patch bump — and `release:skip` releases
nothing. Because the version changes on each release, `pipx` can upgrade an
installed tool to the latest:

```sh
pipx upgrade dd-api        # (or dd-print, dd-validate, dd-redcap, dd-to-linkml…)
```

The `pip`/`pipx` install commands above track `main` (always the newest
release). To pin to a specific release instead, append the tag to the URL,
e.g. `…radx-data-dictionary-specification.git@v0.3.0#subdirectory=api`.

## License

Released under the [BSD 2-Clause License](LICENSE).
