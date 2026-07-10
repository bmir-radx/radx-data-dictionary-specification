# Contributing

Thanks for your interest in improving the Data Dictionary Specification and its
tooling. This repo is a small monorepo of six Python packages built on one
[specification](SPECIFICATION.md); contributions to any of them — or to the
spec itself — are welcome.

## Repository layout

Each directory is an independent, pip-installable package:

| Package | Distribution | Depends on |
| --- | --- | --- |
| [`core/`](core/) | `dd-core` | — |
| [`linkml/`](linkml/) | `dd-linkml` | core |
| [`validator/`](validator/) | `dd-validate` | core |
| [`api/`](api/) | `dd-api` | core, linkml |
| [`printer/`](printer/) | `dd-print` | api |
| [`redcap/`](redcap/) | `dd-redcap` | api |

All six share one version number.

## Development setup

Clone the repo and install the packages **from the local checkout** into a
virtual environment. Install the third-party dependencies explicitly first, then
the local packages with `--no-deps` — this is important: the pinned
`dd-* @ git+...` URLs in each `pyproject.toml` would otherwise make pip clone the
last *released* siblings from GitHub and shadow the code you're editing.

```sh
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip

# Third-party runtime + test deps (the union across all packages).
pip install "lark>=1.1" "linkml>=1.8" pyyaml "jinja2>=3" \
    "markdown-it-py[linkify]>=3" "jsonschema>=4" "pytest>=7"

# Local packages, editable, in dependency order, with --no-deps so no sibling
# is fetched from git.
for pkg in core linkml validator api printer redcap; do
    pip install --no-deps -e "./$pkg"
done
```

## Running the checks

CI runs exactly these two things; run them locally before opening a PR:

```sh
# Lint (uses the root ruff.toml).
ruff check

# Test each package (each package's pyproject drives its own testpaths and
# doctest options; api and redcap run their docstring examples as doctests).
for pkg in core linkml validator api printer redcap; do
    ( cd "$pkg" && pytest )
done
```

## Conventions

- **Python ≥ 3.9.** CI tests on 3.9 and 3.12; don't use syntax newer than 3.9.
- **Lint with ruff** (`F,E,W,B,C4,UP,SIM,I` at 100 columns — see `ruff.toml`).
- **reStructuredText docstrings.** Public API examples are executable doctests
  (`api`, `redcap`) — keep them passing; they are how the docs stay honest.
- **The Markdown [`SPECIFICATION.md`](SPECIFICATION.md) is authoritative.** If a
  change alters behaviour the spec describes, update the spec in the same PR.
- **A design/plan doc per tool.** Larger tools carry a plan or conversion
  document (e.g. `linkml/CONVERTER_PLAN.md`, `redcap/CONVERSION.md`); update it
  when you change the algorithm it describes.

## Pull requests and releases

Every merge to `main` automatically cuts a release (version bump + tag + GitHub
release), which is what lets users `pipx upgrade` the tools. The bump size comes
from the PR's labels:

| Label | Effect |
| --- | --- |
| `release:major` | major bump (`X`.0.0) |
| `release:minor` | minor bump (x.`Y`.0) |
| *(none)* | patch bump (x.y.`Z`) — the default |
| `release:skip` | no release (docs-only / CI-only changes) |

So: label user-facing feature PRs `release:minor`, breaking changes
`release:major`, and label pure docs/CI/chore PRs `release:skip`. If you forget,
a patch release is cut — harmless but noisy.

## Reporting bugs and requesting features

Open an issue using one of the [templates](.github/ISSUE_TEMPLATE). For security
issues, please follow [SECURITY.md](SECURITY.md) instead of filing a public
issue.
