"""Convert a REDCap data dictionary into the specification's format.

REDCap studies export their instrument definitions as a CSV of their own
shape. This package reads that export and produces a
:class:`~dd_api.DataDictionary` — so the result can be written as a
data dictionary CSV, rendered with the printer, checked with the validator,
or converted to LinkML, like any other dictionary::

    from dd_redcap import convert_redcap

    dd = convert_redcap("redcap_export.csv", provenance="My Study")
    print(dd.to_csv())

The conversion is described in ``REDCAP_PLAN.md``. What carries over: field
names, labels (with field notes folded in), sections, choices (as
enumerations), datatypes (from REDCap validation types), and generated prose
descriptions that explain choice counts and branching logic in plain English.
"""

from .convert import convert_redcap
from .headers import ConversionError, RedCapSheet, read_sheet

__all__ = [
    "convert_redcap",
    "ConversionError",
    "RedCapSheet",
    "read_sheet",
]
