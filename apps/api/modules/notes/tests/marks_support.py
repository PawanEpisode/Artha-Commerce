"""Builders and a thin client wrapper for the marks tests: a document of the student and mark bodies that pass validation."""

from __future__ import annotations

import uuid

from modules.coverage.tests.conftest import OTHER, USER  # noqa: F401 - the two students of the shared `api` fixtures
from modules.notes.models import Document

from .factories import make_document

QUADS = {"quads": [[0.10, 0.10, 0.30, 0.02]]}
RECT = {"rect": [0.10, 0.20, 0.20, 0.10]}


def new_document(user_id=USER, **fields) -> Document:
    return make_document(user_id, **fields)


def body(document, kind="highlight", **extra) -> dict:
    """A valid `PUT annotations/{id}/` body."""
    geometry = {"highlight": QUADS, "underline": QUADS, "area": RECT, "sticky": {"pt": [0.5, 0.5]}}.get(kind, QUADS)
    if kind == "textbox":
        geometry = {"rect": [0.1, 0.1, 0.3, 0.1], "fs": 0.018}
    if kind == "bookmark":
        geometry = {"y": 0.3}
    return {"document_id": str(document.id), "kind": kind, "page": 1, "geometry": geometry, "color": "y", **extra}


def put(api, document, mark_id=None, kind="highlight", **extra):
    """Creates (or writes) a mark and returns `(response, id)`."""
    mark_id = mark_id or str(uuid.uuid4())
    return api.put(f"/notes/annotations/{mark_id}/", body(document, kind, **extra)), mark_id


def create(api, document, kind="highlight", **extra) -> dict:
    res, _ = put(api, document, None, kind, **extra)
    assert res.status_code == 201, res.json_body
    return res.json_body["annotation"]


def edit(api, mark, **fields):
    """`PUT` against the mark's current revision (same fields shape as a create)."""
    payload = {"document_id": mark["document_id"], "base_rev": mark["rev"], **fields}
    return api.put(f"/notes/annotations/{mark['id']}/", payload)


def remove(api, mark_id, base_rev=None):
    return api._send("delete", f"/notes/annotations/{mark_id}/", {} if base_rev is None else {"base_rev": base_rev})


def delta(api, document, since=0, limit=500):
    return api.get(f"/notes/documents/{document.id}/annotations/?since_seq={since}&limit={limit}").json_body
