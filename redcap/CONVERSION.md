# The Conversion Algorithm

How `redcap-to-dd` turns a REDCap data dictionary export into a data
dictionary in [this specification's format](../radx-data-dictionary-specification.md).
This is the authoritative description of the strategy; the code in
`dd_redcap/` follows it module by module.

## Pipeline

1. **Read the sheet** (`headers.py`). The CSV is parsed (UTF-8, BOM
   tolerated) and its columns are recognised by name — case-insensitively,
   with the common short forms accepted (`Variable / Field Name` /
   `Variable` / `Field Name`; `Field Label` / `Label` / `Prompt`;
   `Field Type` / `Type`; `Choices, Calculations, OR Slider Labels` /
   `Choices`; …). A file with no recognisable Variable column is rejected
   (`ConversionError`) — it is not a REDCap dictionary. Any *other* missing
   column is fine: its cells simply read as blank, because real exports are
   often trimmed by hand.
2. **Convert row by row** (`convert.py`). Each REDCap row becomes one
   `dd_api.DataElement`, except:
   - rows whose Field Type is `descriptive` — display text on the form, not
     a data field — are skipped;
   - rows with a blank Variable cell are skipped with a logged warning.
3. **Assemble and write.** The elements form a `dd_api.DataDictionary`
   (duplicate Variable names therefore fail loudly), and the output CSV is
   produced by `DataDictionary.to_csv()` — so it is canonical by
   construction and round-trips through every other tool in this repo.

## Per-column strategy

| Output column | Strategy |
| --- | --- |
| `Id` | The Variable / Field Name cell, verbatim. |
| `Label` | The Field Label; a non-blank Field Note is appended in parentheses — `Packs per day` + note `per day` → `Packs per day (per day)`. |
| `Section` | The Section Header, **carried forward**: REDCap writes a section name only on the first row of a section, so a blank cell means "same section as the previous row". |
| `Cardinality` | `multiple` when Field Type is `checkbox` (each choice is its own datafile column holding 0/1); otherwise `single` (radio, dropdown, text, …). |
| `Enumeration` | The Choices cell, parsed per the grammar below, one `"value"=[label]` pair per choice, order preserved. |
| `Datatype` | The decision tree below. |
| `Description` | Generated prose — see below. |
| `Notes` | The Field Annotation, split on `\|`; `@NONEOFTHEABOVE` actions are removed (they are *explained* in the description instead); the rest joined as paragraphs. |
| `Provenance` | The `--provenance` flag (or `provenance=` argument), the same for every element. |
| `Aliases`, `Terms`, `Pattern`, `Unit`, `MissingValueCodes`, `Examples`, `SeeAlso` | Left empty — REDCap has no counterpart. (Text Validation Min/Max are currently not carried; a future version could render them into `Pattern` or the description.) |

## How Field Type drives the conversion

Field Type is the pivot of the whole conversion: it decides whether a row is
a data field at all, how many values a datafile cell holds, and where the
datatype comes from. Type by type:

| Field Type | Row kept? | Cardinality | Enumeration | Datatype comes from |
| --- | --- | --- | --- | --- |
| `descriptive` | **No** — display text on the form, not a field. | — | — | — |
| `radio` | Yes | `single` | from Choices | the choice values (`integer` if the first is all digits, else `string`) |
| `dropdown` | Yes | `single` | from Choices | the choice values, as above |
| `checkbox` | Yes | **`multiple`** — each choice is its own 0/1 column in the datafile | from Choices | the choice values, as above |
| `text` | Yes | `single` | none | the Text Validation Type, via the datatype table below (plus the `MM/DD/YYYY` field-note idiom) |
| `notes` | Yes | `single` | none | no validation → `string` |
| `calc` | Yes | `single` | none | no validation → `string` (the calculation expression is not interpreted) |
| `yesno`, `truefalse` | Yes | `single` | **none** — REDCap implies 0/1 choices without a Choices cell, and the converter does not synthesise them (a known gap; see below) | `string` |
| `slider`, `file`, anything else | Yes | `single` | none (unless a Choices cell is present) | validation if present, else `string` |

Three things to notice about the interplay:

- **Choices beat validation.** When a row has a Choices cell, the datatype
  is derived from the choice *values*, and any Text Validation Type is
  ignored — an enumerated field's type is the type of its codes.
- **Cardinality is purely a Field Type fact.** Only `checkbox` produces
  `multiple`; a radio and a dropdown enumerate the same way but stay
  `single`. Nothing else (choices, validation) affects cardinality.
- **Only `descriptive` removes a row.** Every other type converts —
  unrecognised types deliberately degrade to a `single` `string` field
  rather than being dropped, so no data element silently disappears.

Known gap, inherited from the Java original: `yesno` / `truefalse` fields
carry their 0/1 (true/false) choice lists implicitly, with no Choices cell,
so they currently convert as plain `string` fields with no enumeration. A
future version could synthesise `"0"=[No] | "1"=[Yes]` (and
`"0"=[False] | "1"=[True]`) for them.

## The choices grammar

A Choices cell lists `value, label` pairs separated by `|` — or by `;` in
older exports, used only when the cell contains no pipe at all:

```
1, Yes | 2, No | 3, Maybe
```

Only the **first** comma of each item splits value from label, so labels
keep their own commas (`1, Less than $15,000`). An item with no comma is its
own label. Values and labels are trimmed; order is preserved.

## The datatype decision tree

1. **The field has choices** → the datatype of its *values*: `integer` when
   the first choice value is all digits, else `string`.
2. **No choices, blank validation** → `string`.
3. **Validation `text` with Field Note `MM/DD/YYYY`** → `date_mdy` (a REDCap
   idiom for US-format dates).
4. **Otherwise** the validation name is looked up in one explicit table
   (`datatypes.py`): `integer` → `integer`; `number`, `number_1dp..4dp` →
   `decimal`; `date_ymd` → `date` (Y-M-D is the XSD lexical form);
   `date_mdy` / `datetime_seconds_mdy` → `date_mdy`; `date_dmy` /
   `datetime_seconds_dmy` → `date_dmy`; `datetime_seconds_ymd` → `dateTime`;
   `time`, `time_hh_mm_ss` → `time`. Anything else (emails, phone numbers,
   zip codes, institutional id formats, partial dates like `date_my`) →
   `string` — never silently something stricter than the data warrants.

A test asserts every name the table maps to is a valid spec datatype.

## The generated description

Up to three paragraphs, blank ones omitted:

1. **The prompt** — `` The `{id}` variable records response to the prompt,
   _"{label}"_. ``
2. **The permissible values** (enumerated fields only) — "Values for this
   variable are {datatype}s that are restricted to the list of {n}
   permissible {datatype} values." If the Field Annotation carries a
   `@NONEOFTHEABOVE = '98,99'` action, a sentence names those values as
   mutually exclusive with all others.
3. **The branching logic.** A REDCap field with branching logic is only
   shown — and so only filled in — when a condition on other fields holds;
   datafile readers otherwise see it as mysteriously blank. Three condition
   shapes are recognised per clause (clauses split on ` and `):
   `[field(3)] = '1'` (one checkbox choice ticked), `[field] = '2'` (a value
   test), and `[field] <> ''` (non-blank). Each becomes "the value of
   `field` is `choice`", and the *meaning* of the choice is resolved by
   looking up the referenced field's own choice list — so `[smoker] = '1'`
   renders with `_"Yes"_`. A clause matching none of the shapes is quoted
   verbatim: "the condition `[bmi] > 30` evaluates to true".

## Worked example

Input (two REDCap rows):

```csv
Variable / Field Name,Section Header,Field Type,Field Label,"Choices, Calculations, OR Slider Labels",Field Note,Text Validation Type OR Show Slider Number,Branching Logic (Show field only if...),Field Annotation
smoker,Lifestyle,radio,Do you smoke?,"0, No | 1, Yes",,,,
packs,,text,Packs per day,,per day,number,[smoker] = '1',@HIDDEN
```

The converted `packs` element (converted with `--provenance "Demo Study"`):

| Column | Value |
| --- | --- |
| `Id` | `packs` |
| `Label` | `Packs per day (per day)` |
| `Section` | `Lifestyle` *(carried forward)* |
| `Datatype` | `decimal` *(validation `number`)* |
| `Cardinality` | `single` |
| `Notes` | `@HIDDEN` |
| `Provenance` | `Demo Study` |

and its generated description:

> The `packs` variable records response to the prompt, _"Packs per day (per
> day)"_.
>
> This variable only records a non-blank value if the value of `smoker` is
> `1`, _"Yes"_.

(This example is real output — reproduced from a run of the converter.)

## Departures from the Java original

Recorded in [`REDCAP_PLAN.md`](REDCAP_PLAN.md): the datatype table implements
the Java's evident intent rather than its dead-code accident; a grammar slip
in the values sentence is fixed; output is the full canonical column set via
`dd_api` (the Java omitted Aliases/Examples); rows with a blank Variable cell
are skipped with a warning rather than producing an empty-id record.
