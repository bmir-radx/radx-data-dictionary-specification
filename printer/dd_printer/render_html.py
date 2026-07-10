"""Render the dictionary model to a self-contained HTML page."""

from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment, select_autoescape

from .markdown import render_description
from .model import Dictionary
from .precondition import render_precondition

# Resolve resources relative to the dd_printer package itself, not to the
# templates/static subdirectories: those have no __init__.py, and on Python 3.9
# importlib.resources.files() cannot resolve such a non-package subdirectory
# (it raises TypeError). The parent package always has a concrete location.
_TEMPLATE = (
    files("dd_printer").joinpath("templates", "dictionary.html.j2").read_text(encoding="utf-8")
)
_CSS = files("dd_printer").joinpath("static", "dictionary.css").read_text(encoding="utf-8")

# The template injects pre-rendered HTML via `| safe`, so autoescape is on for
# everything else (labels, ids, cell values) to prevent accidental HTML/markup.
_env = Environment(autoescape=select_autoescape(default=True))


def _toc_entries(dictionary: Dictionary) -> list[dict]:
    """One contents entry per section, reflecting the ``Parent/Child`` paths.

    Sections use a ``Parent/Child`` path convention (seen in real
    dictionaries), but the sheet's row order need not agree with that tree —
    a parent's children may be split apart by unrelated sections. The
    contents indents a child **only when it genuinely continues its parent's
    group** (the parent, or a deeper descendant of it, is the section
    immediately above). An *orphaned* child — one whose parent is not open in
    the run directly above it — is rendered flush-left with its full path as
    its name, so indentation never implies a parent the ordering contradicts.

    Each entry has: ``index`` (1-based, matching the ``#section-N`` anchor),
    ``depth`` (indent level; 0 for a top-level or orphaned entry), ``name``
    (the leaf for a nested entry, the full path for an orphaned one), and
    ``parent`` (the ancestor path shown as muted context on a genuinely
    nested child, distinguishing same-leaf siblings such as the two
    ``Antigen``s under ``Sample`` and the misspelled ``Sampe``).
    """
    # How many sections share each leaf name — a leaf appearing under more
    # than one parent is ambiguous and needs its parent shown for context.
    leaf_counts: dict[str, int] = {}
    for section in dictionary.sections:
        leaf = section.name.split("/")[-1].strip() or section.name
        leaf_counts[leaf] = leaf_counts.get(leaf, 0) + 1

    # The ancestor path prefixes left open by the previous entry's chain. A
    # child is "nested" only if its parent path is among these — i.e. it
    # directly continues a run under that parent.
    open_prefixes: set[str] = {""}
    entries = []
    for index, section in enumerate(dictionary.sections, start=1):
        segments = section.name.split("/")
        parent_path = "/".join(segments[:-1])
        leaf = segments[-1].strip() or section.name
        nested = bool(parent_path) and parent_path in open_prefixes
        if nested:
            entry = {
                "index": index,
                "depth": len(segments) - 1,
                "name": leaf,
                "count": len(section.records),
                # Show the parent only to disambiguate a repeated leaf name.
                "parent": parent_path.replace("/", " › ") if leaf_counts[leaf] > 1 else "",
            }
            # Extend the open run with this child and its ancestors.
            for depth in range(len(segments)):
                open_prefixes.add("/".join(segments[: depth + 1]))
        else:
            # Top-level or orphaned: render flush-left with the full path.
            entry = {
                "index": index,
                "depth": 0,
                "name": section.name,
                "count": len(section.records),
                "parent": "",
            }
            # A top-level section (no path) opens itself as a nestable parent.
            # An orphaned Parent/Child does NOT resurrect its absent parent —
            # otherwise a following same-path sibling would nest under it,
            # rendering an orphan run raggedly (some flush-left, some indented).
            open_prefixes = {"", section.name} if not parent_path else {""}
        entries.append(entry)
    return entries


def render_html(dictionary: Dictionary, *, term_labels: dict[str, str] | None = None) -> str:
    """Render the dictionary to a single self-contained HTML document.

    ``term_labels`` maps ontology term identifiers to human-readable names;
    when given, each term/meaning badge shows its label beside it. The CLI's
    ``--annotate-terms`` resolves this map; without it, terms render as bare
    identifiers (the default, so rendering stays offline and deterministic).
    """
    template = _env.from_string(_TEMPLATE)
    # Attach rendered description/notes HTML to each record for the template.
    for record in dictionary.records:
        record.description_html = render_description(
            record.description, record, dictionary
        )
        record.notes_html = render_description(record.notes, record, dictionary)
        record.precondition_html = render_precondition(record.precondition, dictionary)
    return template.render(
        dictionary=dictionary,
        css=_CSS,
        toc_entries=_toc_entries(dictionary),
        term_labels=term_labels or {},
    )
