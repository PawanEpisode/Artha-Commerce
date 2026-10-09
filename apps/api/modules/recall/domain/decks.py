"""
Pure rules of platform decks (PRD 4.5, FR-F15-44 to 53): what a publish changes, how a deck version is summarised and which
rights statuses may go live. No Django, no I/O. The services call these and write the results.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

SUBSCRIBE_MAX_CARDS = 500  # a deck of more cards than this is refused, never half copied (FR-F15-46)
LIBRARY_PAGE = 20
LIBRARY_PAGE_MAX = 50
PREVIEW_CHARS = 140
CHANGE_KINDS = ("typo", "clarify", "substantive", "amendment")
IMPORTANCE_ORDER = ("bullet", "important", "mandatory")
#: `unknown` cannot go live (FR-F15-53). The other statuses say where the words came from and are the editor's call.
BLOCKING_RIGHTS = frozenset({"unknown"})
SUMMARY_VERSION = 1


@dataclass(frozen=True)
class SnapshotRow:
    """One row of a deck snapshot as the publish sees it: the item, the exact item version and its facts."""

    item_id: str
    item_version_id: str
    importance: str
    faces: int
    change_kind: str = "create"  # of the item version, set by the editor


def change_vs_prev(previous: Mapping[str, str] | None, row: SnapshotRow) -> str:
    """
    How this row differs from the previous live deck version. `previous` maps item id to item version id (None for a first
    version). Same version: `unchanged`. A new version: the editor's change kind (a `create` on an item that was already in
    the deck is a rewrite, so `substantive`). Not there before: `added`.
    """
    if previous is None or row.item_id not in previous:
        return "added"
    if previous[row.item_id] == row.item_version_id:
        return "unchanged"
    return row.change_kind if row.change_kind in CHANGE_KINDS else "substantive"


def removed_item_ids(previous: Mapping[str, str] | None, rows: Iterable[SnapshotRow]) -> list[str]:
    if not previous:
        return []
    now = {r.item_id for r in rows}
    return sorted(i for i in previous if i not in now)


def tier_counts(rows: Sequence[SnapshotRow]) -> dict:
    """`{"v": 1, "mandatory": n, "important": n, "bullet": n, "cards": faces}`; the library shows these without reading the rows."""
    counts = Counter(r.importance for r in rows)
    return {
        "v": SUMMARY_VERSION,
        **{tier: counts.get(tier, 0) for tier in reversed(IMPORTANCE_ORDER)},
        "cards": sum(r.faces for r in rows),
    }


def diff_summary(previous: Mapping[str, str] | None, rows: Sequence[SnapshotRow]) -> dict:
    """Counts of each change against the previous live version, for the change log and the (R2) update preview."""
    counts = Counter(change_vs_prev(previous, r) for r in rows)
    return {
        "v": SUMMARY_VERSION,
        "added": counts.get("added", 0),
        "removed": len(removed_item_ids(previous, rows)),
        "unchanged": counts.get("unchanged", 0),
        **{kind: counts.get(kind, 0) for kind in CHANGE_KINDS},
    }


def rights_blockers(statuses: Mapping[str, str]) -> list[str]:
    """Ids of the items whose rights status blocks publishing, in a stable order."""
    return sorted(i for i, s in statuses.items() if s in BLOCKING_RIGHTS)


def cards_at_or_above(rows: Iterable[SnapshotRow], min_importance: str) -> int:
    """How many cards a subscription at `min_importance` would copy."""
    floor = IMPORTANCE_ORDER.index(min_importance)
    return sum(r.faces for r in rows if IMPORTANCE_ORDER.index(r.importance) >= floor)


def preview(text: str, limit: int = PREVIEW_CHARS) -> str:
    """A one-line preview for the library list (whitespace folded, cut at a word)."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[: limit - 1].rsplit(" ", 1)[0] or flat[: limit - 1]
    return cut + "…"
