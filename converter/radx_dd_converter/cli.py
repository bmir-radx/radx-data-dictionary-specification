"""Command-line interface for the RADx data dictionary -> LinkML converter.

Usage::

    radx-dd-to-linkml INPUT.csv -o SCHEMA.yaml [--name ...] [--id ...] [--class-name ...]

When ``--name`` / ``--id`` / ``--class-name`` are omitted they are derived from
the input filename (e.g. ``patient_data.csv`` -> name ``patient_data``, class
``PatientData``). Output goes to ``-o`` / ``--output`` or, by default, stdout.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from collections.abc import Sequence

from .datatypes import UnknownDatatypeError
from .emit import EmitOptions, emit_schema
from .grammar import ParseError
from .reader import ReadError, read_data_dictionary
from .terms_lookup import LookupError_

DEFAULT_ID_BASE = "https://w3id.org/radx"


def _name_from_filename(path: Path) -> str:
    """Derive a schema name from an input filename.

    ``gcb.dd.csv`` -> ``gcb``; ``patient_data.csv`` -> ``patient_data``. Strips
    a trailing ``.dd`` (a common RADx data-dictionary suffix) and sanitises to a
    LinkML-safe token.
    """
    stem = path.name
    for suffix in (".csv", ".tsv"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem.lower().endswith(".dd"):
        stem = stem[:-3]
    safe = re.sub(r"\W+", "_", stem).strip("_").lower()
    return safe or "data_dictionary"


def _class_from_name(name: str) -> str:
    # Split on any non-alphanumeric, including underscores, so
    # "patient_data" -> "PatientData". (cf. _class_case in emit.py, the same
    # casing; here the empty-input fallback is "Record" rather than "X".)
    parts = re.split(r"[^A-Za-z0-9]+", name)
    return "".join(p[:1].upper() + p[1:] for p in parts if p) or "Record"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="radx-dd-to-linkml",
        description="Convert a RADx data dictionary CSV into a LinkML schema.",
    )
    parser.add_argument("input", type=Path, help="Path to the data dictionary CSV.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output schema file (default: stdout).",
    )
    parser.add_argument("--name", default=None, help="Schema name (default: from filename).")
    parser.add_argument(
        "--id",
        dest="schema_id",
        default=None,
        help="Schema id/URI (default: derived from name).",
    )
    parser.add_argument(
        "--class-name",
        default=None,
        help="Root class name (default: CamelCase of the name, else Record).",
    )
    parser.add_argument(
        "--annotate-terms",
        action="store_true",
        help="Look up ontology term names and add them as YAML comments. "
        "Requires network access; unresolved terms are skipped.",
    )
    parser.add_argument(
        "--resolver",
        choices=("ols4", "bioportal"),
        default="ols4",
        help="Term-name resolver for --annotate-terms (default: ols4). "
        "'bioportal' requires an API key.",
    )
    parser.add_argument(
        "--bioportal-apikey",
        default=None,
        help="BioPortal API key (overrides the BIOPORTAL_API_KEY env var).",
    )
    parser.add_argument(
        "--annotate-enum-values",
        action="store_true",
        help="After a field enum range, add a comment listing its value=label "
        "pairs (capped, with a '(+N more)' overflow).",
    )
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Do not fail on a duplicate Id; keep the first occurrence, skip "
        "later ones, and warn (shown with --verbose).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show warnings (e.g. non-OBO CURIE prefixes, failed term lookups).",
    )
    return parser


def _resolve_options(args: argparse.Namespace) -> EmitOptions:
    name = args.name or _name_from_filename(args.input)
    class_name = args.class_name or _class_from_name(name)
    schema_id = args.schema_id or f"{DEFAULT_ID_BASE}/{name}"
    apikey = args.bioportal_apikey or os.environ.get("BIOPORTAL_API_KEY")
    return EmitOptions(
        schema_id=schema_id,
        schema_name=name,
        class_name=class_name,
        annotate_terms=args.annotate_terms,
        resolver=args.resolver,
        bioportal_apikey=apikey,
        annotate_enum_values=args.annotate_enum_values,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.verbose else logging.ERROR,
        format="%(levelname)s: %(message)s",
    )

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2

    try:
        rows = read_data_dictionary(
            args.input, allow_duplicates=args.allow_duplicates
        )
        schema_yaml = emit_schema(rows, _resolve_options(args))
    except (ReadError, ParseError, UnknownDatatypeError, LookupError_) as exc:
        # Expected, user-facing errors: report cleanly without a traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output is None:
        sys.stdout.write(schema_yaml)
    else:
        args.output.write_text(schema_yaml, encoding="utf-8")
        print(
            f"Wrote {len(rows)} data elements to {args.output}", file=sys.stderr
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
