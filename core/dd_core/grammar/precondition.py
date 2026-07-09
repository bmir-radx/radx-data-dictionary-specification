"""Parse the ``Precondition`` cell grammar.

A precondition says when a field holds a value, as a boolean expression over
other fields in the same dictionary (see "Field: Precondition" in the
specification)::

    consented = "1" and age >= 18
    status in {"1", "2"} or (symptoms contains "3" and severity > 2)

:func:`parse_precondition` turns such a cell into a small typed tree:
:class:`Comparison`, :class:`InSet` and :class:`Contains` atoms, combined by
:class:`And` / :class:`Or`. Literal values are kept as the strings written in
the cell (quotes stripped); interpreting them against a field's datatype is
an evaluator's job, not the parser's.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

from lark import Lark, Tree
from lark.exceptions import LarkError

from .parse import ParseError

_GRAMMAR_PATH = Path(__file__).with_name("precondition.lark")

_parser = Lark(
    _GRAMMAR_PATH.read_text(encoding="utf-8"),
    start="start",
    parser="lalr",
)


@dataclass(frozen=True)
class Comparison:
    """``field <op> literal`` — op is ``=``, ``<>``, ``<``, ``<=``, ``>`` or ``>=``.

    ``field <> ""`` (value is the empty string) is the non-blank test.
    """

    field: str
    op: str
    value: str


@dataclass(frozen=True)
class InSet:
    """``field in {"a", "b", ...}`` — the value is one of a set."""

    field: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class Contains:
    """``field contains "a"`` — a multivalued field's cell holds the value."""

    field: str
    value: str


@dataclass(frozen=True)
class And:
    """All clauses must hold."""

    clauses: tuple[Precondition, ...]


@dataclass(frozen=True)
class Or:
    """At least one clause must hold."""

    clauses: tuple[Precondition, ...]


# A runtime alias (not a lazy annotation), so `X | Y` syntax would need
# Python >= 3.10; Union keeps the package's 3.9 floor.
Precondition = Union[Comparison, InSet, Contains, And, Or]  # noqa: UP007


def parse_precondition(cell: str) -> Precondition | None:
    """Parse a ``Precondition`` cell into its expression tree.

    A blank or whitespace-only cell yields ``None`` (the field always
    applies). Raises :class:`ParseError` if the cell is non-blank but does
    not conform to the grammar.

    ::

        >>> parse_precondition('smoker = "1"')
        Comparison(field='smoker', op='=', value='1')
        >>> tree = parse_precondition('a = "1" and b > 2')
        >>> [type(clause).__name__ for clause in tree.clauses]
        ['Comparison', 'Comparison']
    """
    if cell is None or cell.strip() == "":
        return None
    try:
        tree = _parser.parse(cell)
    except LarkError as exc:
        raise ParseError(f"Malformed precondition {cell!r}: {exc}") from exc
    return _to_node(tree)


def referenced_fields(node: Precondition) -> set[str]:
    """The ids of every field the expression refers to."""
    if isinstance(node, (And, Or)):
        return set().union(*(referenced_fields(clause) for clause in node.clauses))
    return {node.field}


def atoms(node: Precondition) -> list[Comparison | InSet | Contains]:
    """Every atomic predicate in the expression, left to right."""
    if isinstance(node, (And, Or)):
        return [atom for clause in node.clauses for atom in atoms(clause)]
    return [node]


def _literal_text(token: Tree) -> str:
    (leaf,) = token.children
    text = str(leaf)
    if text.startswith('"'):
        return text[1:-1]
    return text


def _to_node(tree: Tree) -> Precondition:
    # `?rule` inlining means single-child rules never appear; a Tree here is
    # a multi-clause or_expression/and_expression, or a predicate wrapper.
    if tree.data == "or_expression":
        return Or(tuple(_to_node(child) for child in tree.children))
    if tree.data == "and_expression":
        return And(tuple(_to_node(child) for child in tree.children))
    if tree.data == "predicate":
        (inner,) = tree.children
        return _to_node(inner)
    if tree.data == "comparison":
        field, op, literal = tree.children
        return Comparison(field=str(field), op=str(op), value=_literal_text(literal))
    if tree.data == "in_set":
        field, *literals = tree.children
        return InSet(field=str(field), values=tuple(_literal_text(lit) for lit in literals))
    if tree.data == "contains":
        field, literal = tree.children
        return Contains(field=str(field), value=_literal_text(literal))
    raise AssertionError(f"unexpected parse node {tree.data!r}")  # pragma: no cover


def serialise_precondition(node: Precondition) -> str:
    """Render an expression tree back to canonical cell text.

    Canonical form: one space around keywords and comparators, string
    literals double-quoted, ``or``-clauses parenthesised inside ``and`` only
    when needed (i.e. never — ``and`` binds tighter, so nested ``Or`` inside
    ``And`` requires parentheses, which is the one case emitted).
    """
    if isinstance(node, Or):
        return " or ".join(serialise_precondition(clause) for clause in node.clauses)
    if isinstance(node, And):
        parts = []
        for clause in node.clauses:
            text = serialise_precondition(clause)
            parts.append(f"({text})" if isinstance(clause, Or) else text)
        return " and ".join(parts)
    if isinstance(node, Comparison):
        return f'{node.field} {node.op} {_quote(node.value)}'
    if isinstance(node, InSet):
        return f'{node.field} in {{{", ".join(_quote(v) for v in node.values)}}}'
    return f"{node.field} contains {_quote(node.value)}"


def _quote(value: str) -> str:
    """Bare numerals stay bare; everything else is double-quoted."""
    try:
        float(value)
        return value
    except ValueError:
        return f'"{value}"'
