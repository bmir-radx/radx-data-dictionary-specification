"""Render a record's Markdown description to HTML, with dictionary-aware enrichment.

Before the Markdown is rendered, two enrichments rewrite backtick-quoted spans:

* a backtick-quoted **record id** that exists in the dictionary
  (`` `age` ``) becomes an in-page cross-reference link to that record;
* a backtick-quoted **choice value** of the current record (`` `0` ``) becomes a
  styled badge, marked when the value is a missing-value code.

The enriched text is then rendered as CommonMark (with autolinking) into HTML.
Injected spans/links pass through because HTML is enabled in the renderer.
"""

from __future__ import annotations

import html

from markdown_it import MarkdownIt

from .model import Dictionary, Record

# CommonMark renderer with raw-HTML passthrough (for the injected spans) and
# linkify (bare URLs become links, matching the Java autolink extension). The
# commonmark preset doesn't turn on the linkify *rule* by default, so enable it.
_md = MarkdownIt("commonmark", {"html": True, "linkify": True}).enable("linkify")


def _link_record_ids(text: str, dictionary: Dictionary) -> str:
    """Turn `` `id` `` into a cross-reference link for every known record id."""
    for record_id in dictionary.ids():
        token = f"`{record_id}`"
        link = f'<a href="#{record_id}" class="record__id badge">{record_id}</a>'
        text = text.replace(token, link)
    return text


def _badge_choice_values(text: str, record: Record) -> str:
    """Turn `` `value` `` into a badge for each of the record's choice values."""
    for choice in record.choices:
        token = f"`{choice.value}`"
        extra = " choice__value--missing-value-code" if choice.is_missing_value_code else ""
        badge = (
            f'<span class="badge choice__value{extra}" '
            f'title="{html.escape(choice.value, quote=True)}">{choice.value}</span>'
        )
        text = text.replace(token, badge)
    return text


def render_description(text: str, record: Record, dictionary: Dictionary) -> str:
    """Enrich and render a record's description Markdown to an HTML string."""
    if not text:
        return ""
    # Choice-value badges first: a choice value is more specific than an id, and
    # linking ids afterwards won't match the already-substituted badge markup.
    enriched = _badge_choice_values(text, record)
    enriched = _link_record_ids(enriched, dictionary)
    return _md.render(enriched)
