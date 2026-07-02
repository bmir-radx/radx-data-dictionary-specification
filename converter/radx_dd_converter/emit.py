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

import jsonasobj2
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


# Value-derived enum names are built from the first few values; when there are
# more, an "Etc" marker is appended so the name stays short and does not imply a
# single owning data element. A name longer than this after that is rejected
# (fall back to the field-derived name).
_ENUM_NAME_LEAD_VALUES = 3
_ENUM_NAME_MAX_LEN = 48


def _value_derived_enum_name(items: List["EnumItem"]) -> Optional[str]:
    """Build an enum name from its values, e.g. ``NoYesEnum`` or ``NoYesEtcEnum``.

    Uses the first few values' labels (falling back to the value itself),
    CamelCased and concatenated in source order; appends ``Etc`` when there are
    further values, so a value set shared by many data elements gets a short,
    ownership-neutral name rather than being named after one field. Returns
    ``None`` only when the leading values yield no usable text, so the caller
    can fall back to a field-derived name.
    """
    if not items:
        return None
    lead = items[:_ENUM_NAME_LEAD_VALUES]
    parts = [_class_case(item.label or item.value) for item in lead]
    parts = [p for p in parts if p != "X"]  # drop values that sanitise to nothing
    if not parts:
        return None
    name = "".join(parts) + ("Etc" if len(items) > len(lead) else "") + "Enum"
    if len(name) > _ENUM_NAME_MAX_LEN:
        return None
    # Reject digit-heavy names: numeric-range value sets (labels like "100-150")
    # CamelCase into an illegible digit mash, so fall back to the field name.
    # Threshold: digits make up more than a quarter of the name.
    if sum(c.isdigit() for c in name) * 4 > len(name):
        return None
    if name[0].isdigit():
        name = f"X{name}"
    return name


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
    annotate_enum_values: bool = False  # comment field-enum values after range:


class Emitter:
    """Builds a LinkML SchemaDefinition from data dictionary rows."""

    def __init__(self, options: Optional[EmitOptions] = None):
        self.opts = options or EmitOptions()
        self._prefixes: Dict[str, str] = {}
        self._enum_by_signature: Dict[str, str] = {}  # dedup identical enumerations
        self._terms: set = set()  # every term identifier emitted (for annotation)
        # Field enums (from Enumeration cells) mapped to their (value, label)
        # pairs, for the optional value comment after `range: <Enum>`. Excludes
        # StandardMissingValueCodes and field-specific missing-code enums.
        self._field_enum_values: Dict[str, list] = {}
        # Field enum name -> list of slot names that use it (for the optional
        # "used by" reverse-reference comment on the enum definition).
        self._enum_users: Dict[str, list] = {}
        # Subset (Section) name -> list of slot names in it (for the section
        # comment block above each subset definition).
        self._section_users: Dict[str, list] = {}

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
        """Create (or reuse) an enum for ``items``; return its name.

        The enum is named after its *values* (e.g. ``NoYesEnum``) rather than the
        data element that first used it, since a deduplicated enum may be shared
        by many data elements and a field-derived name would misleadingly imply
        a single owner. Falls back to the field-derived name when the values do
        not yield a usable name.
        """
        signature = repr([(i.value, i.label, i.iri) for i in items])
        if signature in self._enum_by_signature:
            return self._enum_by_signature[signature]

        enum_name = _value_derived_enum_name(items) or f"{_class_case(base_name)}Enum"
        # Avoid name collisions with an existing, differently-valued enum by
        # appending a numeric suffix (SomeEnum, SomeEnum2, SomeEnum3, ...).
        candidate, suffix = enum_name, 2
        while candidate in schema.enums:
            candidate, suffix = f"{enum_name}{suffix}", suffix + 1
        enum_name = candidate

        enum = EnumDefinition(
            name=enum_name,
            description="A controlled set of values generated from a data "
            "dictionary Enumeration cell.",
        )
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
            self._section_users.setdefault(subset_name, []).append(slot.name)

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
            self._field_enum_values.setdefault(
                enum_name, [(i.value, i.label) for i in enum_items]
            )
            self._enum_users.setdefault(enum_name, []).append(slot.name)
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

        # Finalise field enums now that the full usage map is known. An enum used
        # by exactly one data element is renamed after that element (which is
        # meaningful and unambiguous with a single owner); shared enums keep
        # their value-derived name. Descriptions are set to match.
        renames: Dict[str, str] = {}
        for enum_name, users in list(self._enum_users.items()):
            enum = schema.enums.get(enum_name)
            if enum is None:
                continue
            if len(users) == 1:
                new_name = f"{_class_case(users[0])}Enum"
                # Collision-check against other enums (skip self).
                candidate, suffix = new_name, 2
                while candidate in schema.enums and candidate != enum_name:
                    candidate, suffix = f"{new_name}{suffix}", suffix + 1
                new_name = candidate
                if new_name != enum_name:
                    renames[enum_name] = new_name
                enum.description = (
                    f"Permissible values for the `{users[0]}` data element."
                )
            else:
                enum.description = (
                    f"Permissible values shared by {len(users)} data elements "
                    f"(see the `used by` annotation)."
                )

        if renames:
            self._apply_enum_renames(schema, renames)

        # Always place the shared StandardMissingValueCodes enum last by
        # rebuilding the enums mapping in the desired order. schema.enums may be
        # a plain dict or a linkml JsonObj, so iterate via jsonasobj2.
        enums_by_name = dict(jsonasobj2.items(schema.enums))
        if STANDARD_ENUM_NAME in enums_by_name:
            reordered = {
                name: enum
                for name, enum in enums_by_name.items()
                if name != STANDARD_ENUM_NAME
            }
            reordered[STANDARD_ENUM_NAME] = enums_by_name[STANDARD_ENUM_NAME]
            schema.enums = reordered

        return schema

    def _apply_enum_renames(
        self, schema: SchemaDefinition, renames: Dict[str, str]
    ) -> None:
        """Rename enums and re-point every reference to them.

        Updates the ``enums`` mapping keys, the ``range`` of every slot ``any_of``
        branch (and any direct ``range``) that referenced the old name, and the
        internal tracking dicts used by the annotation passes.
        """
        # Rebuild the enums mapping preserving order, with renamed keys. Keep the
        # enum's own `name` in sync with its key, else validation rejects the
        # mismatch (and _drop_redundant_keys only strips `name` when it matches).
        new_enums = {}
        for name, enum in jsonasobj2.items(schema.enums):
            new_name = renames.get(name, name)
            enum.name = new_name
            new_enums[new_name] = enum
        schema.enums = new_enums

        # Re-point slot ranges (enumerated slots use any_of; be defensive about
        # a direct range too).
        for cls in schema.classes.values():
            for slot in cls.attributes.values():
                for branch in slot.any_of or []:
                    if branch.range in renames:
                        branch.range = renames[branch.range]
                if slot.range in renames:
                    slot.range = renames[slot.range]

        # Keep the annotation-tracking dicts consistent with the new names.
        self._field_enum_values = {
            renames.get(k, k): v for k, v in self._field_enum_values.items()
        }
        self._enum_users = {
            renames.get(k, k): v for k, v in self._enum_users.items()
        }

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
        if self.opts.annotate_enum_values and self._field_enum_values:
            text = _annotate_enum_ranges(text, self._field_enum_values)
        # Move the trailing "n of m" counters into comment blocks above each
        # entry: field enums and sections get a 3-line block (number / used-by
        # count / referencing ids); data elements get a 1-line block. This
        # replaces the trailing counters _render added for them.
        if self._enum_users:
            text = _annotate_blocks(text, 2, "Enum", "enums", self._enum_users)
        if self._section_users:
            text = _annotate_blocks(
                text, 2, "Section", "sections", self._section_users
            )
        text = _annotate_blocks(text, 6, "Data element", "data elements")
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


def _is_entry_line(line: str, indent: int) -> bool:
    """True if ``line`` is a mapping entry (``key:``) at exactly ``indent``.

    Entry lines have exactly ``indent`` leading spaces followed by a non-space,
    non-``-`` character. More deeply indented lines, list items, and block-scalar
    text start differently and are excluded, so multi-line descriptions and
    nested keys are never mistaken for entries.
    """
    prefix = " " * indent
    if not line.startswith(prefix):
        return False
    rest = line[indent:]
    return bool(rest) and not rest[0].isspace() and not rest.startswith("-")


def _space_entries_at(text: str, indent: int) -> str:
    """Insert a blank line before each mapping entry at the given indent.

    An "entry" line has exactly ``indent`` leading spaces followed by a
    non-space, non-``-`` character (i.e. a ``key:``). Lines that are more deeply
    indented, are list items, or are block-scalar text start differently and are
    left untouched, so multi-line descriptions are preserved verbatim.
    """
    out: List[str] = []
    seen_first = False
    for line in text.split("\n"):
        if _is_entry_line(line, indent):
            if seen_first:
                out.append("")
            seen_first = True
        out.append(line)
    return "\n".join(out)


# Sections whose direct entries are numbered "n of m" as a trailing comment.
_NUMBERED_SECTIONS = {"enums", "subsets", "classes"}


def _number_entries_at(
    section_yaml: str, indent: int, total: int, label: str
) -> str:
    """Append `# n of m <label>` to each mapping entry at ``indent``.

    ``label`` is the plural type name (e.g. ``"enums"``), suffixed so the
    counter is self-describing, e.g. ``# 4 of 17 enums`` (singularised when
    ``total`` is 1, e.g. ``# 1 of 1 class``).

    An entry line has exactly ``indent`` leading spaces then a ``key:`` (not a
    list item, not deeper). Block-scalar text and nested keys are left untouched.
    A line already carrying a comment is not doubled.
    """
    _SINGULAR = {"data elements": "data element", "enums": "enum",
                 "sections": "section", "classes": "class"}
    noun = _SINGULAR.get(label, label) if total == 1 else label
    out: List[str] = []
    position = 0
    for line in section_yaml.split("\n"):
        if _is_entry_line(line, indent) and "#" not in line:
            position += 1
            out.append(f"{line}  # {position} of {total} {noun}")
        else:
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
        body = _dump_yaml({key: value}).rstrip("\n")
        if key == "classes":
            # Slots live two levels down under `attributes:`; space them there.
            body = _space_entries_at(body, indent=6)
            # Number the class(es) at indent 2 and the slots at indent 6.
            body = _number_entries_at(body, indent=2, total=len(value or {}), label="classes")
            slot_total = sum(
                len((cls or {}).get("attributes") or {}) for cls in value.values()
            )
            body = _number_entries_at(
                body, indent=6, total=slot_total, label="data elements"
            )
        elif key in _SPACED_SECTIONS:
            body = _space_entries_at(body, indent=2)

        # Number the entries of enums / subsets as "n of m" (classes handled above).
        if key in _NUMBERED_SECTIONS and key != "classes":
            label = "sections" if key == "subsets" else key
            body = _number_entries_at(body, indent=2, total=len(value or {}), label=label)
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
    line_re = re.compile(r"^\s*(?:-\s+|[\w.]+:\s+)(?P<term>\S+)\s*$")
    out: List[str] = []
    for line in text.split("\n"):
        match = line_re.match(line)
        term = match.group("term") if match else None
        if term in labels and "#" not in line:
            out.append(f"{line}  # {labels[term]}")
        else:
            out.append(line)
    return "\n".join(out)


_ENUM_VALUE_CAP = 6  # max value=label pairs shown inline before "(+N more)"


def _format_enum_comment(pairs: list) -> str:
    """Build a capped ``value=label | ...`` comment body for an enum."""
    shown = pairs[:_ENUM_VALUE_CAP]
    parts = [f"{v}={label}" if label else f"{v}" for v, label in shown]
    body = " | ".join(parts)
    extra = len(pairs) - len(shown)
    if extra > 0:
        body += f" (+{extra} more)"
    return body


def _annotate_enum_ranges(text: str, field_enum_values: Dict[str, list]) -> str:
    """Append a capped value=label comment after ``range: <FieldEnum>`` lines.

    Only enum names present in ``field_enum_values`` are annotated (so the
    shared StandardMissingValueCodes and field-specific missing-code enums are
    skipped). Matches both ``range: X`` and ``- range: X`` (the ``any_of``
    branch). Lines already carrying a comment are left alone.
    """
    line_re = re.compile(r"^\s*(?:-\s+)?range:\s+(?P<enum>\S+)\s*$")
    out: List[str] = []
    for line in text.split("\n"):
        match = line_re.match(line)
        enum_name = match.group("enum") if match else None
        if enum_name in field_enum_values and "#" not in line:
            comment = _format_enum_comment(field_enum_values[enum_name])
            out.append(f"{line}  # {comment}")
        else:
            out.append(line)
    return "\n".join(out)


_ENUM_USERS_CAP = 6  # max data-element ids listed in the "used by" comment line


def _annotate_blocks(
    text: str,
    indent: int,
    kind: str,
    counter_noun: str,
    users: Optional[Dict[str, list]] = None,
) -> str:
    """Move an entry's trailing "n of m <noun>" counter into a block above it.

    Matches entry lines at ``indent`` that carry a trailing ``# n of m
    <counter_noun>`` comment (as emitted by ``_render``). The counter becomes a
    ``# <kind> n of m`` line above the now-bare key line. When ``users`` is
    given and contains the entry, two further lines are added — a "Used by N
    data elements" count and a capped id list — mirroring the enum/section block.

    ``users`` also acts as a filter when provided: only entries present in it are
    rewritten (others keep their trailing counter). When ``users`` is ``None``
    every matching entry is rewritten (used for data elements, which have no
    "used by").
    """
    pad = " " * indent
    # Match the counter noun in either plural or singular form (_render
    # singularises when the total is 1), e.g. "enums"/"enum",
    # "data elements"/"data element".
    plural = re.escape(counter_noun)
    singular = re.escape(counter_noun[:-1] if counter_noun.endswith("s") else counter_noun)
    line_re = re.compile(
        rf"^{pad}(?P<name>\S+):"
        rf"\s*(?P<counter># *(?P<position>\d+) of (?P<total>\d+) (?:{plural}|{singular}))?\s*$"
    )
    out: List[str] = []
    for line in text.split("\n"):
        match = line_re.match(line)
        name = match.group("name") if match else None
        has_counter = match and match.group("counter")
        should_rewrite = has_counter and (users is None or name in users)
        if should_rewrite:
            out.append(f"{pad}# {kind} {match.group('position')} of {match.group('total')}")
            if users is not None and name in users:
                user_ids = users[name]
                shown = user_ids[:_ENUM_USERS_CAP]
                id_list = " | ".join(shown)
                hidden = len(user_ids) - len(shown)
                if hidden > 0:
                    id_list += f" (+{hidden} more)"
                element_noun = "data element" if len(user_ids) == 1 else "data elements"
                out.append(f"{pad}# Used by {len(user_ids)} {element_noun}")
                out.append(f"{pad}# {id_list}")
            out.append(f"{pad}{name}:")  # bare key line
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
