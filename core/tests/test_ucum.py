"""Tests for the UCUM suggestion module (curated codes + misnomers)."""

from dd_core import UCUM_UNITS, suggest_ucum, ucum_unit


def test_exact_code_resolves_and_gets_no_suggestion():
    assert ucum_unit("mL").name == "milliliter"
    assert ucum_unit("mm[Hg]").name == "millimeter of mercury"
    assert suggest_ucum("mL") is None  # already the code


def test_no_duplicate_codes_in_curated_list():
    codes = [u.code for u in UCUM_UNITS]
    assert len(set(codes)) == len(codes)


def test_names_plurals_and_spellings_resolve():
    assert suggest_ucum("year").code == "a"
    assert suggest_ucum("years").code == "a"        # derived plural
    assert suggest_ucum("inches").code == "[in_i]"  # irregular plural
    assert suggest_ucum("litres").code == "L"       # regional spelling
    assert suggest_ucum("gm").code == "g"           # abbreviation
    assert suggest_ucum("bpm").code == "{beats}/min"
    assert suggest_ucum("BMI").code == "kg/m2"


def test_normalisation_folds_symbols_periods_and_case():
    assert suggest_ucum("µg").code == "ug"          # micro sign
    assert suggest_ucum("μg").code == "ug"          # greek mu
    assert suggest_ucum("kg/m²").code == "kg/m2"    # superscript
    assert suggest_ucum("kg/m^2").code == "kg/m2"   # caret
    assert suggest_ucum("hrs.").code == "h"         # trailing period
    assert suggest_ucum("ml").code == "mL"          # case fix
    assert suggest_ucum("MMHG").code == "mm[Hg]"


def test_compositional_per_and_slash_forms():
    assert suggest_ucum("per year").code == "/a"
    assert suggest_ucum("per annum").code == "/a"
    assert suggest_ucum("mg per dl").code == "mg/dL"
    assert suggest_ucum("mcg/ml").code == "ug/mL"
    # Never written anywhere in the tables — resolved from the parts.
    composed = suggest_ucum("micrograms per decilitre")
    assert composed.code == "ug/dL"
    assert composed.name == "microgram per deciliter"


def test_multiword_names_pluralise_on_the_head_noun():
    assert suggest_ucum("milligrams per deciliter").code == "mg/dL"


def test_unknown_and_valid_exotic_codes_stay_silent():
    assert suggest_ucum("furlongs") is None
    assert suggest_ucum("nmol/L") is None  # valid UCUM, outside the subset
    assert suggest_ucum("") is None
    assert suggest_ucum("   ") is None
