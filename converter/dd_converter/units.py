"""Built-in unit table for mapping a ``Unit`` cell to a UnitOfMeasure.

``Unit`` values are free text (the specification provides no controlled
list). This module carries the small table of common units from the
specification's own example table, keyed by both unit name and symbol, so the
converter can populate a structured LinkML ``unit:`` block (``descriptive_name``,
``symbol``, and ``ucum_code`` where known) for a recognised unit. Unrecognised
units fall back to ``symbol = <raw string>`` in the emitter, and the raw cell is
always preserved as ``annotations.unit_raw`` (see ``linkml/CONVERTER_PLAN.md``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitOfMeasure:
    """A structured unit, mirroring the fields of LinkML's UnitOfMeasure."""

    descriptive_name: str
    symbol: str
    ucum_code: str | None = None


# The "common units" table from radx-data-dictionary-specification.md.
# (descriptive_name, symbol, ucum_code). UCUM codes are filled where a
# well-defined code exists; None where the free-text unit has no obvious UCUM
# form (the emitter simply omits ucum_code in that case).
_UNIT_TABLE = (
    UnitOfMeasure("millimeter", "mm", "mm"),
    UnitOfMeasure("meter", "m", "m"),
    UnitOfMeasure("inch", "in", "[in_i]"),
    UnitOfMeasure("foot", "ft", "[ft_i]"),
    UnitOfMeasure("liter", "L", "L"),
    UnitOfMeasure("milliliter", "mL", "mL"),
    UnitOfMeasure("second", "s", "s"),
    UnitOfMeasure("minute", "min", "min"),
    UnitOfMeasure("hour", "h", "h"),
    UnitOfMeasure("day", "d", "d"),
    UnitOfMeasure("week", "w", "wk"),
    UnitOfMeasure("degrees Celsius", "°C", "Cel"),
    UnitOfMeasure("Fahrenheit", "°F", "[degF]"),
    UnitOfMeasure("kelvin", "K", "K"),
    UnitOfMeasure("milligram", "mg", "mg"),
    UnitOfMeasure("gram", "g", "g"),
    UnitOfMeasure("kilogram", "kg", "kg"),
    UnitOfMeasure("pound", "lb", "[lb_av]"),
    UnitOfMeasure("mole", "mol", "mol"),
    UnitOfMeasure("ampere", "A", "A"),
    UnitOfMeasure("moles per liter", "mol/L", "mol/L"),
)

# Lookup by both name and symbol, case-insensitively. A name and a symbol never
# collide in the spec table, so a single map is unambiguous.
_LOOKUP: dict[str, UnitOfMeasure] = {}
for _unit in _UNIT_TABLE:
    _LOOKUP[_unit.descriptive_name.lower()] = _unit
    _LOOKUP[_unit.symbol.lower()] = _unit


def lookup_unit(raw: str) -> UnitOfMeasure | None:
    """Return the :class:`UnitOfMeasure` for a raw ``Unit`` cell, or ``None``.

    Matches by unit name or symbol, ignoring surrounding white space and case.
    Returns ``None`` when the unit is not in the built-in table (the emitter
    then falls back to ``symbol = <raw>``).
    """
    if raw is None:
        return None
    key = raw.strip().lower()
    if key == "":
        return None
    return _LOOKUP.get(key)
