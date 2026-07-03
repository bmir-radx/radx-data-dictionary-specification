"""Render a data dictionary to human-readable HTML or JSON.

A vocabulary-neutral printer: it groups a dictionary's data elements by section
and renders each as a card (id, label, facets, description, enumeration). See
``PRINTER_PLAN.md``. Input is loaded via the sibling ``dd_converter``
package (from a data dictionary CSV or a generated LinkML schema).
"""

from .model import Choice, Dictionary, Record, Section

__all__ = ["Choice", "Record", "Section", "Dictionary"]
