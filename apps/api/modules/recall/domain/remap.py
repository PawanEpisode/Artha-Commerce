"""
Pure rules of a scheme switch for her OWN cards (R2-W2, FR-F15-50): which chapter of the new scheme a card follows, mirroring
the F-02 chapter map. The coverage module carries progress with every map row; for cards the rule is stricter on purpose:

* a row an editor has not confirmed (`needs_review`) is ignored for the automatic decision and only offered as a suggestion,
  because a wrong automatic move of a student's own cards is harder to see and undo than a wrong carry of progress;
* `same` and `partial` (a renamed or moved chapter, or a chapter that kept part of its topics) follow the single target;
* `merged` follows its one target (several old chapters map to it, each old chapter has one row);
* `split` offers every target to choose from;
* two confirmed rows that are not a split (an editor's data error) are treated as a choice too, never as a guess;
* nothing confirmed: the card is parked as "Needs a new chapter" and she picks any chapter.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

MAP, CHOOSE, PARK = "map", "choose", "park"


@dataclass(frozen=True)
class MapRow:
    to_chapter_id: str
    relation: str  # same, split, merged, partial
    needs_review: bool = False


@dataclass(frozen=True)
class Decision:
    action: str  # map: move now; choose: wait for her pick among `candidates`; park: wait, any chapter
    relation: str  # same, split, merged, partial, none
    to_chapter_id: str | None = None
    candidates: tuple[str, ...] = ()


def decide(rows: Sequence[MapRow]) -> Decision:
    """The automatic outcome for a card whose chapter has these map rows into the new scheme (in any order)."""
    confirmed = sorted({r.to_chapter_id: r for r in rows if not r.needs_review}.values(), key=lambda r: r.to_chapter_id)
    suggestions = tuple(sorted({r.to_chapter_id for r in rows if r.needs_review}))
    if not confirmed:
        return Decision(PARK, "none", None, suggestions)
    if len(confirmed) == 1 and confirmed[0].relation != "split":
        only = confirmed[0]
        return Decision(MAP, only.relation, only.to_chapter_id)
    relation = "split" if any(r.relation == "split" for r in confirmed) else confirmed[0].relation
    return Decision(
        CHOOSE,
        relation,
        None,
        tuple(r.to_chapter_id for r in confirmed)
        + tuple(i for i in suggestions if i not in {r.to_chapter_id for r in confirmed}),
    )
