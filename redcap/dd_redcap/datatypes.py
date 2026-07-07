"""Map REDCap validation types to the specification's datatype names.

A REDCap text field carries its format in the ``Text Validation Type`` column
(``integer``, ``number_2dp``, ``date_mdy``, ``zipcode``, …). This table maps
each validation name to a datatype name from the data dictionary
specification. Formats with no structured counterpart (ids, emails, phone
numbers, partial dates) map to ``string`` — never silently to something
stricter than the data warrants.
"""

from __future__ import annotations

from . import headers
from .choices import parse_choices
from .headers import RedCapSheet

# REDCap validation name (lowercase) -> spec datatype name.
VALIDATION_DATATYPES: dict[str, str] = {
    "integer": "integer",
    "number": "decimal",
    "number_1dp": "decimal",
    "number_2dp": "decimal",
    "number_3dp": "decimal",
    "number_4dp": "decimal",
    "date_ymd": "date",  # Y-M-D is the XSD lexical form of a date
    "date_mdy": "date_mdy",
    "date_dmy": "date_dmy",
    "datetime_seconds_ymd": "dateTime",
    "datetime_seconds_mdy": "date_mdy",
    "datetime_seconds_dmy": "date_dmy",
    "time": "time",
    "time_hh_mm_ss": "time",
    # Formats with no structured spec counterpart -> string:
    # alpha_id, alpha-dash, custom_id, dash-id, email, ip_address, lab_value,
    # alpha_only, mac_address, mrn_78d, phone, zipcode, api_token, sunet_id,
    # date_my, date_ym (partial dates are not valid xsd:date values), ...
}

_DEFAULT = "string"


def extract_datatype(sheet: RedCapSheet, row: list[str]) -> str:
    """The spec datatype name for one REDCap row.

    A field with choices is typed by its choice values: ``integer`` when the
    first value is all digits, ``string`` otherwise. A text field is typed by
    its validation name via :data:`VALIDATION_DATATYPES`, with one REDCap
    idiosyncrasy honoured: validation ``text`` plus a ``MM/DD/YYYY`` field
    note means a US-format date (``date_mdy``). Everything unrecognised is
    ``string``.
    """
    choices = parse_choices(sheet.get(row, headers.CHOICES))
    if choices:
        first_value = next(iter(choices))
        return "integer" if first_value.isdigit() else "string"

    validation = sheet.get(row, headers.TEXT_VALIDATION).lower()
    if not validation:
        return _DEFAULT
    if validation == "text":
        note = sheet.get(row, headers.FIELD_NOTE)
        if note.strip().upper() == "MM/DD/YYYY":
            return "date_mdy"
    return VALIDATION_DATATYPES.get(validation, _DEFAULT)
