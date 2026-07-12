"""Identifier hygiene shared by the tools.

The specification imposes no restrictions on ``Id`` values (spaces and any
characters are legal), but tools that must produce schema-safe names — the
LinkML emitter, and the validator when it explains what a rename would look
like — share this one sanitisation rule so they can never disagree.
"""

from __future__ import annotations

import re


def sanitize_identifier(name: str) -> str:
    """Turn an arbitrary Id/Section into a schema-safe name.

    Non-word characters become underscores (collapsed), leading/trailing
    underscores are stripped, and a leading digit is prefixed. The original
    value is preserved elsewhere (slot title / ``original_id`` annotation),
    so this only affects the schema-internal name.
    """
    safe = re.sub(r"\W+", "_", name.strip()).strip("_")
    if not safe:
        safe = "_"
    if safe[0].isdigit():
        safe = f"x_{safe}"
    return safe
