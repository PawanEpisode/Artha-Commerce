"""
Student name rules as pure functions (PRD FR-F16-2): trimmed, whitespace collapsed, NFC, 1 to 60 characters, no control
or bidirectional-override characters (they can reorder text in the header and in emails). Zero-width joiners are allowed
because Indic scripts need them.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

NAME_MIN = 1
NAME_MAX = 60

# Embedding, override and isolate controls plus the line and paragraph separators.
_FORBIDDEN = {chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A), 0x2028, 0x2029, 0x200E, 0x200F)}
_SPACES = re.compile(r"\s+")


class InvalidName(ValueError):
    """The message is shown to the student as the field error."""


def normalize_name(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw or "")
    if any(ch in _FORBIDDEN or unicodedata.category(ch) == "Cc" and ch not in "\t\n\r " for ch in text):
        raise InvalidName("Use letters, numbers and normal punctuation only.")
    text = _SPACES.sub(" ", text).strip()
    if len(text) < NAME_MIN:
        raise InvalidName("Enter your name.")
    if len(text) > NAME_MAX:
        raise InvalidName(f"Use {NAME_MAX} characters or fewer.")
    return text


def first_name(full_name: str) -> str:
    return full_name.split(" ", 1)[0] if full_name else ""


def suggested_name(claims: Mapping[str, Any], email: str = "") -> str:
    """
    Prefill for the onboarding form, never stored until the student confirms: the provider's name (Google), else the
    email's local part made readable ("aarav.mehta2@x.com" becomes "Aarav Mehta"). Empty when nothing usable.
    """
    meta = claims.get("user_metadata") or {}
    for key in ("full_name", "name"):
        candidate = meta.get(key)
        if isinstance(candidate, str):
            try:
                return normalize_name(candidate)
            except InvalidName:
                continue
    local = re.sub(r"\d+", "", (email or claims.get("email") or "").split("@", 1)[0])
    words = [w for w in re.split(r"[._\-+]+", local) if w]
    try:
        return normalize_name(" ".join(w.capitalize() for w in words)) if words else ""
    except InvalidName:
        return ""
