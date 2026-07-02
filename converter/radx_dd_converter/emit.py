"""Emit a LinkML schema from parsed data dictionary rows.

Assembles the ``Row`` objects (from :mod:`reader`) plus the parsed cell
grammars, datatype resolution, unit lookup and standard missing-value codes into
a ``linkml_runtime`` :class:`SchemaDefinition`, which is then dumped to YAML.
Building the object model (rather than templating text) means the output is
always well-formed. See ``linkml/CONVERTER_PLAN.md`` for the mapping decisions.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml
from linkml_runtime.dumpers import json_dumper
from linkml_runtime.linkml_model.meta import (
    AnonymousSlotExpression,
    ClassDefinition,
    EnumDefinition,
    Example,
    PermissibleValue,
    SchemaDefinition,
    SlotDefinition,
    SubsetDefinition,
    TypeDefinition,
    UnitOfMeasure as LinkMLUnitOfMeasure,
)

from .datatypes import CustomType, resolve_datatype
from .grammar import EnumItem, parse_enumeration, parse_missing_value_codes, parse_terms
from .missing_values import (
    STANDARD_ENUM_NAME,
    STANDARD_MISSING_VALUE_CODES,
)
from .reader import Row
from .units import lookup_unit

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_CURIE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*):(.+)$")
_OBO_PURL = "http://purl.obolibrary.org/obo/"


def _clean_text(text: str) -> str:
    """Tidy a free-text field for readable YAML output.

    Strips trailing whitespace from each line, and strips leading/trailing blank
    lines from the whole field. Trailing spaces prevent YAML from using the
    readable literal-block (`|`) style, and trailing blank lines leave a run of
    empty lines at the end of a block scalar. Internal newlines and spacing are
    preserved, so this is a lossless-in-intent normalisation.
    """
    per_line = "\n".join(line.rstrip() for line in text.split("\n"))
    return per_line.strip("\n")


class _BlockStyleDumper(yaml.SafeDumper):
    """A YAML dumper that renders multi-line strings as literal `|` blocks."""


def _represent_str(dumper: yaml.SafeDumper, data: str):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_BlockStyleDumper.add_representer(str, _represent_str)


def _sanitize(name: str) -> str:
    """Turn an arbitrary Id/Section into a LinkML-safe name.

    Non-word characters become underscores; a leading digit is prefixed. The
    original value is preserved elsewhere (slot title / annotation), so this only
    affects the schema-internal name.
    """
    safe = re.sub(r"\W+", "_", name.strip()).strip("_")
    if not safe:
        safe = "_"
    if safe[0].isdigit():
        safe = f"x_{safe}"
    return safe


def _class_case(name: str) -> str:
    """CamelCase a name for use as an enum/class name.

    Splits on any non-alphanumeric character, including underscores, so
    ``nih_race`` -> ``NihRace`` (not ``Nih_race``).
    """
    parts = re.split(r"[^A-Za-z0-9]+", name.strip())
    return "".join(p[:1].upper() + p[1:] for p in parts if p) or "X"


@dataclass
class EmitOptions:
    """Options controlling schema identity (from CLI flags / filename)."""

    schema_id: str = "https://w3id.org/radx/generated"
    schema_name: str = "radx_generated"
    class_name: str = "Record"
    default_prefix: Optional[str] = None  # defaults to schema_name
    annotate_terms: bool = False  # look up ontology term names and add as comments
    resolver: str = "ols4"  # term-name resolver: "ols4" or "bioportal"
    bioportal_apikey: Optional[str] = None  # required when resolver == "bioportal"


class Emitter:
    """Builds a LinkML SchemaDefinition from data dictionary rows."""

    def __init__(self, options: Optional[EmitOptions] = None):
        self.opts = options or EmitOptions()
        self._prefixes: Dict[str, str] = {}
        self._enum_by_signature: Dict[str, str] = {}  # dedup identical enumerations
        self._terms: set = set()  # every term identifier emitted (for annotation)

    # -- prefixes / term identifiers ---------------------------------------

    def _register_term(self, term: str) -> str:
        """Register the prefix of a CURIE (OBO auto-expansion); return term as-is.

        Full IRIs are returned unchanged with no registration. OBO-style CURIEs
        get their prefix auto-registered via the deterministic OBO rule. A
        non-OBO CURIE whose prefix is unknown is kept and a warning is logged.
        """
        term = term.strip()
        self._terms.add(term)
        if _URL_RE.match(term):
            return term  # full IRI; nothing to register
        m = _CURIE_RE.match(term)
        if not m:
            return term  # not a CURIE; leave as-is
        prefix = m.group(1)
        if prefix not in self._prefixes:
            # Auto-register any CURIE prefix using the OBO PURL rule. This is
            # correct for OBO Foundry ontologies; for a non-OBO prefix it is a
            # best-effort default, so we warn.
            self._prefixes[prefix] = f"{_OBO_PURL}{prefix}_"
            if not _looks_obo(prefix):
                logger.warning(
                    "Prefix %r is not a known OBO Foundry id space; registered "
                    "with a best-effort OBO expansion. Verify or override it.",
                    prefix,
                )
        return term

    # -- enumerations ------------------------------------------------------

    def _emit_enum(self, schema: SchemaDefinition, base_name: str,
                   items: List[EnumItem]) -> str:
        """Create (or reuse) an enum for ``items``; return its name."""
        signature = repr([(i.value, i.label, i.iri) for i in items])
        if signature in self._enum_by_signature:
            return self._enum_by_signature[signature]

        enum_name = f"{_class_case(base_name)}Enum"
        # Avoid name collisions with an existing, differently-valued enum.
        n, suffix = enum_name, 2
        while n in schema.enums:
            n, suffix = f"{enum_name}{suffix}", suffix + 1
        enum_name = n

        enum = EnumDefinition(name=enum_name)
        for item in items:
            pv = PermissibleValue(text=item.value, title=item.label or None)
            if item.iri:
                pv.meaning = self._register_term(item.iri)
            enum.permissible_values[item.value] = pv
        schema.enums[enum_name] = enum
        self._enum_by_signature[signature] = enum_name
        return enum_name

    def _ensure_standard_codes_enum(self, schema: SchemaDefinition) -> None:
        if STANDARD_ENUM_NAME in schema.enums:
            return
        enum = EnumDefinition(
            name=STANDARD_ENUM_NAME,
            description="The standard set of RADx missing-value codes, which "
            "always applies to a missing-value-coded field.",
        )
        for item in STANDARD_MISSING_VALUE_CODES:
            enum.permissible_values[item.value] = PermissibleValue(
                text=item.value, title=item.label or None
            )
        schema.enums[STANDARD_ENUM_NAME] = enum

    # -- per-row slot ------------------------------------------------------

    def _build_slot(self, schema: SchemaDefinition, row: Row) -> SlotDefinition:
        slot = SlotDefinition(name=_sanitize(row.id))

        # Preserve the original Id if sanitisation changed it.
        if slot.name != row.id:
            slot.annotations["original_id"] = row.id

        slot.title = row.get("Label") or None
        if row.get("Description"):
            slot.description = _clean_text(row.get("Description"))
        if row.get("Notes"):
            slot.comments.append(_clean_text(row.get("Notes")))
        if row.get("SeeAlso"):
            slot.see_also.append(row.get("SeeAlso"))

        # Aliases (pipe-delimited).
        for alias in _split_pipe(row.get("Aliases")):
            slot.aliases.append(alias)

        # Examples (pipe-delimited).
        for ex in _split_pipe(row.get("Examples")):
            slot.examples.append(Example(value=ex))

        # Cardinality.
        if row.get("Cardinality").strip().lower() == "multiple":
            slot.multivalued = True

        # Pattern (verbatim; XSD-regex dialect).
        if row.get("Pattern"):
            slot.pattern = row.get("Pattern")

        # Terms -> related_mappings. RADx Terms are subject-matter annotations
        # (the concept a field relates to), not the slot's predicate URI, so
        # they map to related_mappings rather than slot_uri / exact_mappings.
        for term in parse_terms(row.get("Terms")):
            slot.related_mappings.append(self._register_term(term))

        # Provenance -> source: if URL/CURIE, else annotation.
        prov = row.get("Provenance").strip()
        if prov:
            if _URL_RE.match(prov) or _CURIE_RE.match(prov):
                slot.source = prov
            else:
                slot.annotations["provenance"] = prov

        # Section -> in_subset + declared subset.
        section = row.get("Section").strip()
        if section:
            subset_name = _sanitize(section)
            if subset_name not in schema.subsets:
                schema.subsets[subset_name] = SubsetDefinition(
                    name=subset_name, title=section
                )
            slot.in_subset.append(subset_name)

        # Unit -> native unit: (lookup-assisted), raw always preserved.
        unit_raw = row.get("Unit").strip()
        if unit_raw:
            slot.annotations["unit_raw"] = unit_raw
            known = lookup_unit(unit_raw)
            if known is not None:
                slot.unit = LinkMLUnitOfMeasure(
                    descriptive_name=known.descriptive_name,
                    symbol=known.symbol,
                    ucum_code=known.ucum_code,
                )
            else:
                slot.unit = LinkMLUnitOfMeasure(symbol=unit_raw)

        # Range: Enumeration wins over Datatype; missing-value codes augment via any_of.
        self._apply_range(schema, row, slot)
        return slot

    def _apply_range(self, schema: SchemaDefinition, row: Row,
                     slot: SlotDefinition) -> None:
        enum_items = parse_enumeration(row.get("Enumeration"))
        field_codes = parse_missing_value_codes(row.get("MissingValueCodes"))

        if enum_items:
            # Enumeration is the controlling set; underlying datatype preserved.
            enum_name = self._emit_enum(schema, row.id, enum_items)
            slot.annotations["value_datatype"] = row.get("Datatype")

            branches = [AnonymousSlotExpression(range=enum_name)]
            self._ensure_standard_codes_enum(schema)
            branches.append(AnonymousSlotExpression(range=STANDARD_ENUM_NAME))
            if field_codes:
                field_codes_name = self._emit_enum(
                    schema, f"{row.id}MissingValueCodes", field_codes
                )
                branches.append(AnonymousSlotExpression(range=field_codes_name))
            slot.any_of = branches
        else:
            # No enumeration: range from Datatype (builtin or custom type).
            resolved = resolve_datatype(row.get("Datatype"))
            if isinstance(resolved, CustomType):
                self._emit_custom_type(schema, resolved)
                slot.range = resolved.name
            else:
                slot.range = resolved

    def _emit_custom_type(self, schema: SchemaDefinition, ct: CustomType) -> None:
        if ct.name in schema.types:
            return
        schema.types[ct.name] = TypeDefinition(
            name=ct.name,
            typeof=ct.typeof,
            pattern=ct.pattern,
            uri=ct.uri,
            description=ct.description,
        )

    # -- top-level build ---------------------------------------------------

    def build(self, rows: List[Row]) -> SchemaDefinition:
        opts = self.opts
        schema = SchemaDefinition(
            id=opts.schema_id,
            name=opts.schema_name,
            default_range="string",
            default_prefix=opts.default_prefix or opts.schema_name,
        )
        schema.imports.append("linkml:types")
        schema.prefixes["linkml"] = "https://w3id.org/linkml/"

        cls = ClassDefinition(name=opts.class_name, tree_root=True)
        for row in rows:
            slot = self._build_slot(schema, row)
            cls.attributes[slot.name] = slot
        schema.classes[cls.name] = cls

        # Register any prefixes discovered while building slots.
        for prefix, expansion in self._prefixes.items():
            schema.prefixes.setdefault(prefix, expansion)

        return schema

    def dumps(self, rows: List[Row]) -> str:
        """Build the schema and dump it as readable YAML.

        The schema object is converted to a plain dict via ``json_dumper``
        (which drops empty/None fields), then dumped with a PyYAML dumper that
        renders multi-line strings as literal `|` blocks. Section-header
        comments and blank lines are added between top-level sections and
        between the entries within the mapping-valued sections (subsets, enums,
        types, classes), to make the output easier to scan.
        """
        schema = self.build(rows)
        as_dict = _strip_type_keys(json.loads(json_dumper.dumps(schema)))
        _drop_redundant_keys(as_dict)
        _order_slot_keys(as_dict)
        _annotations_last(as_dict)
        text = _render(as_dict)
        if self.opts.annotate_terms and self._terms:
            from .terms_lookup import lookup_labels

            labels = lookup_labels(
                self._terms,
                resolver=self.opts.resolver,
                apikey=self.opts.bioportal_apikey,
            )
            if labels:
                text = _annotate_term_lines(text, labels)
        return text


# Human-readable header comments for the mapping-valued sections, and the
# order in which top-level sections are emitted.
_SECTION_COMMENTS = {
    "subsets": "Subsets (from the data dictionary's Section column)",
    "types": "Custom datatypes",
    "enums": "Enumerations",
    "slots": "Slots",
    "classes": "Classes",
}
# Sections whose direct entries should be separated by a blank line.
_SPACED_SECTIONS = {"subsets", "types", "enums", "classes"}

# Orientation header prepended to every generated schema.
_HEADER_COMMENT = """\
# LinkML schema generated from a RADx data dictionary by radx-dd-to-linkml.
#
# The single class below (the tree_root) describes a target datafile: each of
# its slots corresponds to one field (column) of that datafile, in order. The
# non-obvious conventions used here are:
#
#   * A field with an enumeration becomes a slot whose value must be one of the
#     generated <Field>Enum values OR a StandardMissingValueCodes code (and any
#     field-specific codes) -- expressed with `any_of`. The field's underlying
#     datatype is kept in the `value_datatype` annotation.
#   * A field's Section becomes a declared `subset`, referenced from the slot
#     via `in_subset`.
#   * Ontology terms are kept as CURIEs; their prefixes are declared in
#     `prefixes` (OBO id spaces expand under purl.obolibrary.org).
#   * Machine-oriented annotations (`unit_raw`, `value_datatype`, `provenance`,
#     `original_id`) appear at the end of each slot.
#
# See the RADx Data Dictionary Specification for the source field definitions:
# https://github.com/bmir-radx/radx-data-dictionary-specification
"""


def _dump_yaml(obj) -> str:
    return yaml.dump(
        obj,
        Dumper=_BlockStyleDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=88,
    )


def _space_entries_at(text: str, indent: int) -> str:
    """Insert a blank line before each mapping entry at the given indent.

    An "entry" line has exactly ``indent`` leading spaces followed by a
    non-space, non-``-`` character (i.e. a ``key:``). Lines that are more deeply
    indented, are list items, or are block-scalar text start differently and are
    left untouched, so multi-line descriptions are preserved verbatim.
    """
    prefix = " " * indent
    out: List[str] = []
    seen_first = False
    for line in text.split("\n"):
        stripped = line[indent:] if line.startswith(prefix) else ""
        is_entry = (
            line.startswith(prefix)
            and bool(stripped)
            and not stripped[0].isspace()
            and not stripped.startswith("-")
        )
        if is_entry:
            if seen_first:
                out.append("")
            seen_first = True
        out.append(line)
    return "\n".join(out)


def _render(as_dict: dict) -> str:
    """Render the schema dict to YAML with section comments and blank lines."""
    scalar_header: List[str] = []
    blocks: List[str] = []

    for key, value in as_dict.items():
        # Group the leading scalar/simple header keys together (no blank lines
        # between them, no section comment): name, id, imports, prefixes, etc.
        if key not in _SECTION_COMMENTS:
            scalar_header.append(_dump_yaml({key: value}).rstrip("\n"))
            continue

        comment = _SECTION_COMMENTS[key]
        if key == "classes":
            # Slots live two levels down under `attributes:`; space them there.
            body = _space_entries_at(_dump_yaml({key: value}).rstrip("\n"), indent=6)
        elif key in _SPACED_SECTIONS:
            body = _space_entries_at(_dump_yaml({key: value}).rstrip("\n"), indent=2)
        else:
            body = _dump_yaml({key: value}).rstrip("\n")
        blocks.append(f"# --- {comment} ---\n{body}")

    header = "\n".join(scalar_header)
    return _HEADER_COMMENT + "\n" + "\n\n".join([header, *blocks]) + "\n"


def _drop_redundant_keys(as_dict: dict) -> None:
    """Drop identifier keys that merely repeat their mapping key.

    Every element defined as an entry in a mapping (``enums``, ``classes``,
    ``slots``, ``types``, ``subsets``) is named by its key, so an inner
    ``name:`` equal to that key is redundant. Likewise a permissible value's
    ``text:`` equal to its key. LinkML infers both from the key, so removing
    them is lossless and de-clutters the output. Mutates ``as_dict`` in place.
    """
    def strip_named(mapping):
        """Drop `name:` from any entry whose name equals its key."""
        for key, element in (mapping or {}).items():
            if isinstance(element, dict) and element.get("name") == key:
                del element["name"]

    # Top-level named sections: types, subsets (Sections), slots, enums.
    for section in ("types", "subsets", "slots", "enums"):
        strip_named(as_dict.get(section, {}))

    # Permissible values: drop `text:` when it equals the value key.
    for enum in (as_dict.get("enums") or {}).values():
        for pv_key, pv in (enum.get("permissible_values") or {}).items():
            if isinstance(pv, dict) and pv.get("text") == pv_key:
                del pv["text"]

    # Classes, and their nested slots (attributes).
    strip_named(as_dict.get("classes", {}))
    for cls in (as_dict.get("classes") or {}).values():
        strip_named(cls.get("attributes", {}))


# Preferred leading key order for a slot definition. Keys not listed keep their
# existing relative order after these; `annotations` is forced last separately.
_SLOT_KEY_ORDER = ("title", "description", "range")


def _order_slot_keys(as_dict: dict) -> None:
    """Reorder each slot's keys so title, description, range come first.

    Remaining keys keep their existing order. Mutates ``as_dict`` in place.
    """
    for cls in (as_dict.get("classes") or {}).values():
        attrs = cls.get("attributes") or {}
        for slot_name, slot in list(attrs.items()):
            if not isinstance(slot, dict):
                continue
            front = [k for k in _SLOT_KEY_ORDER if k in slot]
            rest = [k for k in slot if k not in _SLOT_KEY_ORDER]
            attrs[slot_name] = {k: slot[k] for k in (*front, *rest)}


def _annotations_last(as_dict: dict) -> None:
    """Reorder each slot mapping so ``annotations`` is its last key.

    LinkML emits ``annotations`` near the top of a slot; moving it to the end
    keeps the human-relevant fields (description, range, ...) first and groups
    the machine-oriented annotations (``unit_raw``, ``value_datatype``,
    ``provenance``, ``original_id``) at the bottom. Mutates ``as_dict`` in place.
    """
    for cls in as_dict.get("classes", {}).values():
        for slot_name, slot in list(cls.get("attributes", {}).items()):
            if isinstance(slot, dict) and "annotations" in slot:
                ann = slot.pop("annotations")
                slot["annotations"] = ann  # re-insert at the end


def _annotate_term_lines(text: str, labels: Dict[str, str]) -> str:
    """Append ``  # <label>`` to YAML lines whose value is a known term.

    Matches only the two shapes in which term identifiers appear: a mapping
    value (``  meaning: CURIE``) and a list item (``  - CURIE``). The value is
    compared exactly against the resolved ``labels`` keys, so block-scalar text
    and unrelated lines are never touched. A line already carrying a comment is
    left alone.
    """
    line_re = re.compile(r"^(\s*(?:-\s+|[\w.]+:\s+))(\S+)\s*$")
    out: List[str] = []
    for line in text.split("\n"):
        m = line_re.match(line)
        if m and m.group(2) in labels and "#" not in line:
            out.append(f"{line}  # {labels[m.group(2)]}")
        else:
            out.append(line)
    return "\n".join(out)


def _strip_type_keys(obj):
    """Remove JSON-LD ``@type`` keys that json_dumper adds.

    The LinkML schema meta-model rejects an ``@type`` property on the schema
    object, so it must not appear in the YAML we emit.
    """
    if isinstance(obj, dict):
        return {k: _strip_type_keys(v) for k, v in obj.items() if k != "@type"}
    if isinstance(obj, list):
        return [_strip_type_keys(v) for v in obj]
    return obj


def _split_pipe(cell: str) -> List[str]:
    if not cell or not cell.strip():
        return []
    return [part for part in cell.split("|")]


def _looks_obo(prefix: str) -> bool:
    """Heuristic: OBO Foundry id spaces are upper-case alphanumerics."""
    return bool(re.fullmatch(r"[A-Z][A-Z0-9]+", prefix))


def emit_schema(rows: List[Row], options: Optional[EmitOptions] = None) -> str:
    """Convenience: build and dump a LinkML schema YAML string from rows."""
    return Emitter(options).dumps(rows)
