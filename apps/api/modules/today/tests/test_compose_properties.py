"""Invariants of `compose` over random inputs (hypothesis): the caps hold whatever the providers send."""

from datetime import date

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from modules.today.domain import compose as cp
from modules.today.domain.constants import GROUPS, MAX_TASKS, MIN_TASKS, REVISION_SLOT_CAP, SLOTS

PAPERS = ["p1", "p2", "p3", "p4", "p5"]


@st.composite
def candidates(draw):
    n = draw(st.integers(0, 40))
    rows = []
    for index in range(n):
        slot = draw(st.sampled_from(SLOTS))
        rows.append(
            cp.Candidate(
                provider=f"t.p{draw(st.integers(0, 2))}",
                kind=f"{slot}_k",
                group=draw(st.sampled_from(GROUPS)),
                slot=slot,
                dedupe_key=f"k{index}" if draw(st.integers(0, 9)) else "k0",  # an occasional duplicate key
                title=f"t{index}",
                reason_code="custom",
                reason="",
                link_path="/app/revision",
                est_minutes=draw(st.integers(1, 90)),
                urgency=draw(st.integers(0, 100)),
                importance=draw(st.integers(0, 100)),
                weakness=draw(st.integers(0, 100)),
                freshness=draw(st.integers(0, 100)),
                paper_key=draw(st.sampled_from([*PAPERS, None])),
                must_do=draw(st.integers(0, 12)) == 0,
                provider_weight=draw(st.sampled_from([50, 100, 150])),
                miss_count=draw(st.integers(0, 5)),
            )
        )
    return rows


@st.composite
def contexts(draw):
    return cp.Context(
        local_date=date(2026, 10, 14),
        phase=draw(st.sampled_from(["steady", "build", "consolidate", "sprint", "final"])),
        days_to_exam=draw(st.one_of(st.none(), st.integers(1, 200))),
        budget_minutes=draw(st.integers(10, 240)),
        focus_papers=draw(st.integers(1, 4)),
        max_tasks=draw(st.sampled_from([5, MAX_TASKS])),
        papers=tuple(cp.PaperInfo(p, draw(st.one_of(st.none(), st.integers(0, 12)))) for p in PAPERS),
        comeback=draw(st.booleans()),
        seed=draw(st.integers(0, 10**6)),
    )


SETTINGS = settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@SETTINGS
@given(rows=candidates(), ctx=contexts())
def test_invariants_hold_for_any_input(rows, ctx):
    sel = cp.compose(rows, ctx)
    keys = sel.keys()

    assert len(keys) == len(set(keys)), "a unit of work is never offered twice"
    assert len(sel.picks) <= ctx.max_tasks
    assert sum(1 for p in sel.picks if p.candidate.slot == "revision") <= REVISION_SLOT_CAP
    assert sel.planned_minutes == sum(p.candidate.est_minutes for p in sel.picks)
    assert sel.planned_minutes * 100 <= ctx.budget_minutes * 125 or len(sel.picks) == 0
    assert all(p.candidate.paper_key is None or p.candidate.paper_key in PAPERS for p in sel.picks)
    assert [p.position for p in sel.picks] == list(range(len(sel.picks)))
    assert sorted(p.rank for p in sel.picks) == list(range(1, len(sel.picks) + 1))
    assert sel.starter is None or sel.starter in sel.picks
    assert (sel.starter is None) == (len(sel.picks) == 0)
    assert sum(len(t.picks) for t in sel.tiles) == len(sel.picks)
    assert not [t for t in sel.tiles[:-1] if t.paper_key is None], "General is always the last tile"

    # No slot twice in a paper unless the floor had to relax the caps to reach three tasks.
    if len(sel.picks) > MIN_TASKS:
        pairs = [(p.candidate.paper_key, p.candidate.slot) for p in sel.picks]
        assert len(pairs) == len(set(pairs))


@SETTINGS
@given(rows=candidates(), ctx=contexts())
def test_composition_is_deterministic_and_ignores_input_order(rows, ctx):
    first = cp.compose(rows, ctx)
    second = cp.compose(list(reversed(rows)), ctx)
    assert first.keys() == second.keys()
    assert first.planned_minutes == second.planned_minutes
    assert first.focus == second.focus


@SETTINGS
@given(rows=candidates(), ctx=contexts())
def test_what_the_student_has_done_or_snoozed_is_never_offered(rows, ctx):
    blocked = frozenset(r.dedupe_key for r in rows[::3])
    sel = cp.compose(rows, cp.Context(**{**ctx.__dict__, "done_keys": blocked}))
    assert not blocked & set(sel.keys())
    sel = cp.compose(rows, cp.Context(**{**ctx.__dict__, "suppressed_keys": blocked}))
    assert not blocked & set(sel.keys())
