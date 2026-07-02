"""Look up human-readable names for ontology term identifiers.

Given the CURIEs / IRIs used in a data dictionary's ``Terms`` and enumeration
``meaning`` values, resolve each to its label using a selectable resolver:

* ``ols4`` — the EBI Ontology Lookup Service (open, no key required);
* ``bioportal`` — BioPortal (requires an API key).

Lookups are opt-in (the converter is network-free by default). There is no true
batch endpoint on either service (repeated id parameters are AND-ed), so unique
terms are resolved concurrently with a small thread pool and cached. Failures
are skipped, never fatal.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, Optional

logger = logging.getLogger(__name__)

OLS4_TERMS_URL = "https://www.ebi.ac.uk/ols4/api/terms"
BIOPORTAL_CLASS_URL = "https://data.bioontology.org/ontologies/{ont}/classes/{iri}"
# Also defined in emit.py; kept independent to avoid coupling the modules.
_OBO_PURL = "http://purl.obolibrary.org/obo/"

_DEFAULT_TIMEOUT = 15.0
_DEFAULT_WORKERS = 8

RESOLVERS = ("ols4", "bioportal")


class LookupError_(Exception):
    """Raised for a configuration problem (e.g. BioPortal selected without a key).

    The trailing underscore avoids shadowing the built-in ``LookupError``.
    """


def _to_iri(term: str) -> Optional[str]:
    """Expand a term to a full IRI, or return it if already an IRI.

    OBO-style CURIEs (``MONDO:0004979``) expand deterministically to
    ``http://purl.obolibrary.org/obo/MONDO_0004979``. A full ``http(s)://`` IRI
    is returned as-is. Anything else returns ``None`` and is skipped.
    """
    if term.startswith("http://") or term.startswith("https://"):
        return term
    if ":" in term:
        idspace, local_id = term.split(":", 1)
        if idspace and local_id and "/" not in term:
            return f"{_OBO_PURL}{idspace}_{local_id}"
    return None


def _curie_prefix(term: str) -> Optional[str]:
    """Return the id-space of a CURIE (used as the BioPortal ontology acronym)."""
    if ":" in term and not term.startswith(("http://", "https://")):
        return term.split(":", 1)[0]
    return None


def _get_json(url: str, timeout: float, headers: Optional[dict] = None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _fetch_ols4(term: str, timeout: float, _key: Optional[str]) -> Optional[str]:
    iri = _to_iri(term)
    if iri is None:
        return None
    url = f"{OLS4_TERMS_URL}?{urllib.parse.urlencode({'iri': iri})}"
    data = _get_json(url, timeout)
    for term_obj in data.get("_embedded", {}).get("terms", []):
        if term_obj.get("label"):
            return term_obj["label"]
    return None


def _fetch_bioportal(term: str, timeout: float, apikey: Optional[str]) -> Optional[str]:
    iri = _to_iri(term)
    ont = _curie_prefix(term)
    if iri is None or ont is None or not apikey:
        return None
    url = BIOPORTAL_CLASS_URL.format(
        ont=urllib.parse.quote(ont, safe=""),
        iri=urllib.parse.quote(iri, safe=""),
    )
    data = _get_json(
        url, timeout, headers={"Authorization": f"apikey token={apikey}"}
    )
    return data.get("prefLabel")


_FETCHERS = {"ols4": _fetch_ols4, "bioportal": _fetch_bioportal}


def lookup_labels(
    terms: Iterable[str],
    *,
    resolver: str = "ols4",
    apikey: Optional[str] = None,
    timeout: float = _DEFAULT_TIMEOUT,
    workers: int = _DEFAULT_WORKERS,
) -> Dict[str, str]:
    """Resolve many terms to labels, concurrently and de-duplicated.

    ``resolver`` selects the source (``"ols4"`` or ``"bioportal"``). BioPortal
    requires ``apikey``. Returns ``term -> label`` for terms that resolved;
    unresolved terms are absent (a warning is logged for each).
    """
    if resolver not in _FETCHERS:
        raise LookupError_(f"Unknown resolver {resolver!r}; choose one of {RESOLVERS}.")
    if resolver == "bioportal" and not apikey:
        raise LookupError_(
            "The 'bioportal' resolver requires an API key (set BIOPORTAL_API_KEY "
            "or pass --bioportal-apikey)."
        )

    fetch = _FETCHERS[resolver]
    unique_terms = sorted({t.strip() for t in terms if t and t.strip()})
    if not unique_terms:
        return {}

    def resolve_one(term: str) -> Optional[str]:
        try:
            return fetch(term, timeout, apikey)
        except Exception as exc:  # network error, timeout, bad JSON, HTTP error
            logger.warning("Term lookup failed for %s (%s): %s", term, resolver, exc)
            return None

    results: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for term, label in zip(unique_terms, pool.map(resolve_one, unique_terms)):
            if label:
                results[term] = label
    logger.info(
        "Resolved %d/%d unique terms via %s.", len(results), len(unique_terms), resolver
    )
    return results
