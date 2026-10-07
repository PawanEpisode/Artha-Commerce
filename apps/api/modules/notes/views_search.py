"""The R2 part of `GET search/` (PDF pages and marks), kept out of `views.py` so that module stays small."""

from __future__ import annotations

from . import selectors
from . import serializers_documents as out


def pdf_search_payload(
    user_id, q: str, *, scope: str, limit: int, first_page: bool, flt
) -> tuple[list[dict], dict | None]:
    """
    The R2 part of `GET search/`: `(items, meta)`. `scope=pdf` is up to 100 ranked page hits; `highlights` up to 100 text marks;
    `all` adds the top `limit` of each to the FIRST page of notes only (a ranked list of three kinds has no common cursor).
    `meta` (`indexing_documents`, `not_searchable`) goes with `pdf` and `all`.
    """
    cap = 100 if scope != "all" else limit
    items: list[dict] = []
    meta = None
    if scope in ("highlights", "all") and (first_page or scope == "highlights"):
        items += [out.mark_hit(h) for h in selectors.search_marks(user_id, q, limit=cap, flt=flt)]
    if scope in ("pdf", "all"):
        found = selectors.search_pdf(user_id, q, limit=cap if first_page else 0, flt=flt)
        meta = {
            "indexing_documents": found.indexing_documents,
            "not_searchable": [{"document_id": n["document_id"], "reason": n["reason"]} for n in found.not_searchable],
        }
        if first_page or scope == "pdf":
            items += [out.pdf_hit(h) for h in found.hits]
    return items, meta
