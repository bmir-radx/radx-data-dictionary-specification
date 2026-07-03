"""Command-line interface: render a data dictionary to HTML or JSON.

Usage: ``dd-print INPUT [-o OUTPUT] [--format html|json]``. INPUT may be a data
dictionary CSV or a generated LinkML schema (auto-detected).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .load import load_dictionary
from .render_html import render_html
from .render_json import render_json


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dd-print",
        description="Render a data dictionary (CSV or LinkML schema) to HTML or JSON.",
    )
    parser.add_argument(
        "input", type=Path, help="Data dictionary CSV or LinkML schema."
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output file (default: stdout).",
    )
    parser.add_argument(
        "-f", "--format", choices=("html", "json"), default=None,
        help="Output format (default: inferred from -o extension, else html).",
    )
    parser.add_argument("--title", default=None, help="Document title (default: filename).")
    return parser


def _resolve_format(args: argparse.Namespace) -> str:
    if args.format:
        return args.format
    if args.output and args.output.suffix.lower() == ".json":
        return "json"
    return "html"


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2

    dictionary = load_dictionary(args.input, title=args.title)
    output_format = _resolve_format(args)
    rendered = render_json(dictionary) if output_format == "json" else render_html(dictionary)

    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(
            f"Wrote {len(dictionary.records)} data elements to {args.output}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
