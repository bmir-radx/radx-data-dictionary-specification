"""Command-line interface: convert a REDCap data dictionary.

Usage: ``redcap-to-dd INPUT [-o OUTPUT] [--provenance TEXT]``. INPUT is a
REDCap data dictionary CSV; the output is a data dictionary CSV in the
specification's format (stdout unless ``-o`` is given).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .convert import convert_redcap
from .headers import ConversionError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="redcap-to-dd",
        description="Convert a REDCap data dictionary CSV to a data dictionary CSV.",
    )
    parser.add_argument("input", type=Path, help="REDCap data dictionary CSV.")
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output file (default: stdout)."
    )
    parser.add_argument(
        "--provenance", default="",
        help="Text for every element's Provenance column (e.g. the study name).",
    )
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2

    try:
        dictionary = convert_redcap(args.input, provenance=args.provenance)
    except (ConversionError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    csv_text = dictionary.to_csv()
    if args.output is None:
        sys.stdout.write(csv_text)
    else:
        args.output.write_text(csv_text, encoding="utf-8")
        print(f"Wrote {len(dictionary)} data elements to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
