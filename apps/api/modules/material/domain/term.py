"""
Term code maths for F-12 Institute Study Material (ERD 2.3).
"""

from __future__ import annotations

import re


TERM_REGEX = re.compile(r"^(\d{4})-(\d{2})$")


def term_to_ord(term: str) -> int:
    """
    Converts 'YYYY-MM' to integer ordinal (year * 12 + month).
    e.g. '2026-05' -> 2026 * 12 + 5 = 24317.
    """
    m = TERM_REGEX.match(term)
    if not m:
        raise ValueError(f"Invalid term format: {term}. Expected 'YYYY-MM'.")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid month in term: {term}")
    return year * 12 + month


def ord_to_term(ord_val: int) -> str:
    """
    Converts integer ordinal back to 'YYYY-MM'.
    """
    month = ord_val % 12
    year = ord_val // 12
    if month == 0:
        month = 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def validate_term_range(
    applies_from: str, applies_to: str | None
) -> tuple[int, int | None]:
    """
    Validates that applies_from is valid and <= applies_to if provided.
    Returns (applies_from_ord, applies_to_ord).
    """
    from_ord = term_to_ord(applies_from)
    to_ord = term_to_ord(applies_to) if applies_to else None
    if to_ord is not None and to_ord < from_ord:
        raise ValueError(
            f"applies_to ({applies_to}) cannot precede applies_from ({applies_from})"
        )
    return from_ord, to_ord
