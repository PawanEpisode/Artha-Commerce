"""
`compose(candidates, ctx) -> Selection`: the deterministic, explainable day plan (PRD 5.4).

A pure function. It reads no clock, no database and no global state; the only "randomness" is a tie-break derived from
`ctx.seed` (`hash(user_id, local_date, generation_no)` computed by the caller) so the same inputs always give the same plan
(golden fixtures in `tests/`). Steps follow the PRD numbering:

1. normalise and filter (drop, and count, what is invalid, hidden, done, suppressed or duplicated),
2. score (`scoring.py`; phase multipliers from `phases.py`),
3. choose the day's focus papers (paper need = best + half the second best + a bonus for a starved paper; starved papers take
   focus slots first, longest-waiting first, which is what makes the rotation guarantee hold),
4. fill by rounds under the budget (one task per slot per paper, at most 4 per paper, 3 revisions, 8 tasks),
5. floors (relax the caps, then the budget up to 125 percent, until there are three tasks),
6. order for display (tiles by need, General last; easiest first inside a tile) and pick the starter,
7. explain (each task stores its score breakdown; the plan stores counts of what was dropped).

A paper that has never been touched (`days_untouched is None`) counts as starved: that is what rotates a brand-new student's six
papers through the days instead of re-picking the two loudest.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from . import deeplinks, estimates, phases, scoring
from .constants import (
    COMEBACK_NEWS_WINDOW_DAYS,
    DEDUPE_KEY_MAX,
    DROP_REASONS,
    FILL_TARGET_PCT,
    GENERAL_POOL_CAP,
    GROUPS,
    HARD_CAP_PCT,
    MIN_TASKS,
    PER_PAPER_CAP,
    PROVIDER_REASON_MAX,
    PROVIDER_TITLE_MAX,
    REVISION_SLOT_CAP,
    SLOTS,
    STARTER_MAX_MINUTES,
    STARVATION_BONUS,
    STARVATION_DAYS,
)


@dataclass(frozen=True)
class Candidate:
    """One offer from a provider, resolved against its `KindSpec` (so `group` and `slot` are known). Built by `generation.py`."""

    provider: str
    kind: str
    group: str
    slot: str
    dedupe_key: str
    title: str
    reason_code: str
    reason: str
    link_path: str
    est_minutes: int
    urgency: int
    importance: int
    weakness: int
    freshness: int
    link_search: Mapping[str, Any] = field(default_factory=dict)
    paper_key: str | None = (
        None  # the subject key; None is the General pool (recall cards, amendments, the daily challenge)
    )
    chapter_key: str | None = None
    target_value: int | None = None
    must_do: bool = False
    expires_on: date | None = None
    provider_weight: int = 100  # percent, from `today_providerconfig`
    miss_count: int = 0  # times this dedupe_key expired unfinished in the last 7 days
    ref: Any = field(default=None, compare=False, repr=False)  # opaque handle for the caller; compose never looks at it


@dataclass(frozen=True)
class PaperInfo:
    key: str
    days_untouched: int | None = None  # None: never touched


@dataclass(frozen=True)
class Context:
    local_date: date
    phase: str
    budget_minutes: int
    focus_papers: int
    max_tasks: int
    papers: tuple[PaperInfo, ...]
    days_to_exam: int | None = None
    done_keys: frozenset[str] = frozenset()
    suppressed_keys: frozenset[str] = frozenset()
    hidden_kinds: frozenset[str] = frozenset()
    comeback: bool = False
    seed: int = 0


@dataclass(frozen=True)
class Pick:
    candidate: Candidate
    score: int
    breakdown: dict[str, Any]
    rank: int  # 1-based order of selection
    position: int  # 0-based display order across the whole plan


@dataclass(frozen=True)
class Tile:
    paper_key: str | None
    need: int
    picks: tuple[Pick, ...]


@dataclass(frozen=True)
class Selection:
    picks: tuple[Pick, ...]  # display order
    tiles: tuple[Tile, ...]
    starter: Pick | None
    planned_minutes: int
    candidates: int
    dropped: dict[str, int]
    focus: tuple[str, ...]
    starved: tuple[str, ...]

    def keys(self) -> list[str]:
        return [p.candidate.dedupe_key for p in self.picks]

    def selection_log(self) -> dict[str, Any]:
        """The `today_dayplan.selection_log` payload: counts only, never titles."""
        return {
            "v": 1,
            "candidates": self.candidates,
            "dropped": {reason: self.dropped.get(reason, 0) for reason in DROP_REASONS},
            "focus_papers": list(self.focus),
            "starved": list(self.starved),
        }


# ---- helpers ----------------------------------------------------------------------------------------------------------------


def tie_break(seed: int, key: str) -> int:
    """A stable pseudo-random number for breaking ties; `hashlib`, not `hash()`, so it is the same in every process."""
    return int.from_bytes(hashlib.sha1(f"{seed}|{key}".encode()).digest()[:4], "big")


def _duplicate_order(c: Candidate) -> tuple:
    """A total order for copies of the same unit of work: the heavier provider first, then every field, so input order never matters."""
    return (
        -c.provider_weight,
        c.provider,
        c.dedupe_key,
        c.kind,
        c.paper_key or "",
        c.est_minutes,
        c.title,
        c.urgency,
        c.importance,
        c.weakness,
        c.freshness,
    )


def _reject(c: Candidate, ctx: Context, paper_keys: set[str]) -> str | None:
    """The first reason this candidate must be dropped (step 1), or None."""
    structural = (
        c.group in GROUPS
        and c.slot in SLOTS
        and isinstance(c.dedupe_key, str)
        and 0 < len(c.dedupe_key) <= DEDUPE_KEY_MAX
        and isinstance(c.title, str)
        and 0 < len(c.title.strip()) <= PROVIDER_TITLE_MAX
        and bool(c.reason_code)
        and isinstance(c.reason, str)
        and len(c.reason) <= PROVIDER_REASON_MAX
        and all(scoring.valid_signal(s) for s in (c.urgency, c.importance, c.weakness, c.freshness))
        and (c.target_value is None or (isinstance(c.target_value, int) and 1 <= c.target_value <= 100))
    )
    if not structural:
        return "invalid"
    if not deeplinks.valid_link(c.link_path, c.link_search):
        return "invalid_link"
    if not estimates.valid_estimate(c.est_minutes):
        return "est_range"
    if c.paper_key is not None and c.paper_key not in paper_keys:
        return "not_enrolled"
    if c.kind in ctx.hidden_kinds:
        return "hidden_kind"
    if c.expires_on is not None and c.expires_on < ctx.local_date:
        return "expired"
    if c.dedupe_key in ctx.done_keys:
        return "done_today"
    if c.dedupe_key in ctx.suppressed_keys:
        return "suppressed"
    return None


def _effective_must_do(c: Candidate, ctx: Context) -> bool:
    """Comeback mode ignores must-do except an amendment for an attempt within 14 days (PRD 5.4)."""
    if not c.must_do:
        return False
    if not ctx.comeback:
        return True
    return c.group == "news" and ctx.days_to_exam is not None and 0 < ctx.days_to_exam <= COMEBACK_NEWS_WINDOW_DAYS


@dataclass
class _Scored:
    candidate: Candidate
    scored: scoring.Scored


class _Fill:
    """The running selection: what has been taken, the minutes, and the counters the caps are checked against."""

    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.taken: list[_Scored] = []
        self.minutes = 0
        self.per_pool: Counter[str | None] = Counter()
        self.slots: set[tuple[str | None, str]] = set()
        self.revisions = 0

    def can_take(self, item: _Scored, *, relax_caps: bool, limit_pct: int) -> bool:
        c = item.candidate
        if len(self.taken) >= self.ctx.max_tasks:
            return False
        if c.slot == "revision" and self.revisions >= REVISION_SLOT_CAP:
            return False  # backlog smoothing is never relaxed
        if not relax_caps:
            pool_cap = GENERAL_POOL_CAP if c.paper_key is None else PER_PAPER_CAP
            if self.per_pool[c.paper_key] >= pool_cap or (c.paper_key, c.slot) in self.slots:
                return False
        return (self.minutes + c.est_minutes) * 100 <= self.ctx.budget_minutes * limit_pct

    def take(self, item: _Scored) -> None:
        c = item.candidate
        self.taken.append(item)
        self.minutes += c.est_minutes
        self.per_pool[c.paper_key] += 1
        self.slots.add((c.paper_key, c.slot))
        if c.slot == "revision":
            self.revisions += 1

    def reached_target(self) -> bool:
        return self.minutes * 100 >= self.ctx.budget_minutes * FILL_TARGET_PCT


# ---- the function -----------------------------------------------------------------------------------------------------------


def compose(candidates: Sequence[Candidate], ctx: Context) -> Selection:  # noqa: C901 - one readable pass, steps match the PRD
    dropped: Counter[str] = Counter()
    paper_keys = {p.key for p in ctx.papers}
    days_untouched = {p.key: p.days_untouched for p in ctx.papers}

    # Step 1. Normalise and filter.
    valid: list[Candidate] = []
    for c in candidates:
        reason = _reject(c, ctx, paper_keys)
        if reason:
            dropped[reason] += 1
        else:
            valid.append(c)

    best_by_key: dict[str, Candidate] = {}
    for c in sorted(valid, key=_duplicate_order):
        if c.dedupe_key in best_by_key:
            dropped["duplicate"] += 1  # keep the copy with the higher provider weight
        else:
            best_by_key[c.dedupe_key] = c
    unique = list(best_by_key.values())

    # Step 2. Score.
    scored: list[_Scored] = []
    for c in unique:
        must = _effective_must_do(c, ctx)
        s = scoring.score_candidate(
            urgency=c.urgency,
            importance=c.importance,
            weakness=c.weakness,
            freshness=c.freshness,
            phase_mult=phases.multiplier(ctx.phase, c.group),
            provider_weight=c.provider_weight,
            must_do=must,
            miss_count=c.miss_count,
        )
        scored.append(_Scored(c, s))

    def order(item: _Scored) -> tuple[int, int, str]:
        return (-item.scored.score, tie_break(ctx.seed, item.candidate.dedupe_key), item.candidate.dedupe_key)

    pools: dict[str | None, list[_Scored]] = {}
    for item in sorted(scored, key=order):
        pools.setdefault(item.candidate.paper_key, []).append(item)

    # Step 3. Paper need and the day's focus papers.
    need: dict[str | None, int] = {}
    starved: list[str] = []
    for key, items in pools.items():
        top = items[0].scored.score
        second = items[1].scored.score if len(items) > 1 else 0
        value = top + second // 2
        if key is not None:
            untouched = days_untouched.get(key)
            if untouched is None or untouched >= STARVATION_DAYS:
                value += STARVATION_BONUS
                starved.append(key)
        need[key] = value

    def pool_order(key: str | None) -> tuple[int, int, str]:
        return (-need[key], tie_break(ctx.seed, key or "~general"), key or "~general")

    paper_pools = sorted((k for k in pools if k is not None), key=pool_order)
    # Rotation guarantee: starved papers (never touched, or untouched for STARVATION_DAYS) take focus slots first, the one that
    # has waited longest first (a never-touched paper counts as waiting longest), then the rest by need.
    waiting = {k: days_untouched.get(k) for k in paper_pools}
    due = sorted(
        (k for k in paper_pools if k in starved),
        key=lambda k: (-(10**6 if waiting[k] is None else waiting[k]), *pool_order(k)),
    )
    chosen = [*due, *(k for k in paper_pools if k not in due)][: ctx.focus_papers]
    focus = tuple(sorted(chosen, key=pool_order))  # reported in order of need
    in_play = sorted([*focus, *([None] if None in pools else [])], key=pool_order)

    # Step 4. Fill by rounds. Must-do tasks go first and may stretch the budget to 125 percent.
    fill = _Fill(ctx)
    taken_keys: set[str] = set()

    for item in sorted((i for i in scored if i.scored.must_do), key=order):
        if fill.can_take(item, relax_caps=False, limit_pct=HARD_CAP_PCT):
            fill.take(item)
            taken_keys.add(item.candidate.dedupe_key)

    stop = False
    while not stop:
        progressed = False
        for key in in_play:
            if fill.reached_target() or len(fill.taken) >= ctx.max_tasks:
                stop = True
                break
            for item in pools[key]:
                if item.candidate.dedupe_key in taken_keys:
                    continue
                if fill.can_take(item, relax_caps=False, limit_pct=100):
                    fill.take(item)
                    taken_keys.add(item.candidate.dedupe_key)
                    progressed = True
                    break
        if not progressed:
            break

    # Step 5. Floors: relax the per-slot and per-paper caps, then the budget up to 125 percent, until there are three tasks.
    if len(fill.taken) < MIN_TASKS:
        for limit_pct in (100, HARD_CAP_PCT):
            for item in sorted(scored, key=order):
                if len(fill.taken) >= min(MIN_TASKS, ctx.max_tasks):
                    break
                if item.candidate.dedupe_key in taken_keys:
                    continue
                if fill.can_take(item, relax_caps=True, limit_pct=limit_pct):
                    fill.take(item)
                    taken_keys.add(item.candidate.dedupe_key)

    # Whatever was valid but not chosen, and why (the `budget` and `cap` counts of the selection log).
    for item in scored:
        if item.candidate.dedupe_key in taken_keys:
            continue
        key = item.candidate.paper_key
        if key is not None and key not in focus:
            dropped["not_focus"] += 1
        elif fill.can_take(item, relax_caps=False, limit_pct=100):
            dropped["budget"] += 1  # it would fit, the fill target was reached first
        elif (fill.minutes + item.candidate.est_minutes) * 100 > ctx.budget_minutes * 100:
            dropped["budget"] += 1
        else:
            dropped["cap"] += 1

    # Step 6 and 7. Order for display, pick the starter, explain.
    rank_of = {id(item): n for n, item in enumerate(fill.taken, start=1)}
    by_pool: dict[str | None, list[_Scored]] = {}
    for item in fill.taken:
        by_pool.setdefault(item.candidate.paper_key, []).append(item)

    tile_keys = sorted((k for k in by_pool if k is not None), key=pool_order)
    if None in by_pool:
        tile_keys.append(None)  # General last

    picks: list[Pick] = []
    tiles: list[Tile] = []
    for key in tile_keys:
        ordered = sorted(
            by_pool[key],
            key=lambda i: (
                i.candidate.est_minutes,
                -i.scored.score,
                i.candidate.dedupe_key,
            ),  # easy first builds momentum
        )
        tile_picks = []
        for item in ordered:
            pick = Pick(
                candidate=item.candidate,
                score=item.scored.score,
                breakdown=_breakdown(item, rank_of[id(item)], ctx, starved),
                rank=rank_of[id(item)],
                position=len(picks),
            )
            picks.append(pick)
            tile_picks.append(pick)
        tiles.append(Tile(paper_key=key, need=need[key], picks=tuple(tile_picks)))

    return Selection(
        picks=tuple(picks),
        tiles=tuple(tiles),
        starter=_starter(picks, ctx),
        planned_minutes=fill.minutes,
        candidates=len(candidates),
        dropped=dict(dropped),
        focus=focus,
        starved=tuple(sorted(starved)),
    )


def _starter(picks: Sequence[Pick], ctx: Context) -> Pick | None:
    """The "Start here" task: the highest score among those of 10 minutes or less, else the highest score overall."""
    if not picks:
        return None
    short = [p for p in picks if p.candidate.est_minutes <= STARTER_MAX_MINUTES]
    pool = short or list(picks)
    return min(pool, key=lambda p: (-p.score, tie_break(ctx.seed, p.candidate.dedupe_key), p.candidate.dedupe_key))


def _breakdown(item: _Scored, rank: int, ctx: Context, starved: Sequence[str]) -> dict[str, Any]:
    c, s = item.candidate, item.scored
    modifiers: list[str] = []
    if s.must_do:
        modifiers.append("must_do")
    if s.phase_mult != 100 and ctx.days_to_exam is not None:
        modifiers.append(f"exam_in_{ctx.days_to_exam}_days")
    if c.paper_key is not None and c.paper_key in starved:
        modifiers.append("starved_paper")
    if ctx.comeback:
        modifiers.append("comeback")
    return {
        "v": 1,
        "signals": {"u": c.urgency, "i": c.importance, "w": c.weakness, "f": c.freshness},
        "base": s.base,
        "group": c.group,
        "phase_mult": s.phase_mult,
        "provider_weight": s.provider_weight,
        "must_do": s.must_do,
        "miss_penalty": s.miss_penalty,
        "rank": rank,
        "modifiers": modifiers,
    }
