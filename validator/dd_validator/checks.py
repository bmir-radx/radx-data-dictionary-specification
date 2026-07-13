"""The individual validation checks.

Each check inspects the header or the data rows and yields :class:`Finding`
objects. The checks are independent and never raise on a data problem; they
report it. The per-cell parsing rules (datatype names, the enumeration and
missing-value-codes grammars) are reused from :mod:`dd_core` so the
validator stays in lockstep with the converter and the specification.

Conventions, mirrored from the reference Java validator:

* A per-field check whose column is absent from the header does nothing (a
  missing *optional* column is not itself a problem; missing *required* columns
  are reported by :func:`check_required_headers`).
* Per-field checks skip blank cells, except the required-field checks.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from urllib.parse import urlsplit

from dd_core import (
    BUILTIN_RANGES,
    CUSTOM_TYPES,
    ORDERED_DATATYPES,
    REQUIRED_COLUMNS,
    STANDARD_MISSING_VALUE_CODES,
    CustomType,
    UnknownDatatypeError,
    resolve_datatype,
    sanitize_identifier,
    suggest_ucum,
    ucum_unit,
)
from dd_core.grammar import (
    Comparison,
    Contains,
    ParseError,
    parse_enumeration,
    parse_missing_value_codes,
    parse_precondition,
)
from dd_core.grammar import atoms as precondition_atoms

from .model import Finding, Level
from .rows import RawRow

# Case-insensitive index of the valid datatype names, used to recover the
# correctly-cased name from a near-miss (e.g. "Integer" -> "integer").
# resolve_datatype() remains the source of truth for what is valid.
_DATATYPES_BY_LOWERCASE = {
    name.lower(): name for name in (*BUILTIN_RANGES, *CUSTOM_TYPES)
}

# Datatype names people commonly write that are not in the specification, and
# the valid name each one usually means. From the reference Java validator.
_DATATYPE_FIXES = {
    "bit": "boolean",
    "text": "string",
    "number": "decimal",
    "email": "string",
    "zipcode": "string",
    "phone": "string",
}


def _suggest_datatype(unknown_name: str) -> str | None:
    """Suggest a valid datatype name for an unknown one, or ``None``.

    Tries a case-insensitive match against the valid names first (catches a
    miscased ``Integer``), then the common-mistake fix map.
    """
    lowered = unknown_name.lower()
    return _DATATYPES_BY_LOWERCASE.get(lowered) or _DATATYPE_FIXES.get(lowered)


# --- header ----------------------------------------------------------------

def check_required_headers(header: Sequence[str]) -> Iterable[Finding]:
    """Report each required column header that is absent.

    Suggests a rename when a header matches a required name case-insensitively
    (e.g. ``id`` for ``Id``).
    """
    present = set(header)
    headers_by_lowercase = {h.lower(): h for h in header}
    for required in REQUIRED_COLUMNS:
        if required in present:
            continue
        message = f"required column {required!r} is missing"
        miscased = headers_by_lowercase.get(required.lower())
        if miscased is not None:
            message += f" (did you mean the column {miscased!r}?)"
        yield Finding(Level.ERROR, "required-header", message, column=required)


# --- per-row checks ---------------------------------------------------------

def check_id(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Id" not in columns_present:
        return  # required-header check already reports the missing column
    for row in rows:
        # Deliberately unstripped: the whitespace checks below inspect it.
        id_cell = row.get("Id")
        if id_cell.strip() == "":
            yield Finding(Level.ERROR, "id-missing", "Id is missing", line=row.line, column="Id")
            continue
        if id_cell.startswith(" "):
            yield Finding(
                Level.ERROR, "id-leading-whitespace",
                "Id starts with whitespace", line=row.line, column="Id", value=id_cell,
            )
        # Spaces and special characters are legal per the specification, but
        # they degrade the id elsewhere: schema renderings rename it (the
        # shared sanitisation rule) and preconditions cannot reference it.
        # Broadens the earlier id-whitespace check; the suggestion is exactly
        # the name a schema rendering would use.
        safe = sanitize_identifier(id_cell)
        if safe != id_cell:
            yield Finding(
                Level.INFO, "id-characters",
                f"Id contains spaces or special characters; schema renderings "
                f"rename it to {safe!r} and preconditions cannot reference it "
                f"as written",
                line=row.line, column="Id", value=id_cell, suggestion=safe,
            )


def check_label(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Label" not in columns_present:
        return
    for row in rows:
        if row.get("Label").strip() == "":
            yield Finding(
                Level.WARNING, "label-missing",
                "Label is missing (a label is strongly recommended)",
                line=row.line, column="Label",
            )


def check_datatype(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Datatype" not in columns_present:
        return
    for row in rows:
        datatype_name = row.get("Datatype").strip()
        if datatype_name == "":
            yield Finding(
                Level.ERROR, "datatype-missing",
                "Datatype is missing", line=row.line, column="Datatype",
            )
            continue
        try:
            resolve_datatype(datatype_name)
        except UnknownDatatypeError:
            message = f"{datatype_name!r} is not a known datatype name"
            suggestion = _suggest_datatype(datatype_name)
            if suggestion is not None:
                message += f" (did you mean {suggestion!r}?)"
            yield Finding(
                Level.ERROR, "unknown-datatype", message,
                line=row.line, column="Datatype", value=datatype_name,
            )


def check_cardinality(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Cardinality" not in columns_present:
        return
    for row in rows:
        cardinality = row.get("Cardinality").strip()
        if cardinality == "":
            continue
        if cardinality not in ("single", "multiple"):
            yield Finding(
                Level.ERROR, "invalid-cardinality",
                f"invalid cardinality {cardinality!r} (expected 'single' or 'multiple')",
                line=row.line, column="Cardinality", value=cardinality,
            )


def check_pattern(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Pattern" not in columns_present:
        return
    for row in rows:
        pattern = row.get("Pattern")
        if pattern.strip() == "":
            continue
        try:
            re.compile(pattern)
        except re.error as exc:
            yield Finding(
                Level.ERROR, "malformed-pattern",
                f"pattern is not a valid regular expression: {exc}",
                line=row.line, column="Pattern", value=pattern,
            )


def check_enumeration(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Enumeration" not in columns_present:
        return
    for row in rows:
        enumeration = row.get("Enumeration")
        if enumeration.strip() == "":
            continue
        try:
            parse_enumeration(enumeration)
        except ParseError as exc:
            yield Finding(
                Level.ERROR, "malformed-enumeration",
                f"enumeration is malformed: {exc}",
                line=row.line, column="Enumeration", value=enumeration,
            )


def check_cell_whitespace(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Leading/trailing whitespace in a cell (WARNING).

    Padding survives serialisation and breaks exact-value matching — an
    enumeration code ``' 1'`` is not ``'1'``. The suggestion is the stripped
    value. ``Id`` is covered by its own checks (leading whitespace is an
    ERROR there); wholly-blank cells are the missing-value checks' business.
    """
    for row in rows:
        for column, cell in row.cells.items():
            if column == "Id" or cell == "":
                continue
            stripped = cell.strip()
            if stripped == cell or stripped == "":
                continue
            yield Finding(
                Level.WARNING, "cell-whitespace",
                f"{column} has leading or trailing whitespace",
                line=row.line, column=column, value=cell, suggestion=stripped,
            )


# --- lexical spaces -----------------------------------------------------

_LEXICAL = {
    "integer": re.compile(r"[+-]?\d+"),
    "decimal": re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)"),
    "float": re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?|NaN|[+-]?INF"),
    "double": re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?|NaN|[+-]?INF"),
    "boolean": re.compile(r"true|false|0|1"),
    "date": re.compile(r"-?\d{4}-\d{2}-\d{2}(Z|[+-]\d{2}:\d{2})?"),
    "datetime": re.compile(r"-?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?"),
    "time": re.compile(r"\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?"),
}


def _fits_datatype(value: str, datatype: str) -> bool | None:
    """Whether ``value`` fits the datatype's lexical space; None = uncheckable.

    Builtin numeric/boolean/temporal ranges get hand-written lexical checks;
    custom types are checked against their declared pattern when they have
    one. String-like datatypes accept anything (None: nothing to check).
    """
    pattern = _LEXICAL.get(BUILTIN_RANGES.get(datatype, ""))
    if pattern is not None:
        return pattern.fullmatch(value) is not None
    custom = CUSTOM_TYPES.get(datatype)
    if isinstance(custom, CustomType) and custom.pattern:
        return re.fullmatch(custom.pattern, value) is not None
    return None


def _parsed_enumeration(row: RawRow) -> list | None:
    """The row's parsed enumeration items, or None (blank or malformed)."""
    cell = row.get("Enumeration")
    if cell.strip() == "":
        return None
    try:
        return parse_enumeration(cell)
    except ParseError:
        return None  # malformed-enumeration reports it


# --- aliases -----------------------------------------------------------------

def check_aliases(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    """Alias identity problems.

    An alias exists to key an old datafile header to an element, so an alias
    that equals any element's ``Id`` (WARNING) or is claimed by two elements
    (WARNING) breaks that keying. Empty segments from stray pipes (``a||b``,
    a trailing ``|``) are phantom aliases (WARNING, with the cleaned cell as
    the suggestion).
    """
    if "Aliases" not in columns_present:
        return
    rows = list(rows)
    ids = {row.get("Id").strip() for row in rows if row.get("Id").strip()}
    first_claim: dict[str, int] = {}
    for row in rows:
        cell = row.get("Aliases")
        if cell.strip() == "":
            continue
        segments = cell.split("|")
        aliases = [segment.strip() for segment in segments if segment.strip()]
        if len(aliases) != len(segments):
            yield Finding(
                Level.WARNING, "empty-list-segment",
                "Aliases has an empty segment (a doubled or trailing pipe)",
                line=row.line, column="Aliases", value=cell,
                suggestion="|".join(aliases),
            )
        for alias in aliases:
            if alias in ids:
                yield Finding(
                    Level.WARNING, "alias-id-collision",
                    f"alias {alias!r} is also an element Id — datafile headers "
                    "using it cannot be keyed unambiguously",
                    line=row.line, column="Aliases", value=alias,
                )
            if alias in first_claim and first_claim[alias] != row.line:
                yield Finding(
                    Level.WARNING, "duplicate-alias",
                    f"alias {alias!r} is claimed by more than one element "
                    f"(first on line {first_claim[alias]})",
                    line=row.line, column="Aliases", value=alias,
                )
            first_claim.setdefault(alias, row.line)


# --- examples ----------------------------------------------------------------

def check_examples(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    """Examples SHOULD conform (the specification's word) — and it's checkable.

    Each example is checked against the field's Enumeration membership, its
    Pattern, and its Datatype's lexical space, whichever apply. Stray pipes
    yield the same empty-segment warning as aliases.
    """
    if "Examples" not in columns_present:
        return
    for row in rows:
        cell = row.get("Examples")
        if cell.strip() == "":
            continue
        segments = cell.split("|")
        examples = [segment.strip() for segment in segments if segment.strip()]
        if len(examples) != len(segments):
            yield Finding(
                Level.WARNING, "empty-list-segment",
                "Examples has an empty segment (a doubled or trailing pipe)",
                line=row.line, column="Examples", value=cell,
                suggestion="|".join(examples),
            )
        enumeration = _parsed_enumeration(row)
        legal = {item.value for item in enumeration} if enumeration else None
        pattern = row.get("Pattern").strip()
        try:
            compiled = re.compile(pattern) if pattern else None
        except re.error:
            compiled = None  # malformed-pattern reports it
        datatype = row.get("Datatype").strip()
        for example in examples:
            if legal is not None and example not in legal:
                yield Finding(
                    Level.WARNING, "example-not-in-enumeration",
                    f"example {example!r} is not one of the enumeration's values",
                    line=row.line, column="Examples", value=example,
                )
            if compiled is not None and compiled.fullmatch(example) is None:
                yield Finding(
                    Level.WARNING, "example-pattern-mismatch",
                    f"example {example!r} does not match the field's pattern",
                    line=row.line, column="Examples", value=example,
                )
            if legal is None and _fits_datatype(example, datatype) is False:
                yield Finding(
                    Level.WARNING, "example-datatype-mismatch",
                    f"example {example!r} is not a valid {datatype} value",
                    line=row.line, column="Examples", value=example,
                )


# --- enumeration consistency ---------------------------------------------------

_STANDARD_CODE_VALUES = {item.value for item in STANDARD_MISSING_VALUE_CODES}


def check_enumeration_consistency(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Contradictions within and around an Enumeration cell.

    A value listed twice is meaningless (ERROR); two values sharing a label is
    usually a copy-paste slip (INFO); a value that is also one of the field's
    — or the standard — missing-value codes is ambiguous, since a code cannot
    mean both an answer and "no data" (WARNING); and a value the field's own
    Pattern rejects is a contradiction in the dictionary itself (WARNING).
    """
    if "Enumeration" not in columns_present:
        return
    for row in rows:
        items = _parsed_enumeration(row)
        if not items:
            continue
        seen_values: dict[str, int] = {}
        seen_labels: dict[str, str] = {}
        for item in items:
            count = seen_values.get(item.value, 0)
            seen_values[item.value] = count + 1
            if count == 1:  # report once, on the second sighting
                yield Finding(
                    Level.ERROR, "enumeration-duplicate-value",
                    f"enumeration lists the value {item.value!r} more than once",
                    line=row.line, column="Enumeration", value=item.value,
                )
            label = (item.label or "").strip()
            if label:
                if label in seen_labels and seen_labels[label] != item.value:
                    yield Finding(
                        Level.INFO, "enumeration-duplicate-label",
                        f"enumeration values {seen_labels[label]!r} and "
                        f"{item.value!r} share the label {label!r}",
                        line=row.line, column="Enumeration", value=label,
                    )
                seen_labels.setdefault(label, item.value)

        try:
            field_codes = {
                item.value
                for item in parse_missing_value_codes(row.get("MissingValueCodes"))
            }
        except ParseError:
            field_codes = set()
        for item in items:
            if item.value in field_codes:
                yield Finding(
                    Level.WARNING, "enumeration-missing-code-overlap",
                    f"enumeration value {item.value!r} is also one of the "
                    "field's missing-value codes — it cannot mean both an "
                    "answer and 'no data'",
                    line=row.line, column="Enumeration", value=item.value,
                )
            elif item.value in _STANDARD_CODE_VALUES:
                yield Finding(
                    Level.WARNING, "enumeration-missing-code-overlap",
                    f"enumeration value {item.value!r} is one of the standard "
                    "missing-value codes — it cannot mean both an answer and "
                    "'no data'",
                    line=row.line, column="Enumeration", value=item.value,
                )

        pattern = row.get("Pattern").strip()
        if pattern:
            try:
                compiled = re.compile(pattern)
            except re.error:
                continue  # malformed-pattern reports it
            for item in items:
                if compiled.fullmatch(item.value) is None:
                    yield Finding(
                        Level.WARNING, "enumeration-pattern-mismatch",
                        f"enumeration value {item.value!r} does not match the "
                        "field's own pattern",
                        line=row.line, column="Enumeration", value=item.value,
                    )


# --- precondition values -------------------------------------------------------

def check_precondition_values(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Value-level precondition checks (the structural ones live in
    :func:`check_preconditions`).

    A compared value should belong to the referenced field's enumeration
    (equality-style predicates), or at least fit its datatype's lexical
    space. A blank cell means "field is blank", so the non-blank test
    (``<> ""``) is always fine.
    """
    if "Precondition" not in columns_present:
        return
    rows = list(rows)
    fields = {row.get("Id").strip(): row for row in rows if row.get("Id").strip()}
    for row in rows:
        cell = row.get("Precondition")
        if cell.strip() == "":
            continue
        try:
            condition = parse_precondition(cell)
        except ParseError:
            continue  # malformed-precondition reports it
        for atom in precondition_atoms(condition):
            referenced = fields.get(atom.field)
            if referenced is None:
                continue  # unknown-precondition-field reports it
            if isinstance(atom, Comparison):
                ordering = atom.op in ("<", "<=", ">", ">=")
                values = [] if atom.op == "<>" and atom.value == "" else [atom.value]
            elif isinstance(atom, Contains):
                ordering = False
                values = [atom.value]
            else:  # InSet
                ordering = False
                values = list(atom.values)
            enumeration = _parsed_enumeration(referenced)
            legal = {item.value for item in enumeration} if enumeration else None
            datatype = referenced.get("Datatype").strip()
            for value in values:
                if legal is not None and not ordering:
                    if value not in legal:
                        yield Finding(
                            Level.WARNING, "precondition-value-not-in-enumeration",
                            f"precondition compares {atom.field!r} with "
                            f"{value!r}, which is not one of its enumeration's "
                            "values",
                            line=row.line, column="Precondition", value=value,
                        )
                elif _fits_datatype(value, datatype) is False:
                    yield Finding(
                        Level.WARNING, "precondition-value-datatype",
                        f"precondition compares {atom.field!r} with {value!r}, "
                        f"which is not a valid {datatype} value",
                        line=row.line, column="Precondition", value=value,
                    )


# --- unit hygiene --------------------------------------------------------------

_NON_QUANTITY_DATATYPES = frozenset({"boolean", "anyURI", "date", "dateTime", "time"})


def check_unit_hygiene(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    """Unit spelling and placement (both INFO).

    A unit with a known UCUM equivalent gets it as the suggestion — informal
    spellings, misprints, and word forms resolve through ``dd_core.ucum``
    (a valid code outside the curated subset stays silent rather than
    guessed at). A unit on a boolean/URI/temporal field is almost certainly
    a column slip.
    """
    if "Unit" not in columns_present:
        return
    for row in rows:
        unit = row.get("Unit").strip()
        if unit == "":
            continue
        datatype = row.get("Datatype").strip()
        if BUILTIN_RANGES.get(datatype, datatype) in _NON_QUANTITY_DATATYPES:
            yield Finding(
                Level.INFO, "unit-on-non-quantity",
                f"Unit {unit!r} on a {datatype} field — units belong on "
                "quantity fields",
                line=row.line, column="Unit", value=unit,
            )
        if ucum_unit(unit) is None:
            suggested = suggest_ucum(unit)
            if suggested is not None:
                yield Finding(
                    Level.INFO, "unit-suggestion",
                    f"Unit {unit!r} has a UCUM spelling: {suggested.code!r} "
                    f"({suggested.name})",
                    line=row.line, column="Unit", value=unit,
                    suggestion=suggested.code,
                )


def check_boolean_enumeration(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """A boolean field with an enumeration mixes two representations (INFO)."""
    if "Enumeration" not in columns_present or "Datatype" not in columns_present:
        return
    for row in rows:
        if row.get("Enumeration").strip() == "":
            continue
        if BUILTIN_RANGES.get(row.get("Datatype").strip()) == "boolean":
            yield Finding(
                Level.INFO, "boolean-with-enumeration",
                "boolean field also declares an enumeration — pick one "
                "representation (boolean, or a coded integer enumeration)",
                line=row.line, column="Datatype", value="boolean",
            )


# --- labels, descriptions, sections ---------------------------------------------

def check_label_quality(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    """Label nudges (INFO): a label that just repeats the Id, and the same
    label on more than one element (usually a copy-paste slip)."""
    if "Label" not in columns_present:
        return
    first_use: dict[str, int] = {}
    for row in rows:
        label = row.get("Label").strip()
        if label == "":
            continue
        if label == row.get("Id").strip():
            yield Finding(
                Level.INFO, "label-equals-id",
                "Label just repeats the Id — a human-readable label helps",
                line=row.line, column="Label", value=label,
            )
        if label in first_use:
            yield Finding(
                Level.INFO, "duplicate-label",
                f"label {label!r} is also used on line {first_use[label]}",
                line=row.line, column="Label", value=label,
            )
        first_use.setdefault(label, row.line)


def check_description_present(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """A dictionary that has a Description column should fill it (INFO)."""
    if "Description" not in columns_present:
        return
    for row in rows:
        if row.get("Description").strip() == "":
            yield Finding(
                Level.INFO, "description-missing",
                "Description is blank",
                line=row.line, column="Description",
            )


def check_section_runs(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    """A Section that stops and later resumes is usually accidental row
    ordering (INFO) — sections read as contiguous groups."""
    if "Section" not in columns_present:
        return
    closed: set[str] = set()
    current: str | None = None
    for row in rows:
        section = row.get("Section").strip()
        if section == "" or section == current:
            continue
        if current is not None:
            closed.add(current)
        if section in closed:
            yield Finding(
                Level.INFO, "section-fragmented",
                f"section {section!r} resumes after other sections — its "
                "elements are split into non-contiguous runs",
                line=row.line, column="Section", value=section,
            )
            closed.discard(section)
        current = section


# Datatype names that are pure aliases of a semantic builtin: renaming them
# is free (same value space; the schema maps them silently anyway). The
# g*/duration/binary custom types are deliberate rendering choices and stay
# unflagged; the REDCap-style formats are format-harmonization's business.
_PREFERRED_DATATYPE: dict[str, str] = {
    name: range_
    for name, range_ in BUILTIN_RANGES.items()
    if name != range_ and range_ in ("string", "integer")
}


def check_datatype_preferred(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Advisory: prefer the semantic datatype name (INFO; the value is valid).

    ``int``/``short``/``token`` name a storage width or lexical class and map
    silently onto the semantic builtin anyway — the rename is free, so the
    suggestion is safe to apply mechanically.
    """
    if "Datatype" not in columns_present:
        return
    for row in rows:
        name = row.get("Datatype").strip()
        preferred = _PREFERRED_DATATYPE.get(name)
        if preferred is None:
            continue
        yield Finding(
            Level.INFO, "datatype-preferred",
            f"datatype {name!r} names a storage width, not a meaning; "
            f"the semantic type is {preferred!r}",
            line=row.line, column="Datatype", value=name, suggestion=preferred,
        )


# REDCap-style source formats and their harmonized targets. UNLIKE the pure
# aliases above, these truthfully describe the datafile as it is (mm/dd/yyyy
# strings, Unix seconds): changing the dictionary alone would make it lie.
# The recommendation is to harmonize the DATA, then the datatype — so the
# suggestion is for migration pipelines, not for one-click dictionary edits.
# format -> (harmonized target, concrete value example). The example makes
# "harmonize" unambiguous: it is the DATA that changes shape, not just the
# dictionary cell.
_HARMONIZATION_TARGETS: dict[str, tuple[str, str]] = {
    "date_mdy": ("date", "05/27/2014 becomes 2014-05-27"),
    "date_dmy": ("date", "27/05/2014 becomes 2014-05-27"),
    "timestamp": ("dateTime", "1401148800 becomes 2014-05-27T00:00:00Z"),
}


def check_format_harmonization(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Advisory: REDCap-style formats have a harmonized end-state (INFO).

    ``date_mdy``/``date_dmy``/``timestamp`` are valid and honest about the
    source data; the finding records the recommended target (``date`` /
    ``dateTime``) as the suggestion for pipelines that migrate the datafile
    along with the dictionary, and the message shows a concrete value
    transformation so "harmonize" is unambiguous.
    """
    if "Datatype" not in columns_present:
        return
    for row in rows:
        name = row.get("Datatype").strip()
        entry = _HARMONIZATION_TARGETS.get(name)
        if entry is None:
            continue
        target, example = entry
        yield Finding(
            Level.INFO, "format-harmonization",
            f"datatype {name!r} describes REDCap-style source data — valid "
            f"as-is; harmonizing the datafile (and then this field) to "
            f"{target!r} is the recommended end-state (so {example})",
            line=row.line, column="Datatype", value=name, suggestion=target,
        )


_NUMERIC_RANGES = frozenset({"integer", "decimal", "float", "double"})


def check_units(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    """Advisory: a numeric, non-enumerated field with no Unit (INFO).

    Counts and scores are legitimately unitless (UCUM ``1``), so this is a
    nudge rather than a warning — and exactly why it is INFO and ignorable.
    """
    if "Datatype" not in columns_present:
        return
    for row in rows:
        if row.get("Unit").strip() != "" or row.get("Enumeration").strip() != "":
            continue
        if BUILTIN_RANGES.get(row.get("Datatype").strip()) not in _NUMERIC_RANGES:
            continue
        yield Finding(
            Level.INFO, "missing-unit",
            "numeric field has no Unit — a UCUM unit (or '1' for dimensionless "
            "counts and scores) makes values reliably interpretable and is "
            "supported by standards like LinkML",
            line=row.line, column="Unit",
        )


_INTEGER_VALUE = re.compile(r"^-?\d+$")


def check_enumeration_datatype(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Advisory: every enumeration value is an integer but Datatype is not.

    All-integer value sets usually mean the underlying datatype should be
    ``integer`` (INFO, with that as the suggestion).
    """
    if "Enumeration" not in columns_present or "Datatype" not in columns_present:
        return
    for row in rows:
        cell = row.get("Enumeration")
        if cell.strip() == "":
            continue
        try:
            items = parse_enumeration(cell)
        except ParseError:
            continue  # malformed-enumeration reports it
        if not items or not all(_INTEGER_VALUE.match(item.value.strip()) for item in items):
            continue
        datatype = row.get("Datatype").strip()
        if BUILTIN_RANGES.get(datatype) == "integer":
            continue
        yield Finding(
            Level.INFO, "enumeration-integer-datatype",
            f"every enumeration value is an integer but Datatype is {datatype!r}",
            line=row.line, column="Datatype", value=datatype, suggestion="integer",
        )


def check_missing_value_codes(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    if "MissingValueCodes" not in columns_present:
        return
    for row in rows:
        codes = row.get("MissingValueCodes")
        if codes.strip() == "":
            continue
        try:
            parse_missing_value_codes(codes)
        except ParseError as exc:
            yield Finding(
                Level.ERROR, "malformed-missing-value-codes",
                f"missing value codes are malformed: {exc}",
                line=row.line, column="MissingValueCodes", value=codes,
            )


def check_see_also(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "SeeAlso" not in columns_present:
        return
    for row in rows:
        url = row.get("SeeAlso").strip()
        if url == "":
            continue
        # An absolute URL must have a scheme (e.g. https). urlsplit does not
        # raise on ordinary strings, so we check the parsed scheme directly.
        if not urlsplit(url).scheme:
            yield Finding(
                Level.ERROR, "malformed-see-also",
                "SeeAlso is not an absolute URL",
                line=row.line, column="SeeAlso", value=url,
            )


def check_required(rows: Iterable[RawRow], columns_present: set[str]) -> Iterable[Finding]:
    if "Required" not in columns_present:
        return
    for row in rows:
        value = row.get("Required").strip()
        if value and value.lower() != "y":
            yield Finding(
                Level.ERROR, "invalid-required",
                f"invalid Required {value!r} (expected 'y' or blank)",
                line=row.line, column="Required", value=value,
            )


def check_preconditions(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Check every Precondition cell: grammar, references, and predicate typing.

    Per the specification: referenced fields must exist in this dictionary;
    ordering predicates (< <= > >=) are only valid on fields with an ordered
    Datatype; `contains` is only valid on fields with Cardinality `multiple`.
    """
    if "Precondition" not in columns_present:
        return
    rows = list(rows)
    fields = {
        row.get("Id").strip(): row for row in rows if row.get("Id").strip()
    }
    for row in rows:
        cell = row.get("Precondition")
        if cell.strip() == "":
            continue
        try:
            condition = parse_precondition(cell)
        except ParseError as exc:
            yield Finding(
                Level.ERROR, "malformed-precondition",
                f"precondition is malformed: {exc}",
                line=row.line, column="Precondition", value=cell,
            )
            continue
        for atom in precondition_atoms(condition):
            referenced = fields.get(atom.field)
            if referenced is None:
                yield Finding(
                    Level.ERROR, "unknown-precondition-field",
                    f"precondition refers to {atom.field!r}, which is not a "
                    "field in this dictionary",
                    line=row.line, column="Precondition", value=atom.field,
                )
                continue
            if isinstance(atom, Comparison) and atom.op in ("<", "<=", ">", ">="):
                datatype = referenced.get("Datatype").strip()
                if datatype and datatype not in ORDERED_DATATYPES:
                    yield Finding(
                        Level.ERROR, "invalid-precondition-comparison",
                        f"precondition compares {atom.field!r} with "
                        f"{atom.op!r}, but its datatype {datatype!r} is not ordered",
                        line=row.line, column="Precondition", value=atom.field,
                    )
            if isinstance(atom, Contains):
                cardinality = referenced.get("Cardinality").strip().lower()
                if cardinality != "multiple":
                    yield Finding(
                        Level.ERROR, "invalid-precondition-contains",
                        f"precondition uses 'contains' on {atom.field!r}, "
                        "which is not a multivalued field",
                        line=row.line, column="Precondition", value=atom.field,
                    )


def check_duplicate_ids(
    rows: Iterable[RawRow], columns_present: set[str]
) -> Iterable[Finding]:
    """Report Ids that appear on more than one row.

    Not present in the reference Java validator, but the specification treats an
    Id as the unique identifier of a data element, and the converter refuses a
    dictionary with duplicate Ids. Reported against the *second and subsequent*
    occurrences, naming the first.
    """
    if "Id" not in columns_present:
        return
    first_seen_line: dict[str, int] = {}
    for row in rows:
        row_id = row.get("Id").strip()
        if row_id == "":
            continue
        if row_id in first_seen_line:
            yield Finding(
                Level.ERROR, "duplicate-id",
                f"duplicate Id {row_id!r} (first seen on line {first_seen_line[row_id]})",
                line=row.line, column="Id", value=row_id,
            )
        else:
            first_seen_line[row_id] = row.line
