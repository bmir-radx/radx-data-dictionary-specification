"""Tests for term-name annotation.

The OLS4 network lookup itself is not exercised here (tests stay offline); we
test the CURIE->IRI expansion and the YAML comment-annotation pass, which are
the parts with logic worth pinning down.
"""

from radx_dd_converter.emit import _annotate_term_lines
from radx_dd_converter.terms_lookup import _to_iri


def test_to_iri_expands_obo_curie():
    assert _to_iri("MONDO:0004979") == "http://purl.obolibrary.org/obo/MONDO_0004979"
    assert _to_iri("NCIT:C25150") == "http://purl.obolibrary.org/obo/NCIT_C25150"


def test_to_iri_passes_through_full_iri():
    iri = "http://purl.obolibrary.org/obo/UBERON_0001836"
    assert _to_iri(iri) == iri


def test_to_iri_rejects_non_curie():
    assert _to_iri("just text") is None
    assert _to_iri("has/slash:0001") is None


def test_annotate_meaning_and_list_lines():
    text = (
        "enums:\n"
        "  E:\n"
        "    permissible_values:\n"
        "      '0':\n"
        "        meaning: UBERON:0001836\n"
        "attributes:\n"
        "  age:\n"
        "    related_mappings:\n"
        "    - PATO:0000011\n"
    )
    out = _annotate_term_lines(
        text, {"UBERON:0001836": "saliva", "PATO:0000011": "age"}
    )
    assert "meaning: UBERON:0001836  # saliva" in out
    assert "- PATO:0000011  # age" in out


def test_annotate_leaves_block_scalar_text_untouched():
    text = (
        "    description: |\n"
        "      A sentence mentioning PATO:0000011 inline.\n"
    )
    out = _annotate_term_lines(text, {"PATO:0000011": "age"})
    assert "inline.  #" not in out
    assert out == text  # nothing changed


def test_annotate_skips_unknown_terms_and_existing_comments():
    text = "    - PATO:0000011  # already commented\n    - NCIT:C1\n"
    out = _annotate_term_lines(text, {"PATO:0000011": "age"})
    # existing comment preserved, not doubled
    assert out.count("#") == 1
    # NCIT:C1 not in labels -> untouched
    assert "NCIT:C1\n" in out
