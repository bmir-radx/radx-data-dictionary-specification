# Generalization Plan — make the data dictionary toolkit adoptable outside RADx

> **Status:** Planning. Goal: keep this repository, but generalize the spec and
> tools so they read and work as a general-purpose **data dictionary** toolkit
> that others can adopt, with RADx as one user rather than the whole identity.
> "Generalize in place" — no repo move, no PyPI (yet).

## Decisions (settled)

- **Rename packages & commands to neutral names** (drop `radx`):
  - `radx_dd_converter` → **`dd_converter`**; dist `radx-dd-converter` → **`dd-converter`**;
    commands `radx-dd-to-linkml` → **`dd-to-linkml`**, `linkml-to-radx-dd` → **`linkml-to-dd`**.
  - printer: package stays `dd_printer`; command stays `dd-print` (already neutral);
    dist `dd-printer` unchanged. Its dependency on the converter updates to the new name.
- **Keep the repo name** `radx-data-dictionary-specification`. Renaming would
  break every clone/install URL. Consequence: the install *URLs* still contain
  `radx` (`git+https://…/radx-data-dictionary-specification.git#subdirectory=…`)
  even though the installed command is `dd-to-linkml`. Acceptable for "in place".
- **Missing-value codes become pluggable/optional.** The 25-code set is the only
  RADx-specific *content*. Keep it as a built-in **default** an adopter can
  replace, rather than a privileged constant. (Design below.)
- **Generalize the prose** across spec + READMEs + plans so the framing is a
  general toolkit; keep legitimate attribution (LICENSE copyright; "originally
  developed for RADx"). The Markdown spec title/body stays RADx-attributed but
  should note the format is general-purpose.

## Pluggable missing-value codes (design)

Currently `missing_values.py` hard-codes the 25 standard codes and the emitter
always wires `StandardMissingValueCodes` into every enumerated slot's `any_of`.
Generalize:

- Keep the RADx set as a named built-in default (e.g. `DEFAULT_MISSING_VALUE_CODES`,
  parsed from the same verbatim string) but stop implying it is *the* set.
- Add an option (`EmitOptions.missing_value_codes: list[EnumItem] | None`) and a
  CLI flag to **override** the set — supply codes from a file/string, or pass an
  empty set to omit the shared missing-codes enum entirely.
- The reverse converter and printer already read whatever enum is present, so
  they need no code-set knowledge — only naming updates.

## Rename mechanics (do carefully; this is the error-prone part)

1. `git mv converter/radx_dd_converter converter/dd_converter`.
2. Update every `radx_dd_converter` import (converter, printer, tests) → `dd_converter`.
3. `pyproject.toml`: dist name, `[project.scripts]` entry points, package-find
   include, the printer's git dependency URL (subdirectory unchanged).
4. Rename entry-point functions' console names only (module `cli:main` / `reverse:main` unchanged).
5. Reinstall editable; run the full suite + ruff after each package to catch a missed import.
6. Regenerate the committed example schemas (headers mention the old command name).

## Prose generalization (files to touch)

Spec `radx-data-dictionary-specification.md`, root `README.md`, `converter/README.md`,
`printer/README.md`, `linkml/CONVERTER_PLAN.md`, `printer/PRINTER_PLAN.md`, and
inline comments that say "RADx" where it means "a" dictionary. Distinguish:
- **Neutralize**: generic format/tool descriptions currently branded RADx.
- **Keep**: historical attribution, the Canopy note, the missing-code set's RADx origin.

## Suggested execution order (separate PRs)

1. **Pluggable missing-value codes** (feature; behaviour-preserving default) —
   smallest self-contained change, get it in first.
2. **Rename packages/commands** (mechanical but broad) — its own PR; verify
   installs + tests + ruff; regenerate examples.
3. **Prose/docs generalization** — the spec + READMEs + plan docs.

Each step: full test suite + ruff green, generated examples byte-checked, and
verify the fresh-venv install still works (the printer's git-dependency URL).

## Resolved

- Spec title: **retitle** to "Data Dictionary Specification" with a short
  RADx-origin note (the format is general-purpose; RADx is where it originated).
- Missing-codes CLI override: **from a file** containing the enumeration-cell
  grammar (`"code"=[label] | ...`), passed via a flag; an empty override omits
  the shared missing-codes enum.
