"""
Choice resolution algorithm for F-08 Mock Tests (ERD Section 3.5.5).
Resolves "answer any N of M" choice groups deterministically.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, NamedTuple


class ChoiceResolutionResult(NamedTuple):
    resolution: dict[str, Any]
    excluded_positions: set[int]


def resolve_choices(
    groups: list[dict[str, Any]],
    answered_map: dict[int, dict[str, Any]],
) -> ChoiceResolutionResult:
    """
    Resolves each choice group:
    groups: list of dicts:
      {
        "key": "B-choice-1",
        "required_count": 4,
        "overflow_policy": "block" | "first_n" | "best_n",
        "positions": [21, 22, 23, 24, 25, 26] # in ascending order
      }
    answered_map: dict mapping position -> {
      "answered": bool,
      "marks_awarded": Decimal | float | None,
      "answered_at": datetime | None
    }
    """
    resolution_groups: dict[str, Any] = {}
    all_excluded: set[int] = set()

    for g in groups:
        g_key = g["key"]
        n = g["required_count"]
        policy = g.get("overflow_policy", "block")
        positions = sorted(g.get("positions", []))

        answered_pos = [p for p in positions if answered_map.get(p, {}).get("answered")]
        unanswered_pos = [p for p in positions if p not in answered_pos]

        k = len(answered_pos)

        if k <= n:
            # All answered are counted
            counted = list(answered_pos)
            # Empty slots = N - k lowest position unanswered items
            needed_slots = n - k
            empty_slots = unanswered_pos[:needed_slots]
            not_counted = unanswered_pos[needed_slots:]
        else:
            # k > N: overflow
            empty_slots = []
            if policy == "best_n":
                # Sort answered by marks_awarded desc, then position asc
                sorted_answered = sorted(
                    answered_pos,
                    key=lambda p: (
                        -Decimal(str(answered_map.get(p, {}).get("marks_awarded") or 0)),
                        p,
                    ),
                )
                counted = sorted(sorted_answered[:n])
                overflow = sorted(sorted_answered[n:])
            else:
                # first_n (and block fallback): first N by position
                counted = answered_pos[:n]
                overflow = answered_pos[n:]

            not_counted = overflow + unanswered_pos

        resolution_groups[g_key] = {
            "counted": counted,
            "not_counted": not_counted,
            "empty_slots": empty_slots,
        }
        all_excluded.update(not_counted)

    return ChoiceResolutionResult(
        resolution={"v": 1, "groups": resolution_groups},
        excluded_positions=all_excluded,
    )
