"""Command-line interface: convert a data dictionary between formats.

``dd-json`` reads a data dictionary in any of the toolkit's formats — CSV, a
LinkML schema, or dd-json — and writes it out in any of them, defaulting to the
canonical **dd-json** for serving over a web API::

    dd-json my_dictionary.csv                 # -> dd-json on stdout
    dd-json my_schema.yaml -o out.json        # LinkML in, dd-json out
    dd-json data.json --format csv            # dd-json in, CSV out

Input format is detected from the content; output is chosen with ``--format``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .model import DataDictionary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dd-json",
        description="Convert a data dictionary between CSV, LinkML, and dd-json.",
    )
    parser.add_argument(
        "input", type=Path, help="Data dictionary: a CSV, a LinkML schema, or dd-json."
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output file (default: stdout)."
    )
    parser.add_argument(
        "-f", "--format", choices=("json", "csv", "linkml"), default="json",
        help="Output format (default: json — the canonical dd-json).",
    )
    parser.add_argument(
        "--compact", action="store_true",
        help="For JSON output, omit null and empty-list fields (leaner payload).",
    )
    return parser


def _detect(text: str) -> str:
    """Guess the input format: 'json' (dd-json), 'linkml', or 'csv'."""
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return "json"
    try:
        data = yaml.safe_load(text)
        if isinstance(data, dict) and "classes" in data:
            return "linkml"
    except yaml.YAMLError:
        pass
    return "csv"


def _load(text: str) -> DataDictionary:
    kind = _detect(text)
    if kind == "json":
        return DataDictionary.from_json(text)
    if kind == "linkml":
        import io

        return DataDictionary.from_linkml(io.StringIO(text))
    import io

    return DataDictionary.load(io.StringIO(text))


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2

    try:
        dictionary = _load(args.input.read_text(encoding="utf-8-sig"))
    except (ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.format == "csv":
        rendered = dictionary.to_csv()
    elif args.format == "linkml":
        rendered = dictionary.to_linkml()
    else:
        rendered = dictionary.to_json(compact=args.compact)

    if args.output is None:
        sys.stdout.write(rendered if rendered.endswith("\n") else rendered + "\n")
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {len(dictionary)} data elements to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
