"""Render the dictionary model to a self-contained HTML page."""

from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment, select_autoescape

from .markdown import render_description
from .model import Dictionary

_TEMPLATE = files("dd_printer.templates").joinpath("dictionary.html.j2").read_text(
    encoding="utf-8"
)
_CSS = files("dd_printer.static").joinpath("dictionary.css").read_text(encoding="utf-8")

# The template injects pre-rendered HTML via `| safe`, so autoescape is on for
# everything else (labels, ids, cell values) to prevent accidental HTML/markup.
_env = Environment(autoescape=select_autoescape(default=True))


def render_html(dictionary: Dictionary) -> str:
    """Render the dictionary to a single self-contained HTML document."""
    template = _env.from_string(_TEMPLATE)
    # Attach rendered description/notes HTML to each record for the template.
    for record in dictionary.records:
        record.description_html = render_description(
            record.description, record, dictionary
        )
        record.notes_html = render_description(record.notes, record, dictionary)
    return template.render(dictionary=dictionary, css=_CSS)
