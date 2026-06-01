"""RxNorm client using stdlib urllib only, with local-fallback search.

NO `requests`, NO `httpx`. SPEC section 4.
"""
from __future__ import annotations

import json
import logging
import os
import socket
from typing import Optional
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import Drug


log = logging.getLogger(__name__)


_KEPT_TTY = {"SBD", "SCD", "IN", "BN"}


def _base_url() -> str:
    return os.environ.get("RXNORM_BASE_URL", "https://rxnav.nlm.nih.gov/REST/").rstrip("/") + "/"


def _timeout() -> float:
    try:
        return float(os.environ.get("RXNORM_TIMEOUT_S", "4"))
    except ValueError:
        return 4.0


def _http_get_json(url: str, timeout: float) -> Optional[dict]:
    """Return parsed JSON or None on any failure."""
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "MedSafety/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status < 200 or status >= 300:
                return None
            raw = resp.read()
        return json.loads(raw.decode("utf-8"))
    except (URLError, socket.timeout, TimeoutError, json.JSONDecodeError, ValueError, OSError) as e:
        log.info("rxnorm fetch failed for %s: %s", url, e)
        return None


def _local_search(session: Session, q: str, limit: int = 20) -> list[dict]:
    """Substring search on local Drug rows."""
    if not q:
        return []
    needle = q.strip().lower()
    if not needle:
        return []
    drugs = (
        session.query(Drug)
        .filter(
            or_(
                Drug.name.ilike(f"%{needle}%"),
                Drug.generic_name.ilike(f"%{needle}%"),
            )
        )
        .all()
    )
    drugs.sort(key=lambda d: (len(d.name), d.name.lower()))
    return [
        {
            "id": d.id,
            "rxnorm_cui": d.rxnorm_cui,
            "name": d.name,
            "generic_name": d.generic_name,
            "drug_class": d.drug_class,
        }
        for d in drugs[:limit]
    ]


def search_drugs(session: Session, q: str) -> dict:
    """Search RxNorm by name; fall back to local list on failure."""
    if not q or len(q.strip()) < 2:
        return {"source": "local", "results": []}

    url = f"{_base_url()}drugs.json?name={quote(q.strip())}"
    payload = _http_get_json(url, _timeout())

    if not payload:
        return {"source": "local", "results": _local_search(session, q)}

    try:
        groups = payload.get("drugGroup", {}).get("conceptGroup", []) or []
    except AttributeError:
        groups = []
    if not groups:
        return {"source": "local", "results": _local_search(session, q)}

    results: list[dict] = []
    seen_cuis: set[str] = set()
    for group in groups:
        tty = group.get("tty")
        if tty not in _KEPT_TTY:
            continue
        for cp in group.get("conceptProperties", []) or []:
            cui = str(cp.get("rxcui") or "").strip()
            name = (cp.get("name") or "").strip()
            if not cui or not name or cui in seen_cuis:
                continue
            seen_cuis.add(cui)
            synonym = (cp.get("synonym") or "").strip()

            # Look up local drug by cui to fill class + id when known.
            local = session.query(Drug).filter(Drug.rxnorm_cui == cui).one_or_none()
            if local is not None:
                results.append(
                    {
                        "id": local.id,
                        "rxnorm_cui": local.rxnorm_cui,
                        "name": local.name,
                        "generic_name": local.generic_name,
                        "drug_class": local.drug_class,
                    }
                )
            else:
                results.append(
                    {
                        "id": None,
                        "rxnorm_cui": cui,
                        "name": name,
                        "generic_name": synonym or name,
                        "drug_class": "unknown",
                    }
                )

    if not results:
        return {"source": "local", "results": _local_search(session, q)}

    results.sort(key=lambda r: (len(r["name"]), r["name"].lower()))
    return {"source": "rxnorm", "results": results[:20]}


def fetch_generic_name(cui: str) -> Optional[tuple[str, str]]:
    """Return (generic_name, generic_cui) using RxNorm related.json, or None."""
    if not cui:
        return None
    url = f"{_base_url()}rxcui/{quote(str(cui))}/related.json?tty=IN"
    payload = _http_get_json(url, _timeout())
    if not payload:
        return None
    try:
        groups = payload.get("relatedGroup", {}).get("conceptGroup", []) or []
        if not groups:
            return None
        props = groups[0].get("conceptProperties", []) or []
        if not props:
            return None
        name = (props[0].get("name") or "").strip()
        related_cui = str(props[0].get("rxcui") or "").strip()
        if not name:
            return None
        return name, related_cui
    except (AttributeError, IndexError, KeyError):
        return None
