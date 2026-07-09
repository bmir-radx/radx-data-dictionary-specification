"""A high-level Python API for data dictionaries.

New here? ``COOKBOOK.md`` (next to this package) has ten pasteable recipes
with their output, and every method's docstring carries a runnable example —
``help(DataDictionary.load)`` is a good first stop.

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

The model itself lives in :mod:`dd_api.model`; the parsing it builds on comes
from the sibling ``dd_core`` package (reading, datatype names, the in-cell
grammars) and the LinkML conversion from ``dd_linkml``. Every type the model
hands back or raises is re-exported here, so day-to-day use needs only
``dd_api``:

* :class:`DataDictionary`, :class:`DataElement` — the model.
* :class:`EnumItem` — one enumeration / missing-value-code choice.
* :class:`UnitOfMeasure` — a structured unit (name, symbol, UCUM code).
* :class:`Row` — the raw row behind an element (``element.row``).
* :class:`ReadError` — what loading raises on a bad dictionary.
* :class:`EmitOptions` — options for :meth:`DataDictionary.to_linkml`.

(The lower-level functions themselves — reading raw rows in ``dd_core``,
converting schemas in ``dd_linkml`` — import from those when working below
the model.)
"""

from dd_core import ReadError, Row, UnitOfMeasure
from dd_core.grammar import EnumItem
from dd_linkml import EmitOptions

from .model import DataDictionary, DataElement

__all__ = [
    "DataDictionary",
    "DataElement",
    "EnumItem",
    "UnitOfMeasure",
    "Row",
    "ReadError",
    "EmitOptions",
]
