"""
Plan health (FR-F13-48): on track, slightly behind (a shortfall up to 10 percent of the capacity) or at risk, with the numbers.

`unknown` is not a computed band: it is the state of a plan that has no exam date left to plan towards (the exam day came or
passed), so `assess` returns it only when `plan_over` is true.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import constants as pc


@dataclass(frozen=True)
class Health:
    health: str
    capacity_minutes: int
    remaining_minutes: int
    shortfall_minutes: int

    @property
    def shortfall_hours(self) -> float:
        """For the "20 h short" line (the UI rounds)."""
        return self.shortfall_minutes / 60


def classify(shortfall_minutes: int, capacity_minutes: int) -> str:
    """The band for a shortfall. The 10 percent boundary belongs to `slightly_behind`; zero capacity with work left is `at_risk`."""
    if shortfall_minutes <= 0:
        return "on_track"
    if shortfall_minutes * 100 <= pc.SLIGHTLY_BEHIND_PCT * capacity_minutes:
        return "slightly_behind"
    return "at_risk"


def assess(*, remaining_minutes: int, capacity_minutes: int, plan_over: bool = False) -> Health:
    shortfall = max(0, remaining_minutes - capacity_minutes)
    band = "unknown" if plan_over else classify(shortfall, capacity_minutes)
    return Health(band, capacity_minutes, remaining_minutes, shortfall)
