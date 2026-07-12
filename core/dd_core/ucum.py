"""UCUM unit suggestions: curated codes, misnomers, and compositional forms.

The specification's ``Unit`` field is free text, but UCUM codes (the Unified
Code for Units of Measure — the standard LOINC and FHIR use) are the
machine-readable spelling, and real dictionaries write units every way but
that: ``years``, ``per year``, ``mcg/ml``, ``kg/m²``, ``bpm``. This module
maps those to their UCUM code so tools can *suggest* the code; nothing here
ever rejects a value.

Coverage is systematic rather than enumerated:

* every curated unit carries its own misnomer metadata — name, plural,
  regional spellings, abbreviations — and the lookup index derives the rest
  (case-insensitive codes, symbol variants);
* normalisation folds the mechanical variation one way: trailing periods,
  whitespace runs, micro signs (``µ``/``μ`` → ``u``), superscript and caret
  exponents (``m²``/``m^2`` → ``m2``);
* compositional rules resolve what no list could: ``per X`` → ``/x``,
  ``X per Y`` and ``X/Y`` → ``x/y``, from the parts — so
  ``micrograms per decilitre`` finds ``ug/dL`` without ever being written
  down.

The curated list is a *small subset* of UCUM, chosen for research data; a
valid code outside it simply gets no suggestion (this module cannot tell a
valid exotic code from a typo, and guessing would be worse than silence).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UcumUnit:
    """One curated unit: its UCUM code, name, and informal spellings."""

    code: str
    name: str
    #: Irregular plural of ``name`` (regular ``+s`` is derived automatically).
    plural: str | None = None
    #: Additional informal spellings / misnomers seen in real dictionaries.
    spellings: tuple[str, ...] = ()


UCUM_UNITS: tuple[UcumUnit, ...] = (
    # --- time
    UcumUnit("a", "year", spellings=("yr", "yrs", "annum", "years old")),
    UcumUnit("mo", "month", spellings=("mos", "mnths")),
    UcumUnit("wk", "week", spellings=("wks",)),
    UcumUnit("d", "day", spellings=()),
    UcumUnit("h", "hour", spellings=("hr", "hrs")),
    UcumUnit("min", "minute", spellings=("mins",)),
    UcumUnit("s", "second", spellings=("sec", "secs")),
    UcumUnit("ms", "millisecond", spellings=("msec", "msecs")),
    # --- mass
    UcumUnit("kg", "kilogram", spellings=("kilogramme", "kilogrammes", "kgs", "kilo", "kilos")),
    UcumUnit("g", "gram", spellings=("gramme", "grammes", "gm", "gms")),
    UcumUnit("mg", "milligram", spellings=("mgs",)),
    UcumUnit("ug", "microgram", spellings=("mcg", "mcgs")),
    UcumUnit("ng", "nanogram"),
    UcumUnit("pg", "picogram"),
    UcumUnit("[lb_av]", "pound", spellings=("lb", "lbs")),
    UcumUnit("[oz_av]", "ounce", spellings=("oz",)),
    UcumUnit("[st_av]", "stone", spellings=("st",)),
    # --- length
    UcumUnit("m", "meter", spellings=("metre", "metres")),
    UcumUnit("cm", "centimeter", spellings=("centimetre", "centimetres")),
    UcumUnit(
        "mm", "millimeter",
        spellings=("millimetre", "millimetres", "milimeter", "milimeters"),
    ),
    UcumUnit("km", "kilometer", spellings=("kilometre", "kilometres")),
    UcumUnit("[in_i]", "inch", plural="inches", spellings=("in",)),
    UcumUnit("[ft_i]", "foot", plural="feet", spellings=("ft",)),
    # --- volume
    UcumUnit("L", "liter", spellings=("litre", "litres", "ltr")),
    UcumUnit("dL", "deciliter", spellings=("decilitre", "decilitres")),
    UcumUnit(
        "mL", "milliliter",
        spellings=("millilitre", "millilitres", "mililiter", "mililiters", "cc", "ccs"),
    ),
    UcumUnit("uL", "microliter", spellings=("microlitre", "microlitres")),
    # --- amount / electrical (from the specification's example table)
    UcumUnit("mol", "mole"),
    UcumUnit("mmol", "millimole"),
    UcumUnit("A", "ampere", spellings=("amp", "amps")),
    UcumUnit("K", "kelvin", spellings=("kelvins",)),
    # --- concentrations / lab (composable, but curated for good names)
    UcumUnit("mg/dL", "milligram per deciliter"),
    UcumUnit("g/dL", "gram per deciliter"),
    UcumUnit("g/L", "gram per liter"),
    UcumUnit("mmol/L", "millimole per liter"),
    UcumUnit("mol/L", "mole per liter", spellings=("moles per liter",)),
    UcumUnit("umol/L", "micromole per liter"),
    UcumUnit("ng/mL", "nanogram per milliliter"),
    UcumUnit("ug/mL", "microgram per milliliter"),
    UcumUnit("pg/mL", "picogram per milliliter"),
    UcumUnit("mEq/L", "milliequivalent per liter", spellings=("meq",)),
    UcumUnit("U/L", "enzyme unit per liter"),
    UcumUnit("[IU]", "international unit", spellings=("iu",)),
    UcumUnit("[IU]/L", "international unit per liter"),
    UcumUnit("[IU]/mL", "international unit per milliliter"),
    UcumUnit("mmol/mol", "millimole per mole"),
    UcumUnit("10*9/L", "billion per liter", spellings=("10^9/l", "x10^9/l")),
    UcumUnit("10*6/uL", "million per microliter"),
    UcumUnit("10*3/uL", "thousand per microliter"),
    # --- rates
    UcumUnit("/min", "per minute"),
    UcumUnit("/h", "per hour", spellings=("per hr",)),
    UcumUnit("/d", "per day", spellings=("daily",)),
    UcumUnit("/wk", "per week", spellings=("weekly",)),
    UcumUnit("/mo", "per month", spellings=("monthly",)),
    UcumUnit("/a", "per year", spellings=("per annum", "yearly", "annually")),
    UcumUnit("/s", "per second"),
    UcumUnit("{beats}/min", "beats per minute", spellings=("bpm",)),
    UcumUnit("{breaths}/min", "breaths per minute", spellings=("brpm",)),
    UcumUnit("mL/min", "milliliter per minute"),
    UcumUnit("mL/min/{1.73_m2}", "milliliter per minute per 1.73 square meters",
             spellings=("ml/min/1.73m2", "ml/min/1.73 m2")),
    # --- pressure, temperature, energy
    UcumUnit("mm[Hg]", "millimeter of mercury", spellings=("mmhg", "mm hg")),
    UcumUnit("kPa", "kilopascal", spellings=("kilopascals",)),
    UcumUnit(
        "Cel", "degree Celsius",
        plural="degrees Celsius",
        spellings=("celsius", "centigrade", "°c", "deg c", "degc"),
    ),
    UcumUnit(
        "[degF]", "degree Fahrenheit",
        plural="degrees Fahrenheit",
        spellings=("fahrenheit", "°f", "deg f", "degf"),
    ),
    UcumUnit("kcal", "kilocalorie", spellings=("kilocalories",)),
    UcumUnit("kJ", "kilojoule", spellings=("kilojoules",)),
    # --- body / composite
    UcumUnit("kg/m2", "kilogram per square meter", spellings=("bmi",)),
    UcumUnit("m2", "square meter", spellings=("sq m", "square meters", "square metres")),
    UcumUnit("mg/kg", "milligram per kilogram"),
    # --- dimensionless
    UcumUnit("%", "percent", spellings=("per cent", "pct", "percentage")),
    UcumUnit("1", "dimensionless", spellings=("unitless", "no unit", "no units")),
)

_BY_CODE: dict[str, UcumUnit] = {u.code: u for u in UCUM_UNITS}


def _normalize(text: str) -> str:
    """Fold the mechanical variation one way (lowercased key form)."""
    folded = (
        text.strip()
        .rstrip(".")
        .replace("µ", "u")   # micro sign U+00B5
        .replace("μ", "u")   # greek mu U+03BC
        .replace("²", "2")
        .replace("³", "3")
        .replace("^", "")
        .lower()
    )
    return " ".join(folded.split())


def _plural(name: str) -> str | None:
    """Derived regular plural of a single-word or leading-noun unit name."""
    if name.startswith("per ") or name.endswith("s"):
        return None
    head, _, tail = name.partition(" per ")
    plural_head = f"{head}s"
    return f"{plural_head} per {tail}" if tail else plural_head


def _build_index() -> dict[str, str]:
    """Map every derived misnomer key to its UCUM code. First entry wins."""
    index: dict[str, str] = {}

    def claim(key: str, code: str) -> None:
        key = _normalize(key)
        if key and key not in index:
            index[key] = code

    for unit in UCUM_UNITS:
        claim(unit.code, unit.code)  # case/symbol-variant code spellings
        claim(unit.name, unit.code)
        claim(unit.plural or _plural(unit.name) or "", unit.code)
        for spelling in unit.spellings:
            claim(spelling, unit.code)
            derived = _plural(spelling)
            if derived is not None and not spelling.endswith(("s", "c", "f")):
                claim(derived, unit.code)
    return index


_INDEX: dict[str, str] = _build_index()


def ucum_unit(code: str) -> UcumUnit | None:
    """The curated entry for an exact (case-sensitive) UCUM code, or None."""
    return _BY_CODE.get(code.strip())


def _resolve_token(token: str) -> UcumUnit | None:
    """Resolve one token: an exact code, a misnomer, or a miscased code."""
    token = token.strip()
    if token == "":
        return None
    exact = _BY_CODE.get(token)
    if exact is not None:
        return exact
    code = _INDEX.get(_normalize(token))
    return _BY_CODE.get(code) if code is not None else None


def _composed(code: str, name: str) -> UcumUnit:
    return _BY_CODE.get(code) or UcumUnit(code, name)


def suggest_ucum(raw: str) -> UcumUnit | None:
    """The UCUM unit an informal spelling means, or ``None``.

    Returns ``None`` when the text already *is* the suggested code, and when
    nothing resolves — a valid code outside the curated subset stays silent
    rather than guessed at.
    """
    raw = raw.strip()
    if raw == "":
        return None

    unit = _resolve_token(raw)
    if unit is None:
        key = _normalize(raw)
        if key.startswith("per "):
            base = _resolve_token(key[4:])
            if base is not None:
                unit = _composed(f"/{base.code}", f"per {base.name}")
        else:
            parts = key.split(" per ")
            if len(parts) != 2:
                parts = key.split("/")
            if len(parts) == 2:
                left, right = _resolve_token(parts[0]), _resolve_token(parts[1])
                if left is not None and right is not None:
                    unit = _composed(
                        f"{left.code}/{right.code}", f"{left.name} per {right.name}"
                    )

    if unit is None or unit.code == raw:
        return None
    return unit
