"""
Pure rules of living decks (R2-W2, FR-F15-47 and FR-F15-48): what a student's subscription must do to move from one deck
version to another. No Django, no I/O; the sync service and the update preview call these.

Per item the plan is one of `added`, `removed`, `typo`, `clarify`, `substantive`, `amendment` (an unchanged item is not in the
plan). When she skipped versions, the WORST change kind between her version and the target applies, in the order
amendment > substantive > clarify > typo. A `create` version of an item that was already in the deck is a rewrite, so it
counts as `substantive` (the same rule `domain.decks.change_vs_prev` applies at publish).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping

CHANGE_RANK = {"typo": 1, "clarify": 2, "substantive": 3, "amendment": 4}
SILENT_CHANGES = ("typo", "clarify")  # swap the version quietly: no badge, no memory change
RECHECK_CHANGES = ("substantive", "amendment")  # badge, stability capped at 3 days, due now
PLAN_KINDS = ("added", "removed", "typo", "clarify", "substantive", "amendment")
#: `RecallCard.recheck_reason` for each change that returns a card for re-check
RECHECK_REASON = {"substantive": "content_changed", "amendment": "amendment"}
#: `RecallScheduleEvent.reason_code` of the `content_reset` it writes
RESET_REASON = {"substantive": "substantive", "amendment": "amendment"}
PREVIEW_PER_KIND = 5  # items named per change kind in the update preview
SYNC_CHUNK = 200  # subscriptions per `recall.sync_subscribers` job (ERD 6.4)
SUMMARY_VERSION = 1


def kind_of_version(change_kind: str) -> str:
    """The change kind an item version stands for: `create` on an item already in the deck is a rewrite."""
    return change_kind if change_kind in CHANGE_RANK else "substantive"


def worst_change(kinds: Iterable[str]) -> str | None:
    """The most serious kind among these (`create` counts as `substantive`), or None when there are none."""
    ranked = [kind_of_version(k) for k in kinds]
    return max(ranked, key=CHANGE_RANK.__getitem__) if ranked else None


def plan_diff(
    old: Mapping[str, str], new: Mapping[str, str], kinds_between: Mapping[str, Iterable[str]]
) -> dict[str, str]:
    """
    `old` and `new` map item id to item version id (her synced snapshot and the target snapshot). `kinds_between` maps an item
    id to the change kinds of the item versions after her version up to the target's (any order, any length). The result maps
    each item id that needs work to its change; items whose version is the same are left out. A changed item with no kind on
    record is treated as `substantive`, the safe side.
    """
    plan: dict[str, str] = {}
    for item_id, version in new.items():
        if item_id not in old:
            plan[item_id] = "added"
        elif old[item_id] != version:
            plan[item_id] = worst_change(kinds_between.get(item_id, ())) or "substantive"
    for item_id in old:
        if item_id not in new:
            plan[item_id] = "removed"
    return plan


def summarise(plan: Mapping[str, str]) -> dict:
    """`{"v": 1, "added": n, ..., "total": n, "recheck": n}` for the banner ("Update available (3 changes)")."""
    counts = Counter(plan.values())
    return {
        "v": SUMMARY_VERSION,
        **{kind: counts.get(kind, 0) for kind in PLAN_KINDS},
        "total": len(plan),
        "recheck": sum(counts.get(kind, 0) for kind in RECHECK_CHANGES),
    }


def kinds_present(summary: Mapping) -> list[str]:
    return [kind for kind in PLAN_KINDS if summary.get(kind, 0) > 0]
