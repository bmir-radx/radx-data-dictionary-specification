# Data Dictionary Printer

`dd-print` renders a data dictionary into a human-readable, self-contained
**HTML page** (or JSON). The dictionary is grouped by section, and each data
element is shown as a card: its id, label, facets (datatype, cardinality, unit,
pattern), ontology terms, a Markdown-rendered description, and its enumeration
of permissible values.

The input can be a data dictionary **CSV** or a **LinkML schema** produced by the
sibling [converter](../converter/) — the format is detected automatically.

## Install

For a command-line tool, [`pipx`](https://pipx.pypa.io) is the recommended way to
install it — it puts `dd-print` on your `PATH` in its own isolated environment:

```
pipx install "git+https://github.com/bmir-radx/radx-data-dictionary-specification.git#subdirectory=printer"
```

On first use of pipx, its bin directory may not be on your `PATH` (pipx warns if
so). Run `pipx ensurepath` once — then open a new terminal — to add it.

The printer depends on the sibling [API package](../api/) (for loading
dictionaries); the command above pulls it in automatically. To install into an
existing environment instead of an isolated one, use `pip` in place of `pipx`.

## Use it

```
# Render to a self-contained HTML page
dd-print my_dictionary.csv -o my_dictionary.html

# ...from a generated LinkML schema instead of a CSV (auto-detected)
dd-print my_schema.yaml -o my_dictionary.html

# Render to JSON (format inferred from the .json extension)
dd-print my_dictionary.csv -o my_dictionary.json

# Write to stdout (HTML by default) so you can pipe it
dd-print my_dictionary.csv | less
```

Options:

| Option | Effect |
| --- | --- |
| `-o`, `--output` | Output file (default: stdout). |
| `-f`, `--format` | `html` or `json` (default: inferred from the `-o` extension, else `html`). |
| `--title` | Document title (default: the input filename). |

## What it produces

- **HTML** — one self-contained file (all CSS inlined, no external assets), so it
  opens offline and prints cleanly. Sections become headed groups; each data
  element is a card. Descriptions are rendered from Markdown, with two
  conveniences: a backtick-quoted record id (`` `age` ``) becomes an in-page
  link to that record, and a backtick-quoted enumeration value (`` `0` ``)
  becomes a value badge (missing-value codes are styled distinctly).
- **JSON** — the sectioned model (sections → records → choices), pretty-printed.

## Development

```
pip install -e "./printer[test]"
pytest printer
```
