"""Converter from RADx data dictionary CSV to a LinkML schema.

This package is described in ``linkml/CONVERTER_PLAN.md``. The ``grammar``
subpackage is the parser layer: it turns the in-cell mini-grammars used by RADx
data dictionaries (enumerations, missing-value codes, ontology term lists) into
Python objects. It is the one piece that standard LinkML tooling cannot provide,
because the structure is hidden inside string cells in a bespoke notation.
"""

__all__ = []
