"""
The rotation guarantee (FR-F13-04): with N active papers and F focus papers no paper is absent from the plan for more than
`ceil(N / F) + 1` consecutive days, simulated over 60 days with noisy signals, for every budget the formula can produce.
"""

import math
import random
from datetime import date, timedelta

import pytest

from modules.today.domain import budget
from modules.today.domain import compose as cp

PAPERS = ["taxation", "audit", "costing", "law", "fm", "sm"]
SLOTS = [("revision", "revise"), ("mcq", "practice"), ("section", "learn")]


def day_candidates(rng: random.Random, day: date) -> list[cp.Candidate]:
    rows = []
    for paper in PAPERS:
        for slot, group in SLOTS:
            rows.append(
                cp.Candidate(
                    provider="sim.p",
                    kind=f"{slot}_k",
                    group=group,
                    slot=slot,
                    dedupe_key=f"{paper}:{slot}:{day.isoformat()}",
                    title=f"{paper} {slot}",
                    reason_code="custom",
                    reason="",
                    link_path="/app/revision",
                    est_minutes=rng.choice([5, 8, 10, 12, 15, 20]),
                    urgency=rng.randint(0, 100),
                    importance=rng.randint(20, 100),
                    weakness=rng.randint(0, 100),
                    freshness=rng.randint(0, 100),
                    paper_key=paper,
                )
            )
    return rows


def simulate(budget_minutes: int, seed: int, days: int = 60) -> tuple[int, dict[str, int]]:
    """The longest run of consecutive plans a paper was missing from, and the days each paper appeared."""
    rng = random.Random(seed)
    untouched: dict[str, int | None] = {p: None for p in PAPERS}
    absent = {p: 0 for p in PAPERS}
    longest = 0
    appeared = {p: 0 for p in PAPERS}
    start = date(2026, 10, 14)
    for n in range(days):
        day = start + timedelta(days=n)
        ctx = cp.Context(
            local_date=day,
            phase="steady",
            budget_minutes=budget_minutes,
            focus_papers=budget.focus_papers(budget_minutes),
            max_tasks=8,
            papers=tuple(cp.PaperInfo(p, untouched[p]) for p in PAPERS),
            seed=seed * 1000 + n,
        )
        selection = cp.compose(day_candidates(rng, day), ctx)
        shown = {pick.candidate.paper_key for pick in selection.picks}
        for paper in PAPERS:
            if paper in shown:  # the student does what she is given
                untouched[paper] = 0
                absent[paper] = 0
                appeared[paper] += 1
            else:
                untouched[paper] = 1 if untouched[paper] is None and n == 0 else (untouched[paper] or 0) + 1
                absent[paper] += 1
                longest = max(longest, absent[paper])
    return longest, appeared


@pytest.mark.parametrize("budget_minutes", [30, 60, 90, 120])
@pytest.mark.parametrize("seed", range(8))
def test_no_paper_is_missing_for_more_than_ceil_n_over_f_plus_one_days(budget_minutes, seed):
    focus = budget.focus_papers(budget_minutes)
    longest, appeared = simulate(budget_minutes, seed)
    limit = math.ceil(len(PAPERS) / focus) + 1
    assert longest <= limit, f"a paper was missing {longest} days in a row (limit {limit}, F={focus})"
    assert all(count > 0 for count in appeared.values())


def test_the_plan_for_a_day_is_the_same_when_simulated_twice():
    assert simulate(60, 3) == simulate(60, 3)
