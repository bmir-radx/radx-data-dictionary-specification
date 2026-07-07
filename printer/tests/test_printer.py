"""Tests for the data dictionary printer."""

import io
import json

from dd_printer.load import load_dictionary
from dd_printer.markdown import render_description
from dd_printer.render_html import render_html
from dd_printer.render_json import render_json

SAMPLE = (
    "Id,Label,Description,Section,Cardinality,Datatype,Terms,Enumeration,MissingValueCodes\n"
    "age,Age,The **age** in years.,Demographics,single,integer,PATO:0000011,,\n"
    'sex,Sex,See `age`. Value `0` is female.,Demographics,single,integer,,'
    '"""0""=[Female] | ""1""=[Male]","""-9""=[Refused]"\n'
    "sym,Symptoms,Reported symptoms,Clinical,multiple,string,,,\n"
)


def _load():
    return load_dictionary(io.StringIO(SAMPLE), title="Demo")


# --- loading / model -------------------------------------------------------

def test_sections_grouped_in_order_and_numbered():
    d = _load()
    assert [s.name for s in d.sections] == ["Demographics", "Clinical"]
    assert [r.number for r in d.records] == [1, 2, 3]
    assert [r.id for r in d.records] == ["age", "sex", "sym"]


def test_cardinality_and_enumeration_parsed():
    d = _load()
    by_id = {r.id: r for r in d.records}
    assert by_id["sym"].is_multivalued is True
    assert by_id["age"].is_multivalued is False
    choices = by_id["sex"].choices
    assert [(c.value, c.label) for c in choices] == [("0", "Female"), ("1", "Male")]


def test_loads_from_linkml_schema():
    # Round-trip the sample through the converter to a schema, then load that.
    from dd_converter import EmitOptions, emit_schema, read_data_dictionary

    rows = read_data_dictionary(io.StringIO(SAMPLE))
    schema_yaml = emit_schema(rows, EmitOptions(schema_name="demo", class_name="Record"))
    d = load_dictionary(io.StringIO(schema_yaml))
    assert [r.id for r in d.records] == ["age", "sex", "sym"]
    assert {r.id for r in d.records if r.choices} == {"sex"}


# --- markdown enrichment ---------------------------------------------------

def test_description_renders_markdown_and_id_link():
    d = _load()
    sex = {r.id: r for r in d.records}["sex"]
    html = render_description(sex.description, sex, d)
    assert '<a href="#age" class="record__id badge">age</a>' in html  # id cross-ref
    assert 'class="badge choice__value' in html  # `0` choice badge


def test_missing_value_code_badge_class():
    # A choice value that is a missing-value code gets the extra class. Put the
    # code into the enumeration so it appears as a choice and is referenced.
    csv = (
        "Id,Label,Description,Datatype,Enumeration,MissingValueCodes\n"
        'q,Q,Code `-9` means refused.,integer,"""-9""=[Refused]","""-9""=[Refused]"\n'
    )
    d = load_dictionary(io.StringIO(csv))
    rec = d.records[0]
    html = render_description(rec.description, rec, d)
    assert "choice__value--missing-value-code" in html


# --- renderers -------------------------------------------------------------

def test_html_is_self_contained_and_has_cards():
    html = render_html(_load())
    assert "<style>" in html and "cdn" not in html.lower()  # inlined CSS, no CDN
    assert html.count('class="record"') == 3
    assert 'id="age"' in html and 'id="sex"' in html


def test_json_structure():
    data = json.loads(render_json(_load()))
    assert data["title"] == "Demo"
    assert [s["name"] for s in data["sections"]] == ["Demographics", "Clinical"]
    sex = next(r for s in data["sections"] for r in s["records"] if r["id"] == "sex")
    assert sex["choices"][0]["label"] == "Female"


def test_cli_writes_html(tmp_path):
    from dd_printer.cli import main

    src = tmp_path / "d.csv"
    src.write_text(SAMPLE)
    out = tmp_path / "d.html"
    assert main([str(src), "-o", str(out)]) == 0
    assert '<article class="record"' in out.read_text()


def test_cli_format_inferred_from_json_extension(tmp_path):
    from dd_printer.cli import main

    src = tmp_path / "d.csv"
    src.write_text(SAMPLE)
    out = tmp_path / "d.json"
    assert main([str(src), "-o", str(out)]) == 0
    json.loads(out.read_text())  # valid JSON


def test_cli_missing_input_returns_2(capsys):
    from dd_printer.cli import main

    assert main(["/no/such/file.csv"]) == 2
    assert "not found" in capsys.readouterr().err


def test_precondition_renders_richly():
    import io

    from dd_printer.load import load_dictionary
    from dd_printer.render_html import render_html

    text = (
        "Id,Label,Datatype,Enumeration,Precondition,Required,Cardinality\n"
        'smoker,Do you smoke?,integer,"""0""=[No] | ""1""=[Yes]",,,\n'
        'packs,Packs,decimal,,"smoker = ""1"" and packs_known <> """"",y,\n'
        'sym,Symptoms,integer,"""3""=[Headache]",,,multiple\n'
        'detail,Detail,string,,"sym contains ""3""",,\n'
    )
    html = render_html(load_dictionary(io.StringIO(text)))
    # Field reference links to the record card; value shows its choice label.
    assert '<a href="#smoker" class="record__id badge">smoker</a> is' in html
    assert '<span class="badge choice__value">1</span> <em>(Yes)</em>' in html
    # Non-blank test reads as prose; connectives are emphasised.
    assert "is not blank" in html
    assert "<em>and</em>" in html
    # contains renders as "includes", with the referenced choice labelled.
    assert 'includes <span class="badge choice__value">3</span> <em>(Headache)</em>' in html
    # The raw grammar text survives as a tooltip.
    assert 'title="smoker = &#34;1&#34; and packs_known &lt;&gt; &#34;&#34;"' in html


def test_visual_navigation_and_badges():
    import io

    from dd_printer.load import load_dictionary
    from dd_printer.render_html import render_html

    text = (
        "Id,Label,Datatype,Section,Cardinality,Required\n"
        "a,A,string,One,single,y\n"
        "b,B,integer,Two,multiple,\n"
    )
    html = render_html(load_dictionary(io.StringIO(text)))
    # TOC with per-section counts; sections carry ids and counts.
    assert '<nav class="toc">' in html
    assert '<a href="#section-1">One</a><span class="toc__count">1</span>' in html
    assert '<span class="section__count">1 element</span>' in html
    # Default 'single' cardinality is noise and is hidden; 'multiple' shows.
    assert html.count("Cardinality") == 1 and ">multiple</span>" in html
    # Required gets its own badge class; back-to-top and anchors exist.
    assert 'class="badge record__required"' in html
    assert 'class="back-to-top"' in html
    assert 'class="record__anchor" href="#a"' in html
