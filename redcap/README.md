# REDCap Data Dictionary Converter

`redcap-to-dd` converts a **REDCap data dictionary** — the CSV a REDCap
project exports to describe its instruments — into a data dictionary in
[this specification's format](../radx-data-dictionary-specification.md).
Once converted, the whole toolkit applies: render it with the
[printer](../printer/), check it with the [validator](../validator/), turn it
into a LinkML schema with the [converter](../converter/), or work with it in
Python through the [API](../api/).

## What carries over

| REDCap | Converted dictionary |
| --- | --- |
| Variable / Field Name | `Id` |
| Field Label (+ Field Note in parens) | `Label` |
| Section Header (carried forward over blank cells) | `Section` |
| Field Type `checkbox` | `Cardinality` = `multiple` (else `single`) |
| Choices (`1, Yes \| 2, No`) | `Enumeration` (`"1"=[Yes] \| "2"=[No]`) |
| Text Validation Type (`integer`, `number_2dp`, `date_mdy`, …) | `Datatype` (`integer`, `decimal`, `date_mdy`, …; unrecognised formats become `string`) |
| Field Annotation | `Notes` |
| Branching Logic | `Precondition` (when it fits the spec grammar) + prose in `Description` |
| Required Field? | `Required` |
| — (`--provenance` flag) | `Provenance` |

Rows with Field Type `descriptive` are display text, not fields, and are
skipped. A generated `Description` explains each field in prose: the prompt,
how many permissible values it has (and which are mutually exclusive, from
`@NONEOFTHEABOVE` annotations), and its **branching logic** — a REDCap
condition like `[smoker] = '1'` becomes *"This variable only records a
non-blank value if the value of `smoker` is `1`, \_"Yes"\_."*, with the
choice label looked up from the referenced field.

## Install

```
pipx install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=redcap"
```

(Or `pip` into an existing environment. Pulls in the sibling `dd-api`
package, which the converter builds its output on.)

## Use it

```
# REDCap export in, data dictionary CSV out
redcap-to-dd redcap_export.csv -o my_dictionary.csv --provenance "My Study"

# ...or to stdout
redcap-to-dd redcap_export.csv | less
```

From Python:

```python
from dd_redcap import convert_redcap

dd = convert_redcap("redcap_export.csv", provenance="My Study")  # a dd_api DataDictionary
dd.to_csv()      # the dictionary as CSV
dd.to_linkml()   # or go straight to a LinkML schema
```

Column headers are matched case-insensitively and common short forms are
accepted (`Variable`, `Label`, `Type`, `Choices`, …), so lightly hand-edited
exports convert too. A file with no recognisable `Variable / Field Name`
column is rejected with a clear error.

## Worked example

The repository carries two complete real-world runs of this tool (`up` and
`rad`; the latter needs `--allow-duplicates`, since multi-form exports repeat
shared fields). For instance the RADx-UP export [`up.redcap.csv`](../converter/examples/up.redcap.csv)
converts to [`up.dd.csv`](../converter/examples/up.dd.csv) (159 elements,
50 machine-readable preconditions from branching logic), whose LinkML
schema is [`up.yaml`](../converter/examples/up.yaml).

## How the conversion works

The algorithm — including how REDCap's **Field Type** drives row filtering,
cardinality, enumerations, and datatypes — is documented in
[`CONVERSION.md`](CONVERSION.md), with a verified worked example.

## Development

The design is recorded in [`REDCAP_PLAN.md`](REDCAP_PLAN.md). To run the
tests:

```
pip install -e "./redcap[test]"
pytest redcap
```
