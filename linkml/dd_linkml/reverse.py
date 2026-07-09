"""Reconstruct a data dictionary CSV from a LinkML schema.

This is the inverse of :mod:`emit`. It reads a schema — normally one produced
by this converter — and rebuilds the data dictionary, one row per slot of the
root class, inverting the column -> LinkML mapping.

The schema is read through :class:`linkml_runtime.SchemaView` — LinkML's own
API for resolving a schema — so equivalent syntactic representations are
normalised before inversion. A schema does not have to come from this
converter to load:

* the root class may define its fields as inline ``attributes:`` (the
  generated form) **or** as a class-level ``slots:`` list backed by top-level
  ``slots:`` definitions, refined by ``slot_usage:`` — including fields
  inherited via ``is_a``/``mixins`` and schemas split across imports;
* an enumeration may be a named enum referenced through ``any_of`` (the
  generated form), a named enum used directly as the slot's ``range:``, or an
  inline ``enum_range:``.

Only information the schema actually carries can be reconstructed: without the
converter's machine annotations, the underlying datatype of an enumerated slot
defaults to ``string`` (the annotation ``value_datatype`` normally preserves
it) and units are only recovered from ``unit_raw``.

The round-trip is *semantic*, not byte-exact: the forward conversion normalises
some text (it strips trailing whitespace from descriptions and re-joins ``Terms``
with single spaces) and re-serialises the ``Enumeration`` cell grammar, so a
reconstructed cell may be equivalent to the original without being identical.
See ``CONVERTER_PLAN.md``.
"""

from __future__ import annotations

import csv
import io
from typing import TextIO

import jsonasobj2
import yaml
from dd_core.datatypes import BUILTIN_RANGES
from dd_core.missing_values import STANDARD_ENUM_NAME
from dd_core.reader import KNOWN_COLUMNS
from linkml_runtime import SchemaView

# LinkML ranges that are not themselves valid datatype names, mapped back to
# the unique specification name that produces them (datetime -> dateTime,
# uri -> anyURI). Every other built-in range is already a valid name.
_RANGE_TO_DATATYPE = {
    linkml_range: name
    for name, linkml_range in BUILTIN_RANGES.items()
    if linkml_range not in BUILTIN_RANGES
}


def _get(obj, attr, default=None):
    """Attribute access that works on both LinkML JsonObj and plain dicts."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default) or default


def _items(mapping):
    """Iterate (key, value) over a JsonObj-or-dict mapping."""
    if mapping is None:
        return []
    return list(jsonasobj2.items(mapping))


def _annotation(slot, key: str) -> str:
    """Return the string value of a slot annotation, or ""."""
    annotations = _get(slot, "annotations", {})
    for name, ann in _items(annotations):
        if name == key:
            # An annotation serialises either as a bare value or {value: ...}.
            return str(_get(ann, "value", ann) if not isinstance(ann, str) else ann)
    return ""


def _enum_to_cell(enum) -> str:
    """Re-serialise an enum's permissible values as an Enumeration cell.

    Produces ``"value"=[label](iri) | ...`` — the grammar the forward parser
    consumes. Uses single spaces around ``|`` and ``=`` (canonical form; the
    original cell's incidental spacing is not recoverable).
    """
    parts = []
    for value, pv in _items(_get(enum, "permissible_values", {})):
        label = _get(pv, "title", "") or _get(pv, "description", "") or ""
        meaning = _get(pv, "meaning", "")
        item = f'"{value}"=[{label}]'
        if meaning:
            item += f"({meaning})"
        parts.append(item)
    return " | ".join(parts)


def _terms_to_cell(slot) -> str:
    """Space-join the slot's related_mappings back into a Terms cell."""
    return " ".join(str(t) for t in _get(slot, "related_mappings", []))


def _schema_view(schema: dict | str) -> SchemaView:
    """Wrap a schema (parsed dict, or YAML text) in a :class:`SchemaView`."""
    if isinstance(schema, str):
        return SchemaView(schema)
    return SchemaView(yaml.dump(schema, sort_keys=False))


def schema_to_rows(schema: dict | str) -> list[dict]:
    """Reconstruct data dictionary rows (dicts keyed by column) from a schema.

    ``schema`` is a parsed schema dict or the schema YAML text. It is read
    through LinkML's :class:`SchemaView`, which resolves the representation
    variety (attributes vs slots + slot_usage, inheritance, imports) into one
    induced form; see the module docstring.
    """
    view = _schema_view(schema)
    classes = list(view.all_classes().values())
    if not classes:
        return []
    # The datafile class is the tree_root (fall back to the first class).
    root = next((c for c in classes if c.tree_root), classes[0])
    enums = dict(view.all_enums())
    subsets = dict(view.all_subsets())

    rows: list[dict] = []
    for slot in view.class_induced_slots(root.name):
        slot_name = str(slot.name)
        row = dict.fromkeys(KNOWN_COLUMNS, "")

        # Id: prefer the original (pre-sanitisation) id if it was recorded.
        row["Id"] = _annotation(slot, "original_id") or slot_name
        row["Label"] = _get(slot, "title", "")
        row["Description"] = _get(slot, "description", "")
        row["Notes"] = " ".join(str(c) for c in _get(slot, "comments", []))
        row["SeeAlso"] = " ".join(str(s) for s in _get(slot, "see_also", []))
        row["Aliases"] = "|".join(str(a) for a in _get(slot, "aliases", []))
        row["Examples"] = "|".join(
            str(_get(ex, "value", ex)) for ex in _get(slot, "examples", [])
        )
        # `single` is the spec default, so a non-multivalued slot could have had
        # either "single" or a blank cell originally; we emit the explicit
        # "single" (never wrong, and the common form).
        row["Cardinality"] = "multiple" if _get(slot, "multivalued") else "single"
        row["Pattern"] = _get(slot, "pattern", "")
        row["Terms"] = _terms_to_cell(slot)

        # Provenance: emitted as source: (URL/CURIE) or an annotation otherwise.
        row["Provenance"] = _get(slot, "source", "") or _annotation(slot, "provenance")

        # Precondition: the raw cell is preserved as an annotation (the class
        # rules carry the machine form; the annotation carries the round-trip).
        row["Precondition"] = _annotation(slot, "precondition")
        # Required: plain `required: true` when unconditional; the `required`
        # annotation when requiredness was conditional on a precondition.
        if _get(slot, "required") or _annotation(slot, "required") == "y":
            row["Required"] = "y"

        # Unit: the raw cell was preserved as an annotation.
        row["Unit"] = _annotation(slot, "unit_raw")

        # Section: the slot's subset, whose title is the original section name.
        in_subset = _get(slot, "in_subset", [])
        if in_subset:
            subset_name = str(in_subset[0])
            subset = subsets.get(subset_name)
            # The subset's title is the original Section name.
            row["Section"] = _get(subset, "title", subset_name) if subset else subset_name

        # Datatype / Enumeration / MissingValueCodes come from the range.
        _apply_range(row, slot, enums)

        rows.append(row)
    return rows


def _apply_range(row: dict, slot, enums: dict) -> None:
    """Invert the Datatype/Enumeration/MissingValueCodes mapping for one slot.

    Enumerations are recognised in three shapes: named enums referenced
    through ``any_of`` (the generated form: [field enum, standard codes,
    (field-specific codes)]), a named enum used directly as the slot's
    ``range:``, and an inline ``enum_range:``.
    """
    any_of = _get(slot, "any_of", [])
    inline_enum = _get(slot, "enum_range")
    range_ = str(_get(slot, "range", "") or "")

    if any_of:
        # In order: the first enum branch is the field's Enumeration, the
        # second its own MissingValueCodes; the standard shared codes are
        # dictionary-wide, not a per-field fact, so they are skipped.
        enum_cells = []
        for branch in any_of:
            branch_inline = _get(branch, "enum_range")
            if branch_inline:
                enum_cells.append(_enum_to_cell(branch_inline))
                continue
            branch_range = str(_get(branch, "range", "") or "")
            if branch_range == STANDARD_ENUM_NAME:
                continue
            if branch_range in enums:
                enum_cells.append(_enum_to_cell(enums[branch_range]))
        if enum_cells:
            row["Enumeration"] = enum_cells[0]
        if len(enum_cells) > 1:
            row["MissingValueCodes"] = enum_cells[1]
        row["Datatype"] = _annotation(slot, "value_datatype") or "string"
    elif inline_enum:
        row["Enumeration"] = _enum_to_cell(inline_enum)
        row["Datatype"] = _annotation(slot, "value_datatype") or "string"
    elif range_ in enums:
        row["Enumeration"] = _enum_to_cell(enums[range_])
        row["Datatype"] = _annotation(slot, "value_datatype") or "string"
    else:
        # A plain datatype slot. Ranges that are not themselves valid datatype
        # names map back to the spec name (datetime -> dateTime, uri -> anyURI).
        row["Datatype"] = _RANGE_TO_DATATYPE.get(range_, range_) or "string"


def write_csv(rows: list[dict], handle: TextIO) -> None:
    """Write reconstructed rows as a data dictionary CSV (canonical column order)."""
    writer = csv.DictWriter(handle, fieldnames=list(KNOWN_COLUMNS))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


def schema_to_csv(schema_yaml: str) -> str:
    """Convert a LinkML schema (YAML text) to a data dictionary CSV."""
    rows = schema_to_rows(schema_yaml)
    buffer = io.StringIO()
    write_csv(rows, buffer)
    return buffer.getvalue()


def main(argv=None) -> int:
    """CLI: reconstruct a data dictionary CSV from a generated LinkML schema.

    Usage: ``linkml-to-dd SCHEMA.yaml -o DICTIONARY.csv``. The round-trip is
    semantic, not byte-exact (see the module docstring).
    """
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        prog="linkml-to-dd",
        description="Reconstruct a data dictionary CSV from a LinkML schema.",
    )
    parser.add_argument("input", type=Path, help="Path to the LinkML schema YAML.")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output CSV file (default: stdout).",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2

    csv_text = schema_to_csv(args.input.read_text(encoding="utf-8"))
    if args.output is None:
        sys.stdout.write(csv_text)
    else:
        args.output.write_text(csv_text, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
