# Data Dictionary Printer (Python) — Design

> **Status:** Planning. A Python port of the Java printer at
> `radx-data-dictionary-printer`, scoped to the core printing pipeline. It lives
> here as a sibling to [`../converter/`](../converter/) so it can reuse the
> converter's parsing code directly.
>
> **De-branded / generic:** the printer itself carries no "RADx" naming or
> RADx-specific concepts (no program badges, tiers, or harmonization). It is a
> neutral *data dictionary* printer. Package `dd_printer`, command `dd-print`.
> (The input still comes from the RADx-aware converter; the printer stays
> vocabulary-neutral.)

## Goal

Render a data dictionary into human-readable output — primarily a
**self-contained HTML page** (and JSON), grouped by section, with each data
element shown as a card: its id, label, facets (datatype, cardinality, unit,
pattern), description (Markdown → HTML), and enumeration choices.

## Scope

**In scope** — the core printing pipeline from the Java app:
- Group records by `Section` (preserving order), numbered 1..N across the whole
  dictionary.
- Render `Description` (and `Notes`) from Markdown to HTML.
- Enrichments applied to the description markdown before rendering:
  - backtick-wrapped record ids (`` `nih_race` ``) → in-page cross-reference links;
  - enumeration choice values (`` `0` ``) → styled badges, flagged when they are
    missing-value codes.
- HTML output (Bootstrap-styled, print-friendly, per-record cards) and JSON.

**Out of scope** (was RADx Tier 1-specific; becomes a separate data-harmonization
effort later): the entire mappings subsystem — program mappings, enumeration
mappings, `Augmented*`/`Mapped*` model classes, `TermOracle` + reference
ontologies, `RadxProgram` badges, harmonized-id spans, and the harmonization
parts of `DescriptionGenerator`. **Do not port these.**

## Input (decided direction, confirm in first session)

Read the **LinkML data dictionary schema** produced by `../converter/`
(`dd-to-linkml`), reusing the converter's reader/reverse code, rather than
re-implementing a CSV parser. A data dictionary CSV can be printed by running it
through the converter first (or we accept CSV directly via the converter's
`read_data_dictionary`). This is the main reason the printer lives in this repo.

## Output formats (reproduce the Java behaviour)

- **HTML**: one page. `<head>` pulls in Bootstrap 4.4.1 (CDN) + an inline
  `<style>` block (copy the rules from `template.html`: `.record`, `.record__id`,
  `.record__facet`, `.badge`, `.choice__value`, print `@media` rules, etc.).
  Body = a section-by-section list; each record is a card showing number, id
  (anchored `id=` for cross-refs), label, facet badges, rendered description,
  and the enumeration table. Java uses Thymeleaf; **Python uses Jinja2**.
- **JSON**: the sectioned/record model serialised (pretty-printed). Define the
  Python model (dataclasses) to mirror the useful fields of
  `AugmentedDataDictionaryRecord` minus the mapping fields.

## Description generation (optional, non-mapping part)

`DescriptionGenerator` can synthesise a sentence when a description is absent:
"The `<id>` data element records responses to the prompt \"<label>\". The values
for this data element are <type>s [that come from a list of N permissible
<type> values]." Keep this non-mapping core; drop the harmonized-prompt parts.

## Architecture (proposed)

```
printer/
  dd_printer/
    model.py       # dataclasses: Section, Record, Choice (no mapping fields)
    load.py        # LinkML schema (or CSV via converter) -> [Section] of Records
    markdown.py    # description enrichment (id links, choice badges) + md->html
    render_html.py # Jinja2 template -> self-contained HTML
    render_json.py # model -> JSON
    cli.py         # dd-print IN -o OUT [--format html|json]
    templates/dictionary.html.j2
    static/dictionary.css   # extracted from template.html
  tests/
```
Depends on: the local `dd_converter` package, `markdown-it-py`, and Jinja2.

## Resolved decisions

1. **Input surface (decided)**: accept **both** a data dictionary CSV (via the
   converter's `read_data_dictionary`) and a generated LinkML schema. `load.py`
   sniffs the input (`.csv` vs `.yaml`) and normalises to the printer model.
2. **HTML self-containment (decided)**: **fully self-contained** — inline all
   CSS in the page (no Bootstrap CDN link); the output is one portable file that
   renders offline. The bespoke `.record`/`.badge`/etc. rules from
   `template.html` are inlined; Bootstrap-specific utility classes are replaced
   with equivalent local styles rather than pulling the CDN.
3. **Markdown library (decided)**: `markdown-it-py` (CommonMark-compliant,
   closest to the Java commonmark; linkify plugin for the autolink behaviour).

## Open questions (still to decide)

- **Term names in output**: reuse the converter's `terms_lookup` to show
  human-readable labels for ontology terms? (Optional, network.) Defer.
- **Command name (decided)**: `dd-print` (kebab-case, neutral — no "radx").

## Reference (Java source to reproduce)

`radx-data-dictionary-printer/src/main/java/.../`: `Renderer` (enrichment +
md→html), `SectionedDataDictionary` / `DataDictionarySection` (grouping +
numbering), `DataDictionaryHtmlRenderer` / `DataDictionaryJsonRenderer`,
`DescriptionGenerator` (non-mapping part), and `src/main/resources/template.html`
(the HTML/CSS to reproduce).
