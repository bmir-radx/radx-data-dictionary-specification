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
    """One contents entry per section, with the nesting depth of its path.

    Sections use a ``Parent/Child`` path convention (seen in real
    dictionaries); the contents indents a child under its parent by splitting
    on ``/``. ``depth`` is the number of path separators, ``name`` the last
    segment (the parent context is conveyed by indentation), and ``index``
    the 1-based section position matching the ``#section-N`` anchor.
    """
    entries = []
    for index, section in enumerate(dictionary.sections, start=1):
        path = section.name.split("/")
        entries.append(
            {
                "index": index,
                "depth": len(path) - 1,
                "name": path[-1].strip() or section.name,
                "count": len(section.records),
            }
        )
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
