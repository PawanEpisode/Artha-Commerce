"""
The delivery targets (PRD 13.2, FR-N23): at least 98% of push attempts accepted by the push service and the 95th
percentile of lateness at most 5 seconds. Pure: rows in, a verdict out.

A window with fewer than `MIN_SAMPLE` attempts is never a breach: one failure out of two is noise, not an outage.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

ACCEPTED_TARGET = 0.98
P95_TARGET_MS = 5000
WINDOW_MINUTES = 15
MIN_SAMPLE = 5


@dataclass(frozen=True)
class SloVerdict:
    attempts: int
    accepted: int
    accepted_ratio: float | None
    p95_ms: int | None
    ratio_breached: bool
    lateness_breached: bool

    @property
    def breached(self) -> bool:
        return self.ratio_breached or self.lateness_breached


def p95(values: Sequence[int]) -> int | None:
    """Nearest-rank 95th percentile; None for no data."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def evaluate(*, accepted: int, failed: int, lateness_ms: Sequence[int]) -> SloVerdict:
    attempts = accepted + failed
    enough = attempts >= MIN_SAMPLE
    ratio = accepted / attempts if attempts else None
    late = p95(lateness_ms)
    return SloVerdict(
        attempts=attempts,
        accepted=accepted,
        accepted_ratio=None if ratio is None else round(ratio, 4),
        p95_ms=late,
        ratio_breached=enough and ratio is not None and ratio < ACCEPTED_TARGET,
        lateness_breached=enough and late is not None and late > P95_TARGET_MS,
    )
