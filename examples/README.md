# Examples

Real data dictionaries run through the toolkit. Each named example (`gcb`,
`rad`, `dht`, `tech`, `up`) appears in several formats:

| Suffix | What it is | Produced by |
| --- | --- | --- |
| `.redcap.csv` | The original REDCap export (`rad`, `up` only) | — (source) |
| `.dd.csv` | The data dictionary, in the spec's CSV format | `redcap-to-dd` (for `rad`/`up`) |
| `.yaml` | The equivalent LinkML schema | `dd-to-linkml` |
| `.html` | A rendered, browsable page | `dd-print` |

So `rad` and `up` show the whole chain — REDCap export → dictionary → LinkML
schema → HTML — while `gcb`, `dht`, and `tech` start from the `.dd.csv`.

All files are regenerable from the `.dd.csv` (or, for `rad`/`up`, the
`.redcap.csv`) with the toolkit's commands. See the top-level
[README](../README.md#worked-examples) for the rendered-page links.
