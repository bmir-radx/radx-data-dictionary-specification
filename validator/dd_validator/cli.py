"""Command-line interface: validate a data dictionary and report violations.

Usage::

    dd-validate INPUT [-o OUTPUT] [--format text|csv|tsv|json]
                [--levels ERROR WARNING INFO] [--no-duplicate-check]
                [--exit-zero]

INPUT may be a single CSV file or a directory (every ``*.csv`` beneath it is
validated). Output goes to stdout unless ``-o`` is given.

Exit codes: ``0`` when no ERROR-level findings remain after filtering, ``1``
when any ERROR is present, ``2`` on a usage error (input not found). Pass
``--exit-zero`` to always exit ``0`` regardless of findings.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import report
from .model import Finding, Level
from .validate import validate


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dd-validate",
        description="Validate a data dictionary CSV against the specification.",
    )
    parser.add_argument(
        "input", type=Path, help="Data dictionary CSV, or a directory of CSVs."
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output file (default: stdout)."
    )
    parser.add_argument(
        "-f", "--format", choices=report.FORMATS, default="text",
        help="Report format (default: text).",
    )
    parser.add_argument(
        "--levels", nargs="+", choices=[level.name for level in Level], default=None,
        help="Only report these severity levels (default: all).",
    )
    parser.add_argument(
        "--no-duplicate-check", action="store_true",
        help="Do not check for duplicate Ids (matches the reference validator).",
    )
    parser.add_argument(
        "--exit-zero", action="store_true",
        help="Always exit 0, even when errors are found.",
    )
    return parser


def _inputs(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.rglob("*.csv") if not p.name.startswith("."))
    return [path]


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    levels = {Level[name] for name in args.levels} if args.levels else None

    sections: list[str] = []
    all_findings: list[Finding] = []
    for path in _inputs(args.input):
        findings = validate(path, check_duplicate_ids=not args.no_duplicate_check)
        if levels is not None:
            findings = [f for f in findings if f.level in levels]
        all_findings.extend(findings)
        sections.append(report.render(findings, args.format, file=str(path)))

    rendered = _join(sections, args.format)

    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.write_text(rendered, encoding="utf-8")

    errors = sum(1 for f in all_findings if f.level is Level.ERROR)
    print(
        f"{len(all_findings)} finding(s), {errors} error(s).", file=sys.stderr
    )

    if args.exit_zero:
        return 0
    return 1 if errors else 0


def _join(sections: list[str], fmt: str) -> str:
    """Concatenate per-file report sections.

    For the tabular formats each section carries its own header row; when
    validating several files we keep the first header and drop the repeats so
    the output is one table.
    """
    if fmt in ("csv", "tsv") and len(sections) > 1:
        kept = []
        header_seen = False
        for section in sections:
            lines = section.splitlines()
            if not lines:
                continue
            if header_seen:
                lines = lines[1:]  # drop the repeated header row
            header_seen = True
            kept.extend(lines)
        return "\n".join(kept) + ("\n" if kept else "")
    return "".join(sections)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
