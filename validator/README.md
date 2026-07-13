# Data Dictionary Validator

`dd-validate` checks a data dictionary **CSV** against the
[specification](../SPECIFICATION.md) and reports every
violation it finds. It does not transform the dictionary — it tells you what is
wrong, at which line, and how severe it is.

Each finding has a severity:

- **ERROR** — makes the dictionary invalid (a MUST in the specification).
- **WARNING** — a SHOULD; the dictionary is still valid but could be improved.
- **INFO** — an optional improvement.

## What it checks

| Check | Severity | Flags |
| --- | --- | --- |
| Required headers | ERROR | A required column (`Id`, `Label`, `Datatype`) is missing. |
| Id present | ERROR | An `Id` cell is blank. |
| Id leading whitespace | ERROR | An `Id` starts with a space. |
| Id characters | INFO | An `Id` contains spaces or special characters — legal, but schema renderings rename it and preconditions can't reference it (suggests the schema-safe spelling). |
| Cell whitespace | WARNING | A cell has leading or trailing whitespace (suggests the stripped value). |
| Label present | WARNING | A `Label` cell is blank. |
| Datatype present | ERROR | A `Datatype` cell is blank. |
| Unknown datatype | ERROR | A `Datatype` name is not recognised (suggests a fix). |
| Cardinality | ERROR | A `Cardinality` value is not `single` or `multiple`. |
| Pattern | ERROR | A `Pattern` is not a valid regular expression. |
| Enumeration | ERROR | An `Enumeration` cell does not parse. |
| Missing value codes | ERROR | A `MissingValueCodes` cell does not parse. |
| SeeAlso URL | ERROR | A `SeeAlso` value is not an absolute URL. |
| Duplicate Id | ERROR | An `Id` appears on more than one row. |
| Precondition | ERROR | A `Precondition` cell does not parse, references an unknown field, orders an unordered datatype, or uses `contains` on a single-valued field. |
| Required | ERROR | A `Required` value is not `y` or blank. |
| Preferred datatype | INFO | A `Datatype` names a storage width (`int`, `short`, `token`) — a free rename to the semantic builtin (suggests it). |
| Format harmonization | INFO | A REDCap-style format (`date_mdy`, `date_dmy`, `timestamp`) — valid as-is; records the harmonized target (`date`/`dateTime`) for pipelines that migrate the datafile too. |
| Missing unit | INFO | A numeric, non-enumerated field has no `Unit` (counts and scores are legitimately unitless — see `--ignore`). |
| Enumeration datatype | INFO | Every enumeration value is an integer but the `Datatype` is not (suggests `integer`). |
| Alias / Id collision | WARNING | An alias equals an element `Id`, or is claimed by two elements — either breaks datafile-header keying. |
| Empty list segment | WARNING | A pipe-delimited cell (`Aliases`, `Examples`) has an empty segment from a doubled or trailing pipe (suggests the cleaned cell). |
| Examples conform | WARNING | An example is not in the field's enumeration, does not match its pattern, or does not fit its datatype (the specification's SHOULD, checked). |
| Enumeration consistency | ERROR / INFO / WARNING | A value listed twice (ERROR); two values sharing a label (INFO); a value that is also a missing-value code — the field's or a standard one (WARNING); a value the field's own pattern rejects (WARNING). |
| Precondition values | WARNING | A compared value is not in the referenced field's enumeration, or does not fit its datatype. |
| Unit suggestion | INFO | A `Unit` written informally (`years`, `per year`, `mcg/ml`, `kg/m²`) gets its UCUM code as the suggestion, via `dd_core.ucum`. |
| Unit on non-quantity | INFO | A `Unit` on a boolean / URI / temporal field. |
| Boolean with enumeration | INFO | A boolean field also declares an enumeration — two representations of one thing. |
| Label quality | INFO | A label that just repeats the `Id`; the same label on more than one element. |
| Description present | INFO | A blank `Description` cell (only when the column exists). |
| Fragmented sections | INFO | A `Section` that stops and later resumes — its elements are split into non-contiguous runs. |

The datatype names, the enumeration grammar, and the missing-value-codes grammar
are reused from the sibling [converter](../converter/), so the validator stays in
lockstep with the converter and the specification. A check whose column is not in
the header does nothing — an absent *optional* column is not a problem.

## Install

For a command-line tool, [`pipx`](https://pipx.pypa.io) is the recommended way to
install it — it puts `dd-validate` on your `PATH` in its own isolated
environment:

```
pipx install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=validator"
```

On first use of pipx, its bin directory may not be on your `PATH` (pipx warns if
so). Run `pipx ensurepath` once — then open a new terminal — to add it.

The validator depends on the converter package (for its parsers); the command
above pulls it in automatically. To install into an existing environment instead
of an isolated one, use `pip` in place of `pipx`.

## Use it

```
# Validate a dictionary; findings print to stdout, one per line
dd-validate my_dictionary.csv

# Validate every CSV in a directory
dd-validate ./dictionaries/

# Only show errors, ignoring warnings and info
dd-validate my_dictionary.csv --levels ERROR

# Drop specific advisory checks a pipeline disagrees with
dd-validate my_dictionary.csv --ignore missing-unit datatype-preferred

# Machine-readable output
dd-validate my_dictionary.csv -f json -o report.json
```

Each finding carries a **format-independent address** alongside the CSV line
number: `elementIndex` (the element's 0-based position in document order,
stable across the CSV, dd-json, and LinkML renderings of the same dictionary)
and `elementId`. Checks with a mechanical fix also carry a `suggestion` (the
schema-safe Id spelling, the stripped cell value, the semantic datatype name).
Programmatic access without touching CSV text goes through the API:
`DataDictionary.validate()` in the sibling [`dd_api`](../api/) package.

Options:

| Option | Effect |
| --- | --- |
| `-o`, `--output` | Output file (default: stdout). |
| `-f`, `--format` | `text`, `csv`, `tsv`, or `json` (default: `text`). |
| `--levels` | Only report these levels, e.g. `--levels ERROR WARNING` (default: all). |
| `--no-duplicate-check` | Do not check for duplicate `Id`s. |
| `--exit-zero` | Always exit `0`, even when errors are found. |

## Exit codes

- `0` — no ERROR-level findings remain (after any `--levels` filter).
- `1` — at least one ERROR was found. Use this to gate a CI build.
- `2` — a usage error (input not found).

Pass `--exit-zero` to always exit `0` regardless of findings.

## Development

```
pip install -e "./validator[test]"
pytest validator
```
