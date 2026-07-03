"""Render the dictionary model to JSON."""

from __future__ import annotations

import dataclasses
import json

from .model import Dictionary


def render_json(dictionary: Dictionary, *, indent: int = 2) -> str:
    """Serialise the dictionary model to a pretty-printed JSON string.

    Computed properties (``is_multivalued``, ``has_enumeration``) are dropped;
    only the stored fields are emitted, so the JSON mirrors the model structure.
    """
    return json.dumps(dataclasses.asdict(dictionary), indent=indent, ensure_ascii=False)
