"""Parse the RADx ``Terms`` cell into a list of ontology term identifiers.

Per the specification, multiple term identifiers are separated by white space
(space U+0020 or non-breaking space U+00A0) or newline characters (U+000A). Each
term is a full IRI or a compact OBO id (e.g. ``UBERON:0001836``). This module
only tokenises the cell; it does not validate that each token is a well-formed
IRI/CURIE (that is left to the emitter, which decides how strict to be).
"""

from __future__ import annotations

import re
from typing import List

# The separators the spec allows between terms: ASCII space, non-breaking space,
# tab, and newline. Any run of these is a single separator.
_SEPARATOR = re.compile(r"[  \t\r\n]+")


def parse_terms(cell: str) -> List[str]:
    """Split a ``Terms`` cell into its individual term identifiers.

    A blank or whitespace-only cell yields an empty list. Leading and trailing
    white space is ignored; runs of separators collapse to one.
    """
    if cell is None:
        return []
    stripped = _SEPARATOR.sub(" ", cell).strip()
    if stripped == "":
        return []
    return stripped.split(" ")
