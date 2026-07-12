"""The severity model and the finding record.

A validator, unlike the converter's reader, must collect *every* problem rather
than stop at the first. Each problem is a :class:`Finding`. Findings carry a
:class:`Level` so a report can be filtered by severity and a caller can gate an
exit code on the presence of errors.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Level(enum.Enum):
    """Severity of a finding.

    ``ERROR`` marks something that makes the dictionary invalid (a MUST in the
    specification). ``WARNING`` marks a SHOULD — the dictionary is still valid.
    ``INFO`` is an optional improvement. The associated integer orders levels
    for sorting (most severe first) and is stable for reports.
    """

    ERROR = 0
    WARNING = 1
    INFO = 2

    @property
    def order(self) -> int:
        """Sort rank: lower is more severe (ERROR sorts first)."""
        return self.value

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Finding:
    """One validation problem.

    ``check`` is a short stable identifier (e.g. ``"unknown-datatype"``).

    A finding is addressed two ways. ``line`` is the 1-based line in the
    source CSV — a *presentation* of location, meaningful only for the CSV
    that was validated. ``element_index`` / ``element_id`` are the
    format-independent address: the element's 0-based position in document
    order (stable across CSV, dd-json, and LinkML renderings, which all
    preserve element order) and its ``Id``. The index is canonical — ids may
    legitimately be duplicated in a document under repair — and the id is the
    human-readable companion. Both are ``None`` for whole-file findings.

    ``column`` and ``value`` locate the offending cell when applicable, and
    ``suggestion`` carries a machine-usable replacement value when the check
    has one (e.g. the schema-safe spelling of an Id).
    """

    level: Level
    check: str
    message: str
    line: int | None = None
    column: str | None = None
    value: str | None = None
    element_index: int | None = None
    element_id: str | None = None
    suggestion: str | None = None

    @property
    def sort_key(self) -> tuple[int, int, str]:
        """Order by source line, then severity, then check name."""
        return (self.line or 0, self.level.order, self.check)
