"""Reconstruct a RADx data dictionary CSV from a generated LinkML schema.

This is the inverse of :mod:`emit`. It reads a schema produced by this converter
and rebuilds the data dictionary, one row per slot of the root class, inverting
the column -> LinkML mapping.

The round-trip is *semantic*, not byte-exact: the forward conversion normalises
some text (it strips trailing whitespace from descriptions and re-joins ``Terms``
with single spaces) and re-serialises the ``Enumeration`` cell grammar, so a
reconstructed cell may be equivalent to the original without being identical.
See ``linkml/CONVERTER_PLAN.md``.
"""

from __future__ import annotations

import csv
import io
from typing import TextIO

import jsonasobj2
import yaml

from .missing_values import STANDARD_ENUM_NAME
from .reader import KNOWN_COLUMNS


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


def schema_to_rows(schema: dict) -> list[dict]:
    """Reconstruct data dictionary rows (dicts keyed by column) from a schema."""
    classes = _items(_get(schema, "classes", {}))
    if not classes:
        return []
    # The datafile class is the tree_root (fall back to the first class).
    root = next((c for _, c in classes if _get(c, "tree_root")), classes[0][1])
    enums = dict(_items(_get(schema, "enums", {})))
    subsets = dict(_items(_get(schema, "subsets", {})))

    rows: list[dict] = []
    for slot_name, slot in _items(_get(root, "attributes", {})):
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
    """Invert the Datatype/Enumeration/MissingValueCodes mapping for one slot."""
    any_of = _get(slot, "any_of", [])
    if any_of:
        # Enumerated slot: any_of = [field enum, StandardMissingValueCodes,
        # (field-specific codes)]. Datatype was kept in value_datatype.
        row["Datatype"] = _annotation(slot, "value_datatype") or "string"
        ranges = [str(_get(branch, "range", "")) for branch in any_of]
        field_enum = next(
            (r for r in ranges if r and r != STANDARD_ENUM_NAME), None
        )
        if field_enum and field_enum in enums:
            row["Enumeration"] = _enum_to_cell(enums[field_enum])
        # A third branch (besides the field enum and the standard codes) is the
        # field's own MissingValueCodes.
        extra = [
            r for r in ranges
            if r and r != STANDARD_ENUM_NAME and r != field_enum and r in enums
        ]
        if extra:
            row["MissingValueCodes"] = _enum_to_cell(enums[extra[0]])
    else:
        row["Datatype"] = _get(slot, "range", "") or "string"


def write_csv(rows: list[dict], handle: TextIO) -> None:
    """Write reconstructed rows as a data dictionary CSV (canonical column order)."""
    writer = csv.DictWriter(handle, fieldnames=list(KNOWN_COLUMNS))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


def schema_to_csv(schema_yaml: str) -> str:
    """Convert a generated LinkML schema (YAML text) to a data dictionary CSV."""
    schema = yaml.safe_load(schema_yaml)
    rows = schema_to_rows(schema)
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
        description="Reconstruct a RADx data dictionary CSV from a LinkML schema.",
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
