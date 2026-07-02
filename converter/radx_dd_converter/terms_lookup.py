"""Look up human-readable names for ontology term identifiers.

Given the CURIEs / IRIs used in a data dictionary's ``Terms`` and enumeration
``meaning`` values, resolve each to its label via the EBI Ontology Lookup
Service (OLS4). Lookups are opt-in (the converter is network-free by default);
failures are skipped, never fatal.

There is no true batch endpoint on OLS4 (repeated ``iri`` / ``short_form``
parameters are AND-ed), so unique terms are resolved concurrently with a small
thread pool and cached.
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
_OBO_PURL = "http://purl.obolibrary.org/obo/"

_DEFAULT_TIMEOUT = 15.0
_DEFAULT_WORKERS = 8


def _to_iri(term: str) -> Optional[str]:
    """Expand a term to a full IRI for lookup, or return it if already an IRI.

    OBO-style CURIEs (``MONDO:0004979``) expand deterministically to
    ``http://purl.obolibrary.org/obo/MONDO_0004979``. A full ``http(s)://`` IRI
    is returned as-is. Anything else (unknown CURIE shape) returns ``None`` and
    is skipped.
    """
    if term.startswith("http://") or term.startswith("https://"):
        return term
    if ":" in term:
        idspace, local_id = term.split(":", 1)
        if idspace and local_id and "/" not in term:
            return f"{_OBO_PURL}{idspace}_{local_id}"
    return None


def _fetch_label(term: str, timeout: float) -> Optional[str]:
    """Resolve one term to its label via OLS4, or ``None`` on any failure."""
    iri = _to_iri(term)
    if iri is None:
        return None
    query = urllib.parse.urlencode({"iri": iri})
    url = f"{OLS4_TERMS_URL}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
        terms = data.get("_embedded", {}).get("terms", [])
        for t in terms:
            label = t.get("label")
            if label:
                return label
        return None
    except Exception as exc:  # network error, timeout, bad JSON, HTTP error
        logger.warning("Term lookup failed for %s: %s", term, exc)
        return None


def lookup_labels(
    terms: Iterable[str],
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    workers: int = _DEFAULT_WORKERS,
) -> Dict[str, str]:
    """Resolve many terms to labels, concurrently and de-duplicated.

    Returns a mapping of ``term -> label`` containing only the terms that
    resolved successfully; unresolved terms are simply absent (and a warning is
    logged for each). The input order does not matter and duplicates are
    collapsed.
    """
    unique = sorted({t.strip() for t in terms if t and t.strip()})
    if not unique:
        return {}

    results: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for term, label in zip(
            unique, pool.map(lambda t: _fetch_label(t, timeout), unique)
        ):
            if label:
                results[term] = label
    logger.info("Resolved %d/%d unique terms.", len(results), len(unique))
    return results
