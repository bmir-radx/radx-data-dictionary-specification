"""Parse the RADx enumeration and missing-value-codes cell grammars.

Both the ``Enumeration`` and ``MissingValueCodes`` fields use the same cell
syntax::

    "value"=[label](optionalTermIri) | "value"=[label] | ...

This module turns such a cell into a list of :class:`EnumItem` objects. White
space around the ``|`` and ``=`` separators is insignificant; white space inside
a quoted value or boxed label is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lark import Lark, Tree
from lark.exceptions import LarkError

_GRAMMAR_PATH = Path(__file__).with_name("enumeration.lark")

# One shared parser instance. LALR is sufficient for this grammar and is fast.
_parser = Lark(
    _GRAMMAR_PATH.read_text(encoding="utf-8"),
    start="enumeration",
    parser="lalr",
)


class ParseError(ValueError):
    """Raised when a cell does not conform to the enumeration grammar."""


@dataclass(frozen=True)
class EnumItem:
    """A single value-label pair from an enumeration or missing-value-codes cell.

    ``value`` is the unquoted value (what appears, unquoted, in a datafile).
    ``label`` is the human-readable label. ``iri`` is the optional ontology term
    identifier attached to the value (a full IRI or a compact OBO id), or
    ``None`` when the pair carries no term.
    """

    value: str
    label: str
    iri: str | None = None


def _strip_delims(token: str, open_ch: str, close_ch: str) -> str:
    """Remove the surrounding delimiter characters from a terminal's text."""
    assert token.startswith(open_ch) and token.endswith(close_ch), token
    return token[len(open_ch) : len(token) - len(close_ch)]


def _tree_to_items(tree: Tree) -> list[EnumItem]:
    items: list[EnumItem] = []
    for pair in tree.children:
        # Each `pair` is a Tree whose children are: value, label, [bracketed_iri]
        value_text = label_text = None
        iri_text: str | None = None
        for child in pair.children:
            if not isinstance(child, Tree):
                continue
            (leaf,) = child.children  # each of value/label/bracketed_iri holds one token
            text = str(leaf)
            if child.data == "value":
                value_text = _strip_delims(text, '"', '"')
            elif child.data == "label":
                label_text = _strip_delims(text, "[", "]")
            elif child.data == "bracketed_iri":
                iri_text = _strip_delims(text, "(", ")").strip()
        items.append(EnumItem(value=value_text, label=label_text, iri=iri_text))
    return items


def parse_enumeration(cell: str) -> list[EnumItem]:
    """Parse an ``Enumeration`` cell into a list of :class:`EnumItem`.

    A blank or whitespace-only cell yields an empty list. Raises
    :class:`ParseError` if the cell is non-blank but malformed.
    """
    if cell is None or cell.strip() == "":
        return []
    try:
        tree = _parser.parse(cell)
    except LarkError as exc:
        raise ParseError(f"Malformed enumeration cell {cell!r}: {exc}") from exc
    return _tree_to_items(tree)


def parse_missing_value_codes(cell: str) -> list[EnumItem]:
    """Parse a ``MissingValueCodes`` cell.

    Identical grammar to :func:`parse_enumeration`; provided as a separate name
    because the two fields are semantically distinct (see the specification).
    """
    return parse_enumeration(cell)
