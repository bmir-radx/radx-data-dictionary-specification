# Data Dictionary → LinkML Schema Converter — Design

> **Status:** Implemented in [`../converter/`](../converter/) as the
> `dd-to-linkml` tool. This document is the design record: it explains what
> the converter does and why the mapping decisions were made. Where the code and
> this document ever disagree, the code (and its tests) is authoritative.

## Goal

The converter reads a data dictionary in CSV format and emits a **LinkML
schema** describing the *target datafile* that the dictionary documents. Each
data element (row) becomes a **slot**; the datafile as a whole becomes a
**class** (default name `Record`).

This is *metamodeling*: the dictionary is metadata about a datafile, and the
output schema is a formal description of that datafile's structure, suitable for
validating the datafile with standard LinkML tooling — subject to the
multi-value delimiter caveat noted under "Future work" (bare `|` vs.
LinkML's bracketed `[ | ]`).

> Not in scope for v1 (but the parser core is shared with it): converting a data
> *dictionary* CSV into LinkML *data instances* of the parsed object model
> (`data-dictionary.yaml`). See "Future work".

## Inputs and outputs

- **Input:** one data dictionary CSV file (RFC 4180), with the header record and
  columns defined in `radx-data-dictionary-specification.md`.
- **Output:** one LinkML schema YAML file describing the target datafile.
- **CLI:** `dd-to-linkml INPUT.csv -o SCHEMA.yaml [--name ... --id ...]`

## Core mapping: dictionary row → LinkML slot

| Dictionary column | LinkML target | Notes |
|---|---|---|
| `Id` | slot name | Sanitized for LinkML; original kept as `slot_uri`/annotation if changed |
| `Aliases` | `aliases:` | Native LinkML slot metadata |
| `Label` | `title:` | |
| `Description` | `description:` | |
| `Section` | declared `subset` + slot `in_subset:` | See "Section grouping"; annotation only as fallback |
| `Cardinality` | `multivalued: true` | Only when value is `multiple`; else single-valued |
| `Terms` | `related_mappings:` (all terms) | Subject-matter annotations, not the slot's predicate URI; CURIE prefixes registered in output |
| `Datatype` | `range:` | Via the datatype map below |
| `Pattern` | `pattern:` | Emitted verbatim (XSD-regex dialect) |
| `Unit` | native `unit:` (UnitOfMeasure), lookup-assisted | See "Unit mapping"; `annotations.unit_raw` always kept |
| `Enumeration` | generated `enum` + slot `any_of` | Range via `any_of` (see Enumeration handling) |
| `MissingValueCodes` | shared/`per-field` enum in slot `any_of` | Augments the enum (see below) |
| `Examples` | `examples:` | Native LinkML slot metadata (list of `{value:}`) |
| `Notes` | `comments:` | |
| `Provenance` | slot `source:` if URL/CURIE, else `annotations.provenance` | See "Provenance vs. source" |
| `SeeAlso` | `see_also:` | Native |

**Losslessness (decided):** every column that has no clean native LinkML home is
preserved under `annotations:` so the conversion loses nothing and could be
reversed.

### Provenance vs. source (two different levels)

These are easy to conflate but operate at different levels:

- **Schema-level `source:`** — metadata about the *output schema as a whole*.
  Set once, to the authoritative prose specification / repository it was derived
  from (as in `data-dictionary.yaml`: the GitHub repo). Not per-field.
- **`Provenance`** — a *per-field* dictionary column: where the *definition*
  of that field came from (typically a Common Data Element it is based on). Per
  the spec its value is *ideally* a URL to a CDE repository, but *may* also be a
  free-text unambiguous CDE name.

Mapping (decided): map `Provenance` onto the slot's native LinkML **`source:`**
when the value is a URL/CURIE — LinkML `source` ("where this element came from")
is a close semantic match. When the value is free text (a CDE name), `source:`
would fail its `uriorcurie` typing, so fall back to `annotations.provenance`.
Either way nothing is lost. The schema-level `source:` (whole-file lineage)
is set independently and is unaffected by this per-field mapping.

### Unit mapping (decided: native `unit:`, lookup-assisted)

`Unit` is a single **free-text** string (the spec provides no controlled
list) — e.g. `mm`, `mg/dL`, `degrees Celsius`. LinkML has a native `unit:` slot
whose range is `UnitOfMeasure`, with fields: `symbol`, `abbreviation`,
`descriptive_name`, `exact_mappings`, `ucum_code`, `derivation`,
`has_quantity_kind`, `iec61360code`. (Verified in LinkML 1.11: a populated
`unit:` block compiles and survives materialization with all sub-fields intact.)

Mapping (decided — lookup-assisted):

- The converter carries a small built-in unit table seeded from the spec's own
  "common units" example table (23 rows: `millimeter`/`mm`/length …
  `moles per liter`/`mol/L`/concentration). Each entry maps a unit **name or
  symbol** → `{descriptive_name, symbol, ucum_code?}`.
- If the `Unit` value matches the table (by name **or** symbol), emit a
  populated `unit:` block (`descriptive_name` + `symbol`, plus `ucum_code` where
  known).
- If it does **not** match, emit `unit: {symbol: <raw string>}` — `symbol` is the
  fallback field, since unit values are most often short symbols.
- **In all cases**, also preserve the original cell verbatim as
  `annotations.unit_raw` so the un-normalized string is always recoverable and
  the mapping is lossless (a table match must never silently discard the raw
  input).

Deliberately **not** doing UCUM validation / QUDT `has_quantity_kind` resolution
in v1: units are free-text and many will not be valid UCUM, so requiring a
UCUM library would reject legitimate data. `ucum_code` is populated only for the
table-known units. This can be revisited later.

### Section grouping (decided: `in_subset` + declared `subsets:`)

`Section` is the one field about *relationships between rows* rather than a
single row: multiple data elements share a section name (e.g. `Demographics`),
so it is a grouping of fields. Mapping (decided):

- Collect the distinct `Section` values across the dictionary and emit one
  entry per section in the schema's `subsets:` block (section name → subset,
  with the name as its `description`).
- On each slot, set `in_subset: [<its section>]`.
- Fall back to `annotations.section` only when a section name cannot be
  sanitized into a valid subset name, so the mapping stays lossless.

`in_subset` was chosen over `slot_group` because it directly models what
`Section` is — a flat label tagging each field with the group it belongs to —
and needs no `slot_usage` scaffolding. (`slot_group` was also verified to work
in LinkML 1.11 and could be added later for form/section-header rendering
tools, but is not needed for the core grouping semantics.) Both `in_subset` and
the `subsets:` declarations were verified to survive schema materialization
(`SchemaView` resolves `in_subset` on induced slots and lists the subsets).

## Datatype mapping (decided: emit custom LinkML types)

Direct built-in mappings (datatype name → LinkML built-in range):

| Datatype name | LinkML built-in |
|---|---|
| `string`, `normalizedString`, `token`, `Name`, `NCName`, `language`, `NMTOKEN`, `QName`, etc. | `string` |
| `integer`, `int`, `short`, `byte`, `long`, `nonNegativeInteger`, `positiveInteger`, `unsignedInt`, ... | `integer` |
| `decimal` | `decimal` |
| `float` | `float` |
| `double` | `double` |
| `boolean` | `boolean` |
| `date` | `date` |
| `dateTime` | `datetime` |
| `time` | `time` |
| `anyURI` | `uri` |

Types with **no** LinkML built-in → the converter emits a **custom `type`** into
the output schema's `types:` block, so the schema is self-contained:

| Datatype name | Emitted custom type |
|---|---|
| `date_mdy` | `typeof: date`, `pattern: '^\d{2}/\d{2}/\d{4}$'` (US mm/dd/yyyy) |
| `date_dmy` | `typeof: date`, `pattern: '^\d{2}/\d{2}/\d{4}$'` (intl dd/mm/yyyy) |
| `timestamp` | `typeof: integer`, `pattern: '^[0-9]+$'` (Unix long) |
| `gYearMonth`, `gYear`, `gMonthDay`, `gDay`, `gMonth` | `typeof: string` + XSD `pattern`, `uri: xsd:<name>` |
| `duration`, `hexBinary`, `base64Binary`, `NOTATION`, ID/IDREF(S)/ENTITY(IES) | `typeof: string`, `uri: xsd:<name>` |

Every emitted custom type carries `uri: xsd:<name>` so the
provenance of the type is explicit. Only the custom types *actually used* by the
input are emitted.

**Case sensitivity:** datatype names are case-sensitive per the spec; the map
keys are exact. An unknown/mis-cased datatype is a hard error (see errors).

## Enumeration handling

- Each non-blank `Enumeration` cell → a named `enum` in the output schema.
- Enum name: `{SanitizedSlotId}Enum` (collision-checked; deduped if two slots
  carry an identical enumeration → shared enum).
- Each value-label pair → a `permissible_value`:
  - key = the (unquoted) value,
  - `description` = the label,
  - `meaning:` = the term IRI/CURIE if present (`(UBERON:...)`).
- **`Datatype` + `Enumeration` interaction:** when both are present, the
  enumeration is the controlling set of values; the underlying `Datatype` is
  preserved as `annotations.value_datatype` so the value type is not lost.

### Missing-value codes augment the enum (Option 3: slot-level `any_of`)

Missing-value codes and enumerations are the same value=label shape, and the
standard missing-value codes are a shared set repeated across every enumerated
field. To avoid repeating ~25 codes in every enum while still permitting them as
values, the converter models the slot's range as a **union** of the field enum
and a **shared** missing-value-codes enum:

```yaml
slots:
  SampleType:
    any_of:
      - range: SampleTypeEnum            # the field's own values
      - range: StandardMissingValueCodes # shared; defined once per schema
```

- The converter emits **one** `StandardMissingValueCodes` enum per output schema
  (the 25 default codes from the spec) and references it by name from every
  enumerated field's `any_of`. No repetition.
- If a field's row carries its **own** non-blank `MissingValueCodes` cell, the
  converter emits a field-specific `{SanitizedSlotId}MissingValueCodes` enum and
  adds it as a **third** `any_of` branch. This realizes the spec's "augment, not
  replace" rule: field-specific codes are added on top of the standard set.
- A datafile value is valid iff it is a member of the field enum **or** the
  standard codes **or** (if present) the field-specific codes.

**Why not enum `inherits:` / `mixins:`?** The natural-looking approach — have
each field enum `inherits:` from `StandardMissingValueCodes` — was tested
against LinkML 1.11 and **does not work**: `inherits:` parses but the inherited
permissible values are not merged by `gen-json-schema`, by `gen-linkml`
derivation, or by `SchemaView.induced_enum`/`enum_ancestors` (all return only
the field's own values). Slot-level `any_of` with two enum ranges was verified
to enforce correctly: a real value passes, a standard code passes (augment), and
an out-of-set value is rejected ("not valid under any of the given schemas").
This is why Option 3 (union at the slot) is used rather than enum inheritance.

## Architecture

```
dd_converter/
  reader.py        # RFC-4180 CSV -> list[Row]; validates required headers, ordering
  grammar/
    enumeration.lark   # EBNF from spec section "Semantics of Enumeration Values"
    parse.py           # cell string -> [EnumItem(value,label,iri?)]; also MissingValueCodes
    terms.py           # split Terms cell -> [iri|curie] (ws / NBSP / newline)
  datatypes.py     # datatype name -> LinkML range | CustomTypeSpec
  missing_values.py # the 25 standard missing-value codes (constant) -> StandardMissingValueCodes enum
  units.py         # built-in unit table (from the spec) -> UnitOfMeasure lookup by name/symbol
  emit.py          # rows + parsed cells -> linkml_runtime SchemaDefinition -> YAML
                   #   emits shared StandardMissingValueCodes enum once; wires
                   #   enumerated slots as any_of [field enum, standard codes, (field codes)]
  cli.py           # argparse entry point
tests/
  fixtures/        # small CSVs incl. the spec's own worked examples
  test_reader.py test_parse.py test_terms.py test_datatypes.py
  test_tables.py test_emit.py test_cli.py
```

The emitter also post-processes its YAML for readability (literal `|` blocks for
multi-line text, section-header comments, blank lines between entries, redundant
`name:`/`text:` keys dropped, `annotations` last); a round-trip test asserts this
never alters the schema content.

**Two layers, cleanly separated:**
1. **Parser layer** (`grammar/`) — turns cell mini-grammars into Python objects.
   Driven by the EBNF already in the spec (Lark). *Reused verbatim if we later
   add data-instance output.*
2. **Emitter layer** (`emit.py`) — builds a `SchemaDefinition` using
   `linkml_runtime` and dumps it. Building the object model (not string
   templating) means the output is guaranteed well-formed and we can
   `linkml-lint` it in tests.

## Error handling

- Missing required header (`Id`, `Label`, `Datatype`) → fail fast, name the column.
- Unknown / mis-cased datatype name → error listing the offending value + row.
- Malformed `Enumeration` / `MissingValueCodes` cell → parser error with the
  cell content and row index.
- Duplicate `Id` → error naming both lines. (Alias-vs-Id/alias uniqueness across
  the whole dictionary is specified but not yet enforced by the reader; noted as
  future work.)
- Non-OBO CURIE prefix in `Terms`/enum `meaning` → the prefix is registered with
  a best-effort OBO expansion and a warning is logged (shown with `--verbose`),
  rather than failing.

## Validation strategy

- Unit-test each layer against the spec's own examples (`"0"=[Saliva] | ...`,
  the standard MissingValueCodes set, `^[NP](\d+)$`, etc.).
- End-to-end: convert a fixture CSV, then run `linkml-lint` on the *output*
  schema in-test and assert 0 errors — the converter must always emit a valid
  schema.

## Resolved decisions

1. **Prefixes for `Terms`/`meaning` CURIEs (decided).** Emit compact ids
   (`UBERON:0001836`) **as-is** and register their prefixes in the output
   schema's `prefixes:` block, rather than expanding to full IRIs. OBO Foundry
   prefixes are auto-registered using the deterministic OBO rule
   (`IDSPACE:LOCALID` → `http://purl.obolibrary.org/obo/IDSPACE_LOCALID`), so any
   `IDSPACE:` prefix seen in the input maps to
   `http://purl.obolibrary.org/obo/IDSPACE_`. Full IRIs are emitted unchanged. A
   non-OBO CURIE whose prefix cannot be resolved is kept as-is and a warning is
   logged (its prefix is left for the user to declare).

2. **Schema `id` / `name` / root class name (decided).** Taken from CLI flags
   (`--id`, `--name`, `--class-name`); when a flag is omitted, derived from the
   input CSV filename (e.g. `patient_data.csv` → name `patient_data`, id under a
   default base, class `PatientData`). The default root class name, when nothing
   else is given, is **`Record`**. No dictionary metadata row is assumed (these
   dictionaries have no standard metadata row).

3. **Packaging (decided).** An installable Python package living in this
   repository under [`converter/`](../converter/), exposing the
   `dd-to-linkml` console script.

## Future work (not v1)

Two distinct CSVs must not be confused here:

- a **data dictionary CSV** — the metadata; rows are data elements
  (Id, Label, Datatype, ...);
- a **datafile CSV** — the actual study data; rows are participant records
  (`N001`, `67`, ...). The dictionary *describes* this file's columns.

Future items:

- **Data dictionary CSV → DataElement instances** (instances of
  `data-dictionary.yaml`, the parsed object model). This is a genuine project: it
  reuses the `grammar/` parser layer to turn the in-cell mini-grammars
  (`Enumeration`, `Terms`, `MissingValueCodes`) into nested objects — the one
  piece LinkML tooling cannot provide.
- **Datafile CSV → data instances of the generated schema.** This is *almost*
  free with stock `linkml-convert`, but **not entirely**: multi-valued
  cells use a **bare** pipe (`cough|headache`) whereas LinkML's CSV convention
  is a **bracketed** pipe (`[cough|headache]`), and LinkML's CSV reader does not
  split a bare-pipe (or space-separated) cell at all (see the tested note
  below). So this needs a small **delimiter-normalization** pre-processing step
  (rewrite bare-pipe cells to `[a|b|c]`, or a custom loader) before
  `linkml-convert` can be used. It is not a no-op.
- Reverse direction: LinkML schema → data dictionary CSV.
- **Alias uniqueness enforcement.** The reader rejects a duplicate `Id`, but does
  not yet check that an `Alias` never collides with another record's `Id` or
  alias (the spec's cross-dictionary uniqueness rule).

## Tested note: LinkML in-cell multi-value behavior (LinkML 1.11)

Verified empirically with `linkml-convert` on this machine:

- **Reading CSV → instances:** for a `multivalued: true` slot, a cell containing
  `cough|sorethroat|headache` is loaded as a **single-element list holding the
  whole string** `"cough|sorethroat|headache"` — LinkML does **not** split on
  `|`. A space-separated cell (`cough sorethroat headache`) is likewise not
  split. There is no built-in "split this cell on a delimiter" for arbitrary
  input.
- **Writing instances → CSV:** a multivalued slot with values `[cough, headache]`
  is emitted as `[cough|headache]` — pipe-separated **and wrapped in square
  brackets**.

Consequence: A bare-pipe dictionary (bare `|`) and LinkML (bracketed `[ | ]`) multi-value cell
conventions are **not interchangeable**, even though both use the pipe
character. Any datafile round-trip through stock LinkML tooling must normalize
the delimiter first, or the values are silently mis-read as one string.
