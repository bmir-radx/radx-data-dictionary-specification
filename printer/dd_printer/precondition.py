"""Render a Precondition expression as rich HTML.

Instead of showing the raw grammar text, the expression is rendered with the
page's own visual vocabulary: field references become clickable record-id
badges (linking to the referenced card), literal values become choice-value
badges, and where the referenced field enumerates its values the choice's
human-readable label is shown after the value — so ``smoker = "1"`` renders
as *smoker is 1 (Yes)*. The raw grammar text is kept as a tooltip.
"""

from __future__ import annotations

from dd_converter.grammar import And, Contains, InSet, Or, parse_precondition
from markupsafe import escape

from .model import Dictionary, Record

# Ordering comparators shown as symbols (escaped where HTML needs it).
_SYMBOLS = {"<": "&lt;", "<=": "&le;", ">": "&gt;", ">=": "&ge;"}


def render_precondition(text: str, dictionary: Dictionary) -> str:
    """The precondition ``text`` as inline HTML, or ``""`` for no condition."""
    node = parse_precondition(text)  # validated at load; parses cleanly
    if node is None:
        return ""
    by_id = {record.id: record for record in dictionary.records}
    return (
        f'<span class="record__precondition" title="{escape(text)}">'
        f"{_node_html(node, by_id)}</span>"
    )


def _node_html(node, by_id: dict[str, Record]) -> str:
    if isinstance(node, (And, Or)):
        keyword = " <em>and</em> " if isinstance(node, And) else " <em>or</em> "
        parts = []
        for clause in node.clauses:
            clause_html = _node_html(clause, by_id)
            # An `or` nested inside an `and` needs its grouping shown.
            if isinstance(node, And) and isinstance(clause, Or):
                clause_html = f"({clause_html})"
            parts.append(clause_html)
        return keyword.join(parts)
    return _atom_html(node, by_id)


def _atom_html(atom, by_id: dict[str, Record]) -> str:
    field = _field_html(atom.field, by_id)
    if isinstance(atom, Contains):
        return f"{field} includes {_value_html(atom.field, atom.value, by_id)}"
    if isinstance(atom, InSet):
        values = ", ".join(_value_html(atom.field, v, by_id) for v in atom.values)
        return f"{field} is one of {values}"
    # Comparison.
    if atom.op == "=":
        return f"{field} is {_value_html(atom.field, atom.value, by_id)}"
    if atom.op == "<>" and atom.value == "":
        return f"{field} is not blank"
    if atom.op == "<>":
        return f"{field} is not {_value_html(atom.field, atom.value, by_id)}"
    return f"{field} {_SYMBOLS[atom.op]} {_value_html(atom.field, atom.value, by_id)}"


def _field_html(field_id: str, by_id: dict[str, Record]) -> str:
    """A field reference as a record-id badge, linked when the record exists."""
    if field_id in by_id:
        return f'<a href="#{escape(field_id)}" class="record__id badge">{escape(field_id)}</a>'
    return f'<span class="badge record__id">{escape(field_id)}</span>'


def _value_html(field_id: str, value: str, by_id: dict[str, Record]) -> str:
    """A literal as a choice-value badge, labelled when the field enumerates it."""
    badge = f'<span class="badge choice__value">{escape(value)}</span>'
    referenced = by_id.get(field_id)
    if referenced:
        label = next(
            (c.label for c in referenced.choices if c.value == value and c.label), None
        )
        if label and label != value:
            badge += f" <em>({escape(label)})</em>"
    return badge
