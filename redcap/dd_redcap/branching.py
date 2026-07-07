"""Explain REDCap branching logic in prose.

A REDCap field with *branching logic* is only shown (and so only filled in)
when a condition on other fields holds, e.g. ``[smoker] = '1'`` or, for one
checkbox choice, ``[symptoms(3)] = '1'``. Datafile readers see those fields
as mysteriously blank; this module turns the condition into a sentence for
the generated description, looking up what the referenced choice value
*means* in the referenced field's own choice list::

    This variable only records a non-blank value if the value of `smoker`
    is `1`, _"Yes"_.

Clauses joined by ``and`` are explained clause by clause; anything the three
recognised patterns do not match is quoted verbatim as a condition.
"""

from __future__ import annotations

import re

from . import headers
from .choices import parse_choices
from .headers import RedCapSheet

# [field(3)] = '1'   — one choice of a checkbox field is ticked
_CHECKBOX_CHOICE = re.compile(r"\[([A-Za-z0-9_]+)\((\d+)\)\]\s*=\s*['\"]?1[\"']?")
# [field] = '2'      — a radio/dropdown field has a particular value
_FIELD_EQUALS = re.compile(r"\[([A-Za-z0-9_]+)\]\s*=\s*['\"]?(\d+)['\"]?")
# [field] <> ''      — a field is non-blank
_FIELD_NON_EMPTY = re.compile(r"\[([A-Za-z0-9_]+)\]\s*<>\s*''")


def explain_branching_logic(sheet: RedCapSheet, row: list[str]) -> str:
    """A prose explanation of the row's branching logic, or ``""`` if none."""
    logic = sheet.get(row, headers.BRANCHING_LOGIC).strip()
    if not logic:
        return ""
    explained = " and ".join(
        _explain_clause(clause.strip(), sheet) for clause in logic.split(" and ")
    )
    return f"This variable only records a non-blank value if {explained}."


def _explain_clause(clause: str, sheet: RedCapSheet) -> str:
    checkbox = _CHECKBOX_CHOICE.fullmatch(clause)
    equals = _FIELD_EQUALS.fullmatch(clause)
    non_empty = _FIELD_NON_EMPTY.fullmatch(clause)
    if checkbox:
        field, value = checkbox.group(1), checkbox.group(2)
    elif equals:
        field, value = equals.group(1), equals.group(2)
    elif non_empty:
        field, value = non_empty.group(1), "empty"
    else:
        # Fall back to just quoting the expression.
        return f"the condition `{clause}` evaluates to true"

    label = _choice_label(sheet, field, value)
    quoted_label = f'_"{label}"_' if label is not None else ""
    return f"the value of `{field}` is `{value}`, {quoted_label}"


def _choice_label(sheet: RedCapSheet, field_id: str, value: str) -> str | None:
    """What ``value`` means in ``field_id``'s choice list (its label).

    Falls back to the value itself when the referenced field exists but does
    not list the value; ``None`` when the field is not in the sheet at all.
    """
    referenced_row = sheet.row_with_id(field_id)
    if referenced_row is None:
        return None
    choices = parse_choices(sheet.get(referenced_row, headers.CHOICES))
    return choices.get(value, value)
