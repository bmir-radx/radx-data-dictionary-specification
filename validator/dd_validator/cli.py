"""Command-line interface: validate a data dictionary and report violations.

Usage::

    dd-validate INPUT [-o OUTPUT] [--format text|csv|tsv|json]
                [--levels ERROR WARNING INFO] [--no-duplicate-check]
                [--ignore CHECK ...] [--exit-zero]

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
        "--ignore", nargs="+", metavar="CHECK", default=(),
        help="Drop findings by check name (e.g. --ignore missing-unit "
        "datatype-preferred), for tuning out advisory checks.",
    )
    parser.add_argument(
        "--exit-zero", action="store_true",
        help="Always exit 0, even when errors are found.",
    )
    return parser


def _input_files(path: Path) -> list[Path]:
    """Return the CSV files to validate: the path itself, or every non-hidden
    ``*.csv`` beneath it when it is a directory."""
    if path.is_dir():
        return sorted(p for p in path.rglob("*.csv") if not p.name.startswith("."))
    return [path]


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    levels = {Level[name] for name in args.levels} if args.levels else None

    per_file_reports: list[str] = []
    all_findings: list[Finding] = []
    for path in _input_files(args.input):
        findings = validate(
            path, check_duplicate_ids=not args.no_duplicate_check, ignore=args.ignore
        )
        if levels is not None:
            findings = [finding for finding in findings if finding.level in levels]
        all_findings.extend(findings)
        per_file_reports.append(report.render(findings, args.format, file=str(path)))

    rendered = _join_reports(per_file_reports, args.format)

    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.write_text(rendered, encoding="utf-8")

    error_count = sum(1 for finding in all_findings if finding.level is Level.ERROR)
    print(
        f"{len(all_findings)} finding(s), {error_count} error(s).", file=sys.stderr
    )

    if args.exit_zero:
        return 0
    return 1 if error_count else 0


def _join_reports(per_file_reports: list[str], fmt: str) -> str:
    """Concatenate per-file reports into one document.

    Each tabular (csv/tsv) report carries its own header row; when several
    files were validated, keep the first header and drop the repeats so the
    result is a single table.
    """
    if fmt in ("csv", "tsv") and len(per_file_reports) > 1:
        joined_lines: list[str] = []
        header_seen = False
        for file_report in per_file_reports:
            lines = file_report.splitlines()
            if not lines:
                continue
            if header_seen:
                lines = lines[1:]  # drop the repeated header row
            header_seen = True
            joined_lines.extend(lines)
        return "\n".join(joined_lines) + ("\n" if joined_lines else "")
    return "".join(per_file_reports)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
