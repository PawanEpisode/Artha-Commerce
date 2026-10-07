"""Tag names (ERD 2.8): uniqueness is judged on a normal form, display keeps what the student typed."""

from __future__ import annotations

import unicodedata

MAX_NAME = 30


def normalise_tag(name: str) -> str:
    """NFKC, lower case, internal whitespace collapsed: "  GST  Input " and "gst input" are one tag."""
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


def clean_tag_name(name: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", name).split())
