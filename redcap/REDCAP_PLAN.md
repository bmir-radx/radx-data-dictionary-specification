# REDCap Converter — Plan

A Python tool that converts a **REDCap data dictionary** (the CSV that REDCap
exports) into a data dictionary in this repository's format. Ported from the
Java `redcap-data-dictionary-converter`; fifth tool in the repo.

Folder `redcap/`, package `dd_redcap`, command `redcap-to-dd`. Depends on
**`dd-api`**: the converter builds `DataElement` objects and lets
`DataDictionary.to_csv()` do the writing, so the output is canonical by
construction (the Java version hand-printed CSV and omitted the Aliases and
Examples columns; ours emits the full canonical column set).

## What the Java converter does (behaviour to port)

Per REDCap row, matched by header name (case-insensitive, with synonyms —
e.g. `Variable / Field Name` / `Variable` / `Field Name`):

- **Skip** rows whose Field Type is `descriptive` (display text, not a field).
- **Id** ← Variable / Field Name (error if the column is absent).
- **Label** ← Field Label, with a non-blank Field Note appended in parens:
  `Age (in years)`.
- **Section** ← Section Header, *carried forward* (REDCap does not fill
  section headers down; blank means "same as the previous row").
- **Cardinality** ← Field Type: `checkbox` → `multiple`; everything else
  (radio, dropdown, text, …) → `single`.
- **Enumeration** ← the Choices cell, parsed as `value, label` pairs
  separated by `|` (or `;` when no pipe is present); the first comma splits
  value from label, so labels keep their own commas (`1, Less than $15,000`);
  an item with no comma is its own label.
- **Datatype**: with choices → `integer` if the first choice value is all
  digits, else `string`; without → mapped from the Text Validation Type
  (see decision 1 below); special case: validation `text` with Field Note
  `MM/DD/YYYY` → `date_mdy`; default `string`.
- **Description** — generated prose:
  `` The `{id}` variable records response to the prompt, _"{label}"_. `` plus,
  for enumerated fields, a sentence about the number of permissible values
  (and which values are mutually exclusive, per `@NONEOFTHEABOVE` field
  annotations), plus a **branching-logic explanation**: expressions like
  `[smoker] = '1'`, `[symptoms(3)] = '1'`, `[age] <> ''` (joined by `and`)
  are rendered as `This variable only records a non-blank value if the value
  of `smoker` is `1`, _"Yes"_.` — looking the choice label up from the row it
  references. Unrecognised expressions fall back to quoting the condition.
- **Notes** ← Field Annotation, split on `|`, with `@NONEOFTHEABOVE` actions
  removed (they are explained in the description instead), rejoined as
  paragraphs.
- **Provenance** ← a caller-supplied string (CLI flag for us).
- Terms, Pattern, Unit, MissingValueCodes, Aliases, Examples, SeeAlso: empty.

## Decisions

1. **Datatype mapping (depart from the Java accident).** The Java source
   contains a rich validation-name table (`RedcapValidationType`: `number` →
   decimal, `email` → string, …) that is **dead code** — the live path only
   recognises the eight names `string, integer, decimal, date, date_mdy,
   date_dmy, date_ymd, time` and silently strings everything else, and the two
   disagree (`date_mdy` → `date` in the table, `date_mdy` live). The port
   implements the evident *intent* as one explicit table mapping REDCap
   validation names to **this spec's** datatype names:
   `integer` → `integer`; `number`, `number_1dp..4dp` → `decimal`;
   `date_ymd` → `date` (Y-M-D is the XSD lexical form); `date_mdy` /
   `datetime_seconds_mdy` → `date_mdy`; `date_dmy` / `datetime_seconds_dmy` →
   `date_dmy`; `datetime_seconds_ymd` → `dateTime`; `time`, `time_hh_mm_ss` →
   `time`; everything else (email, phone, zipcode, ids, …) → `string`.
   The table is data, easy to review and extend.
2. **Description prose**: same templates as the Java, with its grammar slip
   fixed ("are *that restricted* to" → "are restricted to").
3. **Fail-fast, like the toolkit.** A REDCap sheet without a recognisable
   Variable/Field-Name column raises a clear error. Everything else is
   best-effort (REDCap exports are messy; missing optional columns are fine).
4. **Round-trip check in tests**: the produced CSV must load with
   `DataDictionary.load` (guaranteed by construction, but asserted anyway).

## Layout

```
redcap/
  REDCAP_PLAN.md  README.md  pyproject.toml   (deps: dd-api)
  dd_redcap/
    __init__.py    (exports: convert_redcap, ConversionError)
    headers.py     (the REDCap column vocabulary + synonym lookup)
    choices.py     (parse_choices: the "1, Yes | 2, No" notation)
    datatypes.py   (validation-name -> spec datatype table)
    branching.py   (branching-logic explanation)
    convert.py     (row -> DataElement; convert_redcap -> DataDictionary)
    cli.py         (redcap-to-dd INPUT [-o OUT] [--provenance TEXT])
  tests/           (choices parser cases from the Java tests + converter,
                    branching, datatype, CLI, round-trip tests)
```

Conventions as established: Python >=3.9, `from __future__ import
annotations`, ruff (F,E,W,B,C4,UP,SIM,I @ 100), reStructuredText docstrings
with doctest examples where they teach, pytest.
