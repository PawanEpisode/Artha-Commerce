"""
Quota allocation, difficulty mix and smart mix algorithms (F-05 ERD 3.5).
Pure, deterministic, zero-dependency.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


def allocate_quotas(
    total_count: int,
    chapter_keys: Sequence[str],
    weights: Sequence[float],
    availabilities: Sequence[int],
) -> dict[str, int]:
    """
    Allocates total_count across chapters by weight using Largest Remainder (Hare-Niemeyer),
    capping at availability and redistributing shortfalls.
    Asserts: sum(quotas) == min(total_count, sum(availabilities)), 0 <= q_i <= a_i.
    """
    n = len(chapter_keys)
    if n == 0 or total_count <= 0:
        return {}

    avail = [max(0, a) for a in availabilities]
    total_avail = sum(avail)
    target = min(total_count, total_avail)
    if target == 0:
        return {k: 0 for k in chapter_keys}

    w = [max(0.001, float(x)) for x in weights]
    quotas = [0] * n

    # Iterative allocation: allocate target items
    remaining_target = target
    active_indices = set(range(n))

    while remaining_target > 0 and active_indices:
        sum_w = sum(w[i] for i in active_indices)
        if sum_w <= 0:
            # Fall back to round-robin among active
            for idx in sorted(active_indices):
                if remaining_target <= 0:
                    break
                space = avail[idx] - quotas[idx]
                if space > 0:
                    quotas[idx] += 1
                    remaining_target -= 1
            break

        # Largest remainder
        exact = [(w[i] * remaining_target) / sum_w for i in range(n)]
        floors = [math.floor(exact[i]) if i in active_indices else 0 for i in range(n)]
        remainders = [(exact[i] - floors[i], -i, i) if i in active_indices else (-1, 0, i) for i in range(n)]

        tentative = list(floors)
        distributed = sum(tentative)
        deficit = remaining_target - distributed

        remainders.sort(key=lambda t: (t[0], t[1]), reverse=True)
        for _r, _, idx in remainders:
            if deficit <= 0:
                break
            if idx in active_indices:
                tentative[idx] += 1
                deficit -= 1

        # Check against capacity
        new_active = set()
        progress = False
        for idx in active_indices:
            cap = avail[idx] - quotas[idx]
            give = min(tentative[idx], cap)
            if give > 0:
                quotas[idx] += give
                remaining_target -= give
                progress = True
            if quotas[idx] < avail[idx]:
                new_active.add(idx)

        if not progress:
            # Emergency distribution if floating math caused zero allocation
            for idx in sorted(active_indices):
                if remaining_target <= 0:
                    break
                if quotas[idx] < avail[idx]:
                    quotas[idx] += 1
                    remaining_target -= 1
                    if quotas[idx] < avail[idx]:
                        new_active.add(idx)
        active_indices = new_active

    return {k: quotas[i] for i, k in enumerate(chapter_keys)}


def allocate_difficulty_mix(
    quota: int,
    difficulty_mix: Sequence[int] = (3, 5, 2),  # (easy, medium, hard) out of 10
    available_by_diff: dict[str, int] | None = None,
) -> dict[str, int]:
    """
    Distributes chapter quota into easy, medium, hard bands using largest remainder.
    Falls back to Medium -> Easy -> Hard if a band lacks available questions.
    """
    if quota <= 0:
        return {"easy": 0, "medium": 0, "hard": 0}

    mix = list(difficulty_mix)
    if len(mix) != 3 or sum(mix) == 0:
        mix = [3, 5, 2]
    total_mix = sum(mix)

    # Largest remainder allocation
    exact = [(m * quota) / total_mix for m in mix]
    floors = [math.floor(x) for x in exact]
    rems = sorted([(exact[i] - floors[i], -i, i) for i in range(3)], reverse=True)

    target = floors
    deficit = quota - sum(target)
    for _, _, idx in rems:
        if deficit <= 0:
            break
        target[idx] += 1
        deficit -= 1

    bands = {"easy": target[0], "medium": target[1], "hard": target[2]}
    if not available_by_diff:
        return bands

    # If availability provided, cap and redistribute (Medium -> Easy -> Hard)
    avail_easy = available_by_diff.get("easy", 0)
    avail_med = available_by_diff.get("medium", 0) + available_by_diff.get("unrated", 0)
    avail_hard = available_by_diff.get("hard", 0)

    shortfall = 0
    if bands["easy"] > avail_easy:
        shortfall += bands["easy"] - avail_easy
        bands["easy"] = avail_easy
    if bands["hard"] > avail_hard:
        shortfall += bands["hard"] - avail_hard
        bands["hard"] = avail_hard
    if bands["medium"] > avail_med:
        shortfall += bands["medium"] - avail_med
        bands["medium"] = avail_med

    # Fill shortfall from Medium, then Easy, then Hard
    order = ["medium", "easy", "hard"]
    caps = {"easy": avail_easy, "medium": avail_med, "hard": avail_hard}
    for band in order:
        if shortfall <= 0:
            break
        space = caps[band] - bands[band]
        if space > 0:
            give = min(space, shortfall)
            bands[band] += give
            shortfall -= give

    return bands


def apply_smart_mix(
    unseen_ids: Sequence[Any],
    wrong_last_ids: Sequence[Any],
    due_ids: Sequence[Any],
    other_ids: Sequence[Any],
    count: int,
) -> list[Any]:
    """
    Fills count questions per chapter in priority order:
    unseen -> wrong_last -> due -> others, deduplicating in-order.
    """
    picked: list[Any] = []
    seen_set: set[Any] = set()

    pools = [unseen_ids, wrong_last_ids, due_ids, other_ids]
    for pool in pools:
        for item in pool:
            if len(picked) >= count:
                return picked
            if item not in seen_set:
                seen_set.add(item)
                picked.append(item)

    return picked
