# Data Dictionary Validator

`dd-validate` checks a data dictionary **CSV** against the
[specification](../radx-data-dictionary-specification.md) and reports every
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
| Id whitespace | INFO | An `Id` contains a space. |
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

# Machine-readable output
dd-validate my_dictionary.csv -f json -o report.json
```

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
