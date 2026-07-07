"""Validate a data dictionary CSV against the specification.

This package reports *every* violation it finds rather than transforming the
dictionary. It is described in ``VALIDATOR_PLAN.md``. The per-cell parsing rules
(datatype names, the enumeration and missing-value-codes grammars) are reused
from the sibling :mod:`dd_converter` package so the validator stays in lockstep
with the converter and the specification.
"""

from .model import Finding, Level
from .report import FORMATS, render
from .rows import RawRow, read_rows
from .validate import validate

__all__ = [
    "Finding",
    "Level",
    "FORMATS",
    "render",
    "RawRow",
    "read_rows",
    "validate",
]
