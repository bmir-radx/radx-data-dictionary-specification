"""The default set of missing-value codes (originally from RADx).

Per the specification, this standard set of codes always applies to a
``MissingValueCodes`` field; any codes given in a field's cell *augment* it. The
emitter renders these as a single shared ``StandardMissingValueCodes`` enum that
enumerated slots reference (see ``linkml/CONVERTER_PLAN.md``, Option 3).

The codes are stored here as the exact default-value string from the
specification and parsed with the converter's own parser, so this module cannot
drift from the enumeration grammar or transcribe a code incorrectly.
"""

from __future__ import annotations


from .grammar import EnumItem, parse_missing_value_codes

# The "Standard Codes (Default value)" block from
# radx-data-dictionary-specification.md, copied verbatim.
STANDARD_MISSING_VALUE_CODES_TEXT = (
    '"-9999"=[Reason Unknown] | "-9980"=[Not Sent to Data Hub] '
    '| "-9981"=[Data Transfer Agreement] '
    '| "-9982"=[No Participant Consent To Share] '
    '| "-9983"=[Not Available Or Mappable] '
    '| "-9984"=[Data Lost Or Inaccessible] | "-9985"=[Data Invalid] '
    '| "-9986"=[Anonymization Or Privacy Concerns] '
    '| "-9987"=[Other Unsent Reason Not Specified] '
    '| "-9960"=[Not Entered By Originator] | "-9961"=[Omitted This Value] '
    '| "-9962"=[Originator Chose to Omit] | "-9963"=[Question Not Applicable] '
    '| "-9964"=[Answer Not Known] | "-9965"=[Record Not Provided] '
    '| "-9966"=[All Originators Omitted Element] '
    '| "-9967"=[CDE Omitted With Exception] '
    '| "-9968"=[Other Unentered Reason Not Specified] '
    '| "-9940"=[Not Presented To Participant] | "-9941"=[Skip Logic] '
    '| "-9942"=[No Participant Consent to Ask] '
    '| "-9943"=[CDE Not Presented Due to Exception] '
    '| "-9944"=[Element Never Presented for Collection] '
    '| "-9945"=[Process Error] '
    '| "-9946"=[Other Unpresented Reason Not Specified]'
)

# Parsed once at import; the canonical list of standard codes.
STANDARD_MISSING_VALUE_CODES: list[EnumItem] = parse_missing_value_codes(
    STANDARD_MISSING_VALUE_CODES_TEXT
)

# The name of the shared enum the emitter generates for these codes.
STANDARD_ENUM_NAME = "StandardMissingValueCodes"


def parse_missing_value_codes_file(path) -> list[EnumItem]:
    """Read a missing-value-codes override from a file.

    The file contains the same enumeration-cell grammar as a ``MissingValueCodes``
    cell (``"code"=[label] | ...``). Returns the parsed codes, which callers can
    pass to the emitter to replace the built-in default set. An empty/blank file
    yields an empty list (meaning "no shared missing-value-codes enum").
    """
    from pathlib import Path

    text = Path(path).read_text(encoding="utf-8-sig")
    return parse_missing_value_codes(text)
