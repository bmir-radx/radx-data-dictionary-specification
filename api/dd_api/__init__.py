"""A high-level Python API for data dictionaries.

Load a dictionary and work with typed, parsed objects instead of raw CSV
cells::

    from dd_api import DataDictionary

    dd = DataDictionary.load("my_dictionary.csv")

    for element in dd:                     # elements, in file order
        print(element.id, element.label, element.datatype)
        for choice in element.enumeration: # parsed "value"=[label](iri) pairs
            print(" ", choice.value, choice.label)

    age = dd["age"]                        # lookup by id (KeyError if absent)
    "weight" in dd                         # membership test by id
    dd.sections                            # section names, in order
    schema_yaml = dd.to_linkml()           # the LinkML rendering

The model itself lives in :mod:`dd_api.model`; the parsing it builds on
(datatype names, the in-cell grammars, LinkML conversion) comes from the
sibling ``dd_converter`` package. The types a caller touches are re-exported
here so ``dd_api`` is the only import needed:

* :class:`DataDictionary`, :class:`DataElement` — the model.
* :class:`EnumItem` — one enumeration / missing-value-code choice.
* :class:`UnitOfMeasure` — a structured unit (name, symbol, UCUM code).
* :class:`ReadError` — what :meth:`DataDictionary.load` raises on a bad
  dictionary.
* :class:`EmitOptions` — options for :meth:`DataDictionary.to_linkml`.
"""

from dd_converter import EmitOptions, ReadError, UnitOfMeasure
from dd_converter.grammar import EnumItem

from .model import DataDictionary, DataElement

__all__ = [
    "DataDictionary",
    "DataElement",
    "EnumItem",
    "UnitOfMeasure",
    "ReadError",
    "EmitOptions",
]
