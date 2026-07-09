# Data Dictionary Validator — Plan

A Python tool that validates a data dictionary CSV against the specification and
**reports every problem it finds** (it does not transform). Third tool in this
repo, sibling to `converter/` and `printer/`. Ported from the Java validator at
`bmir-radx/radx-data-dictionary-validator`, but generic/de-branded from the
start and reusing the `dd_core` package for per-cell parsing.

Package: `dd_validator`. Command: `dd-validate`.

---

## 1. What the Java validator does (the thing we're porting)

The Java validator (package `edu.stanford.bmir.radx.datadictionary.lib`) is a set
of independent `*ValidatorComponent` beans, each producing typed `*Result`
violations. Its architecture is **collect-all, never fail-fast**: every check
runs against every row and appends problems to one list, which is then sorted
and written as a tabular report. Key properties we will preserve:

- Each per-field check looks up its column by header name; **if the column is
  absent it does nothing** (a missing optional column is not an error).
- Blank cells are skipped by per-field checks (except the required-field checks).
- **No cross-row checks** — no duplicate-Id detection, no uniqueness. Each row is
  validated independently. (This is a deliberate difference from the converter's
  reader, which *does* raise on duplicate Ids.)
- Datatype validation is **name-only**: it checks the datatype *name* is known;
  it never validates cell *values* against datatype regexes.
- Three severity levels: **ERROR, WARNING, INFO**.
- Report output is **tabular CSV or TSV only** (no JSON in the original).
- **Exit code is always 0** in the original — findings do not change it.

### Check inventory (Java component → severity → what it flags)

| # | Check | Column | Severity | Flags |
|---|-------|--------|----------|-------|
| 1 | Required headers | header row | ERROR | A required column header is absent. Suggests a rename if a header matches case-insensitively. |
| 2 | Id present | `Id` | ERROR | Row too short or Id blank. |
| 3 | Id starts with whitespace | `Id` | ERROR | Id begins with an ASCII space. |
| 4 | Id contains whitespace | `Id` | **INFO** | Id contains an ASCII space anywhere. (Both #3 and #4 can fire on the same cell.) |
| 5 | Label present | `Label` | **WARNING** | Label blank ("strongly recommended"). |
| 6 | Datatype present | `Datatype` | ERROR | Datatype blank. |
| 7 | Unknown datatype name | `Datatype` | ERROR | Name not in the datatype set. Emits a "Did you mean …?" suggestion. |
| 8 | Invalid cardinality | `Cardinality` | ERROR | Value not exactly `single` or `multiple`. |
| 9 | Malformed pattern | `Pattern` | ERROR | Value is not a compilable regex; reports description + index. |
| 10 | Malformed enumeration | `Enumeration` | ERROR | Value fails the enumeration grammar. |
| 11 | Malformed missing value codes | `MissingValueCodes` | ERROR | Value fails the **same** enumeration grammar. |
| 12 | Malformed SeeAlso URL | `SeeAlso` | ERROR | Value is not an absolute URI. |

There is **no Unit/UCUM check** in the Java tool (only a TODO).

---

## 2. Decisions for the Python port

Most of these mirror the Java tool. Where I depart from it, it's flagged
**[DEPART]** with a reason, and the open ones are in §7 for you to confirm.

### 2a. Reuse vs. reimplement

We reuse `dd_core`'s per-cell parsers — they already encode this repo's
grammar and datatype set, so the validator stays in lockstep with the converter
and spec instead of duplicating rules:

- **Datatype name** → `resolve_datatype(name)`; catch `UnknownDatatypeError`.
  This is name-membership (+ the custom-type resolution), matching the Java
  name-only semantics. We do **not** validate cell values against regexes.
- **Enumeration** → `grammar.parse_enumeration(cell)`; catch `ParseError`.
- **MissingValueCodes** → `grammar.parse_missing_value_codes(cell)`; catch
  `ParseError`. (In this repo these are separate functions; the Java tool shared
  one grammar. Same effect.)
- **Column vocabulary** → `dd_core.KNOWN_COLUMNS` and `REQUIRED_COLUMNS`
  (`Id, Label, Datatype`). This resolves the Java source's header-vocabulary
  split (its `columns.csv` used `Meaning`/`Units` while the field components used
  `Unit`/etc.) — we use the **single** canonical vocabulary from the spec.

We do **not** reuse `read_data_dictionary`: it is fail-fast (raises on the first
duplicate/blank/bad header) and a validator must collect all problems. Instead
the validator reads the CSV at the raw level with the stdlib `csv` module —
exactly as `reader._read` does — and runs the checks itself. So the reader's
duplicate/blank *checks* are re-expressed here as collect-all findings, not
reused as raising code.

### 2b. Datatype suggestions

Port the Java "Did you mean …?" suggestion: case-insensitive exact match against
the known names, else a small fix map (`bit→boolean, text→string,
number→decimal, email→string, zipcode→string, phone→string`). This lives in the
validator (no `dd_core` equivalent). Message includes the suggestion only
when one is found.

### 2c. Pattern check

Compile with Python `re.compile`; catch `re.error`, report its message and
`.pos` when available. **[DEPART]** Python regex error text/positions differ from
Java's `PatternSyntaxException` — we do not attempt byte-for-byte parity, since
the spec says patterns are XSD regexes and neither engine is the XSD engine; a
"pattern does not compile" signal is what matters.

### 2d. SeeAlso check

Parse with `urllib.parse.urlsplit`; flag as malformed if it has no scheme
(not absolute). Matches the Java "not absolute" semantics.

### 2e. Whitespace-in-Id checks

Reproduce faithfully: `startswith(" ")` → ERROR; `" " in id` → INFO; both may
fire. ASCII space only (not tab), matching the original.

### 2f. Severity model

Three levels: `ERROR`, `WARNING`, `INFO` (an `enum.Enum`, ordered for sorting).
Level is a constant per check, assigned as in the table in §1.

### 2g. Cross-row checks — **[DEPART, opt-in]**

The Java tool has none. But this repo's spec and converter treat duplicate Ids as
an error, and duplicate detection is genuinely useful. Plan: implement a
**duplicate-Id** check as an ERROR, but keep the port faithful by default is a
judgment call — see §7 Q1. (Alias uniqueness and referential checks: out of
scope for v1.)

---

## 3. Module layout

```
validator/
  VALIDATOR_PLAN.md          (this file)
  README.md
  pyproject.toml             (name=dd-validate? see §5; console script dd-validate)
  dd_validator/
    __init__.py              (public API: Finding, Level, validate, __all__)
    model.py                 (Level enum, Finding dataclass)
    checks.py                (the individual check functions)
    validate.py              (orchestrator: read CSV rows, run all checks, collect)
    report.py                (render findings: text, csv, tsv, json)
    cli.py                   (dd-validate CLI)
  tests/
    test_checks.py
    test_validate.py
    test_report.py
    test_cli.py
    fixtures/...
```

### `model.py`
- `class Level(enum.Enum)`: `ERROR`, `WARNING`, `INFO` (with an int order for sort).
- `@dataclass(frozen=True) class Finding`: `level: Level`, `check: str` (short
  name, e.g. `"unknown-datatype"`), `message: str`, `line: int | None`
  (1-based source line; `None` for whole-file/header findings), `column: str |
  None`, `value: str | None` (offending cell). A `.sort_key` on
  `(line or 0, level.order, check)`.

### `checks.py`
Each check is a function `(rows, header, columns_present) -> Iterable[Finding]`
or a per-row helper. Named checks: `check_required_headers`, `check_id`,
`check_label`, `check_datatype`, `check_cardinality`, `check_pattern`,
`check_enumeration`, `check_missing_value_codes`, `check_see_also`, and
(opt-in) `check_duplicate_ids`.

### `validate.py`
- `read_rows(source) -> tuple[list[str], list[RawRow]]` — raw CSV read (stdlib
  `csv`, `utf-8-sig`, BOM strip), no raising on data problems. Mirrors
  `reader._read` structure but collects nothing / raises only on truly
  unreadable input (empty file → a single ERROR finding, not an exception).
- `validate(source, *, levels=None, include_duplicate_check=...) -> list[Finding]`
  — run every check, concatenate, sort. This is the public entry point.

### `report.py`
- `render(findings, fmt) -> str` for `fmt in {"text", "csv", "tsv", "json"}`.
- **text** (default): human-friendly, `path:line: LEVEL check — message`.
- **csv/tsv**: columns `File, Row, Level, Check, Message, Value`. **[DEPART]** We
  fix the Java writer's 7-header/6-field mismatch (it printed a `Directory`
  header with no data field) — our header and rows agree.
- **json**: a list of finding objects (the Java tool had no JSON; added because
  every other tool in this repo emits JSON and it's the machine-readable path).

### `cli.py`
`dd-validate INPUT [-o OUTPUT] [--format text|csv|tsv|json] [--levels ...]
[--exit-nonzero-on-error]`. INPUT may be a file or a directory (walk `*.csv`,
like the Java `--in`). See §6 for exit-code decision.

---

## 4. Reuse summary (what comes from `dd_core`)

| Need | Source | Behavior |
|------|--------|----------|
| Column vocabulary | `KNOWN_COLUMNS`, `REQUIRED_COLUMNS` | canonical spec columns |
| Datatype name check | `resolve_datatype` / `UnknownDatatypeError` | name-only membership |
| Enumeration grammar | `grammar.parse_enumeration` / `ParseError` | catch per cell |
| Missing value codes grammar | `grammar.parse_missing_value_codes` / `ParseError` | catch per cell |
| CSV read shape | (pattern from) `reader._read` | reimplemented as collect-all |

Datatype suggestion map, pattern compile, SeeAlso URL, whitespace-in-Id, and
cardinality checks have **no** `dd_core` equivalent → implemented in
`checks.py`.

---

## 5. Packaging

Follows the printer exactly:
- `name = "dd-validate"`, `version = "0.0.1"`, `requires-python = ">=3.9"`,
  BSD-2-Clause.
- Dependency on the converter via the same direct-git pattern:
  `dd-core @ git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=core`.
- `[project.scripts] dd-validate = "dd_validator.cli:main"`.
- ruff config identical to the other packages (F,E,W,B,C4,UP,SIM @ 100 cols),
  `from __future__ import annotations`, modern type hints, pytest tests.

---

## 6. Exit codes

The Java tool always returns 0. **[DEPART, default-on]** Proposed:
- `0` — no findings at/above the reporting threshold.
- `1` — findings present (default gate: any ERROR).
- `2` — usage error (input not found, unreadable), matching converter/printer.

Rationale: a validator invoked in CI is expected to fail the build on errors;
always-0 makes it useless as a gate. `--exit-zero` can restore the Java behavior.
This is Q2 in §7.

---

## 7. Open questions for you

1. **Duplicate-Id check.** The Java validator has no cross-row checks, but this
   repo's converter treats duplicate Ids as fatal. Include a duplicate-Id check
   (as an ERROR) in v1? *Recommend: yes* — it's the one cross-row rule the spec
   clearly implies, and it's cheap.
2. **Exit codes.** Gate exit status on findings (exit 1 on any ERROR) as above,
   or stay faithful to the Java always-0? *Recommend: gate on ERROR*, with
   `--exit-zero` to opt out.
3. **Default output format.** Java defaults to TSV. This repo's other tools are
   human-first (printer → HTML) with JSON as the machine path. *Recommend:
   `text` default for a person at a terminal; `csv/tsv/json` on request.*
4. **Command/package name.** `dd-validate` (verb) vs `dd-validator` (noun) —
   the other two are verbs (`dd-print`) and nouns-as-packages (`dd_printer`).
   *Recommend: command `dd-validate`, package `dd_validator`.*
