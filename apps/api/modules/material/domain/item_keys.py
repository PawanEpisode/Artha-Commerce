"""
Item key generation and content hash computation (F-12 ERD 2.5, 2.6).
"""

from __future__ import annotations

import hashlib
import re


KIND_SHORT_MAP = {
    "illustration": "ill",
    "example": "ex",
    "exercise": "exer",
    "mcq": "mcq",
    "true_false": "tf",
    "theory": "th",
    "practical": "pr",
    "case_study": "cs",
}

SHORT_KIND_MAP = {v: k for k, v in KIND_SHORT_MAP.items()}


def kind_to_short(kind: str) -> str:
    return KIND_SHORT_MAP.get(kind, kind[:4])


def make_item_key(unit_key: str, kind: str, seq: int) -> str:
    """
    Generates a stable item key:
    {unit_key}:{kind_short}:{seq:04d}
    e.g. m1-ch3:ill:0007
    """
    short_k = kind_to_short(kind)
    clean_unit = re.sub(r"[^a-zA-Z0-9_-]", "", unit_key).lower()
    return f"{clean_unit}:{short_k}:{seq:04d}"


def compute_content_hash(kind: str, descriptor: str | None) -> str | None:
    """
    For reference items: SHA-256 of kind plus normalised descriptor
    (only when the descriptor has at least 20 characters).
    """
    if not descriptor or len(descriptor.strip()) < 20:
        return None
    norm = re.sub(r"\s+", " ", descriptor.strip().lower())
    payload = f"{kind}:{norm}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
