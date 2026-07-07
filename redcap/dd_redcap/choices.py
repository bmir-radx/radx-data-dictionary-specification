"""Parse REDCap's choices notation.

A REDCap ``Choices`` cell lists permissible values as ``value, label`` pairs
separated by ``|`` — or by ``;`` in older exports that contain no pipe::

    1, Yes | 2, No | 3, Maybe

Only the *first* comma splits value from label, so labels keep their own
commas (``1, Less than $15,000``). An item with no comma at all is used as
both value and label.
"""

from __future__ import annotations


def parse_choices(cell: str | None) -> dict[str, str]:
    """Parse a Choices cell into an ordered ``{value: label}`` mapping.

    ::

        >>> parse_choices("1, Yes | 2, No")
        {'1': 'Yes', '2': 'No'}
        >>> parse_choices("1, Less than $15,000 | 2, $15,000 - $19,999")
        {'1': 'Less than $15,000', '2': '$15,000 - $19,999'}
        >>> parse_choices("23")
        {'23': '23'}
        >>> parse_choices("")
        {}
    """
    if cell is None or not cell.strip():
        return {}
    text = cell.strip()
    separator = "|" if "|" in text else ";"
    choices: dict[str, str] = {}
    for item in text.split(separator):
        item = item.strip()
        if not item:
            continue
        value, comma, label = item.partition(",")
        if comma:
            choices[value.strip()] = label.strip()
        else:
            choices[item] = item
    return choices
