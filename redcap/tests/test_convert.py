"""Converter tests: REDCap rows -> DataElements."""

import io

import pytest
from dd_api import DataDictionary
from dd_redcap import ConversionError, convert_redcap

HEADER = (
    "Variable / Field Name,Form Name,Section Header,Field Type,Field Label,"
    '"Choices, Calculations, OR Slider Labels",Field Note,'
    "Text Validation Type OR Show Slider Number,Text Validation Min,"
    "Text Validation Max,Identifier?,Branching Logic (Show field only if...),"
    "Required Field?,Custom Alignment,Question Number (surveys only),"
    "Matrix Group Name,Matrix Ranking?,Field Annotation"
)


def _convert(rows, **kwargs):
    return convert_redcap(io.StringIO(HEADER + "\n" + "\n".join(rows) + "\n"), **kwargs)


def test_basic_text_field():
    dd = _convert(["age,form1,,text,Age in years,,,integer,,,,,,,,,,"])
    element = dd["age"]
    assert element.label == "Age in years"
    assert element.datatype == "integer"
    assert element.cardinality == "single"
    assert not element.is_enumerated


def test_field_note_appended_to_label():
    dd = _convert(["age,form1,,text,Age,,in years,integer,,,,,,,,,,"])
    assert dd["age"].label == "Age (in years)"


def test_choices_become_enumeration():
    dd = _convert(['sex,form1,,radio,Sex,"1, Male | 2, Female",,,,,,,,,,,,'])
    element = dd["sex"]
    assert [(c.value, c.label) for c in element.enumeration] == [("1", "Male"), ("2", "Female")]
    assert element.datatype == "integer"  # first choice value is all digits
    assert "2 permissible integer values" in element.description


def test_non_numeric_choices_are_strings():
    dd = _convert(['grp,form1,,dropdown,Group,"a, Alpha | b, Beta",,,,,,,,,,,,'])
    assert dd["grp"].datatype == "string"


def test_checkbox_is_multivalued():
    dd = _convert(['sym,form1,,checkbox,Symptoms,"1, Cough | 2, Fever",,,,,,,,,,,,'])
    assert dd["sym"].is_multivalued


def test_sections_carry_forward():
    dd = _convert(
        [
            "a,form1,Demographics,text,A,,,,,,,,,,,,,",
            "b,form1,,text,B,,,,,,,,,,,,,",
            "c,form1,Vitals,text,C,,,,,,,,,,,,,",
        ]
    )
    assert [e.section for e in dd] == ["Demographics", "Demographics", "Vitals"]


def test_descriptive_rows_are_skipped():
    dd = _convert(
        [
            "blurb,form1,,descriptive,Please answer the following,,,,,,,,,,,,,",
            "a,form1,,text,A,,,,,,,,,,,,,",
        ]
    )
    assert dd.ids == ("a",)


def test_branching_logic_explained_with_choice_label():
    dd = _convert(
        [
            'smoker,form1,,radio,Do you smoke?,"0, No | 1, Yes",,,,,,,,,,,,',
            "packs,form1,,text,Packs per day,,,number,,,,[smoker] = '1',,,,,,",
        ]
    )
    description = dd["packs"].description
    assert "only records a non-blank value if" in description
    assert "the value of `smoker` is `1`" in description
    assert '_"Yes"_' in description
    assert dd["packs"].datatype == "decimal"  # validation "number" -> decimal


def test_unrecognised_branching_logic_quoted():
    dd = _convert(["x,form1,,text,X,,,,,,,[bmi] > 30,,,,,,"])
    assert "the condition `[bmi] > 30` evaluates to true" in dd["x"].description


def test_none_of_the_above_annotation():
    dd = _convert(
        [
            'sym,form1,,checkbox,Symptoms,"1, Cough | 99, None",,,,,,,,,,,,'
            "@NONEOFTHEABOVE = '99'",
        ]
    )
    element = dd["sym"]
    assert "`99` is mutually exclusive with any other values" in element.description
    assert element.notes is None  # the action is explained, not kept as a note


def test_other_annotations_become_notes():
    dd = _convert(["a,form1,,text,A,,,,,,,,,,,,,@HIDDEN | @READONLY"])
    assert dd["a"].notes == "@HIDDEN\n\n@READONLY"


def test_provenance_fills_every_element():
    dd = _convert(["a,form1,,text,A,,,,,,,,,,,,,"], provenance="My Study")
    assert dd["a"].provenance == "My Study"


def test_output_round_trips_through_the_model():
    dd = _convert(['sex,form1,,radio,Sex,"1, Male | 2, Female",,,,,,,,,,,,'])
    reloaded = DataDictionary.load(io.StringIO(dd.to_csv()))
    assert reloaded.elements == dd.elements


def test_not_a_redcap_file_raises():
    with pytest.raises(ConversionError, match="Variable / Field Name"):
        convert_redcap(io.StringIO("Id,Label,Datatype\na,A,string\n"))


def test_synonym_headers_accepted():
    text = "Variable,Label,Type\nage,Age,text\n"
    dd = convert_redcap(io.StringIO(text))
    assert dd["age"].label == "Age"
    assert dd["age"].datatype == "string"


# --- precondition / required ---------------------------------------------------

def test_branching_logic_becomes_precondition():
    dd = _convert(
        [
            'smoker,form1,,radio,Do you smoke?,"0, No | 1, Yes",,,,,,,y,,,,,',
            "packs,form1,,text,Packs per day,,,number,,,,[smoker] = '1',y,,,,,",
        ]
    )
    assert dd["packs"].precondition == 'smoker = "1"'
    assert dd["packs"].required
    assert dd["smoker"].required and dd["smoker"].precondition is None


def test_checkbox_branching_becomes_contains():
    dd = _convert(
        [
            'sym,form1,,checkbox,Symptoms,"1, Cough | 3, Headache",,,,,,,,,,,,',
            "detail,form1,,text,Detail,,,,,,,[sym(3)] = '1',,,,,,",
        ]
    )
    assert dd["detail"].precondition == 'sym contains "3"'


def test_uniform_or_branching_translates():
    dd = _convert(
        [
            'x,form1,,radio,X,"1, A | 2, B",,,,,,,,,,,,',
            "y,form1,,text,Y,,,,,,,[x] = '1' or [x] = '2',,,,,,",
        ]
    )
    assert dd["y"].precondition == 'x = "1" or x = "2"'


def test_untranslatable_branching_stays_prose_only():
    dd = _convert(["y,form1,,text,Y,,,,,,,[bmi] > 30,,,,,,"])
    assert dd["y"].precondition is None
    assert "the condition `[bmi] > 30` evaluates to true" in dd["y"].description


def test_dangling_reference_precondition_dropped():
    # [ghost] is not a field in the dictionary -> precondition must not dangle.
    dd = _convert(["y,form1,,text,Y,,,,,,,[ghost] = '1',,,,,,"])
    assert dd["y"].precondition is None


def test_mixed_connectives_not_translated():
    dd = _convert(
        [
            'a,form1,,radio,A,"1, X",,,,,,,,,,,,',
            'b,form1,,radio,B,"1, X",,,,,,,,,,,,',
            "y,form1,,text,Y,,,,,,,[a] = '1' and [b] = '1' or [a] = '2',,,,,,",
        ]
    )
    assert dd["y"].precondition is None


def test_windows_1252_export_reads(tmp_path):
    # Real REDCap exports are often Excel-saved cp1252 (0xa0 = non-breaking space).
    path = tmp_path / "export.csv"
    path.write_bytes("Variable,Label,Type\nage,Age\xa0(years),text\n".encode("cp1252"))
    dd = convert_redcap(path)
    assert dd["age"].label == "Age\xa0(years)"


def test_duplicate_variables_raise_unless_allowed():
    rows = ["a,form1,,text,A,,,,,,,,,,,,,", "a,form2,,text,A again,,,,,,,,,,,,,"]
    with pytest.raises(ValueError, match="duplicate"):
        _convert(rows)
    dd = _convert(rows, allow_duplicates=True)
    assert dd.ids == ("a",)
    assert dd["a"].label == "A"  # first occurrence wins
