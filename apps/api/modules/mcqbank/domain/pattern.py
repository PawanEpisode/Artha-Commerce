"""
Pattern resolution domain logic (F-05 ERD 2.2, 3.5).
Resolves active and verified exam patterns for a subject and target date.
Scheme-specific pattern preferred over a generic null-scheme pattern.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any


def resolve_pattern_profile(
    profiles: Sequence[Any],
    target_date: datetime.date,
    scheme_id: Any | None = None,
) -> Any | None:
    """
    Selects the best active and verified PatternProfile for target_date.
    Prefers matching scheme_id over scheme_id is None.
    Breaks ties by latest effective_from.
    """
    candidates = []
    for p in profiles:
        if getattr(p, "status", None) != "active" or not getattr(p, "verified", False):
            continue
        eff_from = getattr(p, "effective_from", None)
        eff_to = getattr(p, "effective_to", None)
        if eff_from and eff_from > target_date:
            continue
        if eff_to and eff_to < target_date:
            continue
        candidates.append(p)

    if not candidates:
        return None

    # Sort key: (matches scheme, effective_from desc)
    def sort_key(p: Any):
        p_scheme = getattr(p, "scheme_id", None)
        matches_scheme = 1 if (scheme_id is not None and p_scheme == scheme_id) else (0 if p_scheme is None else -1)
        eff_from = getattr(p, "effective_from", datetime.date.min)
        return (matches_scheme, eff_from)

    candidates.sort(key=sort_key, reverse=True)
    best = candidates[0]
    p_scheme = getattr(best, "scheme_id", None)
    if p_scheme is not None and scheme_id is not None and p_scheme != scheme_id:
        # If it was tied to a different scheme, don't use it
        fallback = [c for c in candidates if getattr(c, "scheme_id", None) is None]
        return fallback[0] if fallback else None
    return best
