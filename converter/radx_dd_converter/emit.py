"""Emit a LinkML schema from parsed data dictionary rows.

Assembles the ``Row`` objects (from :mod:`reader`) plus the parsed cell
grammars, datatype resolution, unit lookup and standard missing-value codes into
a ``linkml_runtime`` :class:`SchemaDefinition`, which is then dumped to YAML.
Building the object model (rather than templating text) means the output is
always well-formed. See ``linkml/CONVERTER_PLAN.md`` for the mapping decisions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from linkml_runtime.dumpers import yaml_dumper
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
    """CamelCase a name for use as an enum/class name."""
    parts = re.split(r"\W+", name.strip())
    return "".join(p[:1].upper() + p[1:] for p in parts if p) or "X"


@dataclass
class EmitOptions:
    """Options controlling schema identity (from CLI flags / filename)."""

    schema_id: str = "https://w3id.org/radx/generated"
    schema_name: str = "radx_generated"
    class_name: str = "Record"
    default_prefix: Optional[str] = None  # defaults to schema_name


class Emitter:
    """Builds a LinkML SchemaDefinition from data dictionary rows."""

    def __init__(self, options: Optional[EmitOptions] = None):
        self.opts = options or EmitOptions()
        self._prefixes: Dict[str, str] = {}
        self._enum_by_signature: Dict[str, str] = {}  # dedup identical enumerations

    # -- prefixes / term identifiers ---------------------------------------

    def _register_term(self, term: str) -> str:
        """Register the prefix of a CURIE (OBO auto-expansion); return term as-is.

        Full IRIs are returned unchanged with no registration. OBO-style CURIEs
        get their prefix auto-registered via the deterministic OBO rule. A
        non-OBO CURIE whose prefix is unknown is kept and a warning is logged.
        """
        term = term.strip()
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
            pv = PermissibleValue(text=item.value, description=item.label or None)
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
                text=item.value, description=item.label or None
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
            slot.description = row.get("Description")
        if row.get("Notes"):
            slot.comments.append(row.get("Notes"))
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

        # Terms -> slot_uri (first) + exact_mappings (rest). SlotDefinition uses
        # `slot_uri` (single) and `exact_mappings` (list).
        terms = parse_terms(row.get("Terms"))
        if terms:
            slot.slot_uri = self._register_term(terms[0])
            for t in terms[1:]:
                slot.exact_mappings.append(self._register_term(t))

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
                    name=subset_name, description=section
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
        return yaml_dumper.dumps(self.build(rows))


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
