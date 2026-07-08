"""Render the dictionary model to a self-contained HTML page."""

from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment, select_autoescape

from .markdown import render_description
from .model import Dictionary
from .precondition import render_precondition

_TEMPLATE = files("dd_printer.templates").joinpath("dictionary.html.j2").read_text(
    encoding="utf-8"
)
_CSS = files("dd_printer.static").joinpath("dictionary.css").read_text(encoding="utf-8")

# The template injects pre-rendered HTML via `| safe`, so autoescape is on for
# everything else (labels, ids, cell values) to prevent accidental HTML/markup.
_env = Environment(autoescape=select_autoescape(default=True))


def _toc_entries(dictionary: Dictionary) -> list[dict]:
    """One contents entry per section, reflecting the ``Parent/Child`` paths.

    Sections use a ``Parent/Child`` path convention (seen in real
    dictionaries); the contents indents a child under its parent. Each entry
    has: ``index`` (1-based, matching the ``#section-N`` anchor), ``depth``
    (indent level), ``name`` (the leaf segment), and ``parent`` — the parent
    path shown as muted context *only when it is needed to disambiguate*:
    when the same leaf name occurs under more than one parent (so the two
    ``Antigen``s under ``Sample`` and the misspelled ``Sampe`` are
    distinguishable), or when the parent section is not the entry directly
    above (so an orphaned child is not silently filed under an unrelated
    preceding section).

    Indentation follows the *path*, not mere position: a child's depth is the
    number of ``/`` separators in its name, independent of what precedes it.
    """
    leaf_counts: dict[str, int] = {}
    for section in dictionary.sections:
        leaf = section.name.split("/")[-1].strip() or section.name
        leaf_counts[leaf] = leaf_counts.get(leaf, 0) + 1

    entries = []
    previous_path = ""
    for index, section in enumerate(dictionary.sections, start=1):
        segments = section.name.split("/")
        leaf = segments[-1].strip() or section.name
        parent_path = "/".join(segments[:-1])
        # Show the parent as context when the leaf is ambiguous, or when this
        # child does not sit directly under its parent in the listing.
        ambiguous = leaf_counts[leaf] > 1
        orphaned = bool(parent_path) and previous_path != parent_path
        entries.append(
            {
                "index": index,
                "depth": len(segments) - 1,
                "name": leaf,
                "count": len(section.records),
                "parent": parent_path.replace("/", " › ") if (ambiguous or orphaned) else "",
            }
        )
        previous_path = section.name
    return entries


def render_html(dictionary: Dictionary) -> str:
    """Render the dictionary to a single self-contained HTML document."""
    template = _env.from_string(_TEMPLATE)
    # Attach rendered description/notes HTML to each record for the template.
    for record in dictionary.records:
        record.description_html = render_description(
            record.description, record, dictionary
        )
        record.notes_html = render_description(record.notes, record, dictionary)
        record.precondition_html = render_precondition(record.precondition, dictionary)
    return template.render(
        dictionary=dictionary, css=_CSS, toc_entries=_toc_entries(dictionary)
    )
