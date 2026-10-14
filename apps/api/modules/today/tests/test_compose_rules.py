"""The composition rules one at a time: filters, caps, must-do, floors, comeback, phases (PRD 5.4, 5.7)."""

from datetime import date, timedelta

from modules.today.domain import compose as cp

TODAY = date(2026, 10, 14)


def ctx(papers=("taxation", "audit", "costing"), **over):
    fields = dict(
        local_date=TODAY,
        phase="steady",
        budget_minutes=60,
        focus_papers=2,
        max_tasks=8,
        papers=tuple(cp.PaperInfo(k, 1) for k in papers),
    )
    fields.update(over)
    return cp.Context(**fields)


def cand(key, paper="taxation", slot="mcq", group="practice", minutes=10, sig=(50, 50, 50, 50), **over):
    u, i, w, f = sig
    fields = dict(
        provider="test.p",
        kind=f"{slot}_k",
        group=group,
        slot=slot,
        dedupe_key=key,
        title=f"Task {key}",
        reason_code="custom",
        reason="because",
        link_path="/app/revision",
        est_minutes=minutes,
        urgency=u,
        importance=i,
        weakness=w,
        freshness=f,
        paper_key=paper,
    )
    fields.update(over)
    return cp.Candidate(**fields)


def drops(selection):
    return {k: v for k, v in selection.dropped.items() if v}


# ---- step 1: filters --------------------------------------------------------------------------------------------------------


def test_invalid_candidates_are_dropped_and_counted_not_fatal():
    rows = [
        cand("ok"),
        cand("bad_link", link_path="https://evil.example"),
        cand("bad_scheme", link_path="//evil.example/app"),
        cand("not_listed", link_path="/app/admin"),
        cand("reserved", link_search={"task": "x"}),
        cand("too_long", minutes=91),
        cand("zero", minutes=0, slot="read"),
        cand("signal", sig=(101, 0, 0, 0), slot="read"),
        cand("no_title", title="  ", slot="read"),
        cand("bad_slot", slot="nope"),
        cand("not_mine", paper="law", slot="section"),
    ]
    sel = cp.compose(rows, ctx())
    assert sel.keys() == ["ok"]
    assert drops(sel) == {
        "invalid_link": 4,
        "est_range": 2,
        "invalid": 3,
        "not_enrolled": 1,
    }


def test_done_suppressed_expired_and_hidden_are_not_offered():
    rows = [
        cand("done", slot="mcq"),
        cand("snoozed", slot="read"),
        cand("old", slot="section", expires_on=TODAY - timedelta(days=1)),
        cand("today_only", slot="practical", expires_on=TODAY),
        cand("hidden", slot="formula", kind="formula_k"),
        cand("fine", slot="revision", group="revise"),
    ]
    sel = cp.compose(
        rows,
        ctx(
            done_keys=frozenset({"done"}), suppressed_keys=frozenset({"snoozed"}), hidden_kinds=frozenset({"formula_k"})
        ),
    )
    assert sorted(sel.keys()) == ["fine", "today_only"]
    assert drops(sel) == {"done_today": 1, "suppressed": 1, "expired": 1, "hidden_kind": 1}


def test_duplicate_keys_keep_the_higher_provider_weight():
    rows = [
        cand("same", provider="a.low", provider_weight=100),
        cand("same", provider="b.high", provider_weight=150, title="From the heavier provider"),
    ]
    sel = cp.compose(rows, ctx())
    assert [p.candidate.provider for p in sel.picks] == ["b.high"]
    assert sel.dropped["duplicate"] == 1


def test_provider_weight_scales_the_score():
    heavy = cp.compose([cand("x", provider_weight=200)], ctx()).picks[0].score
    light = cp.compose([cand("x", provider_weight=50)], ctx()).picks[0].score
    assert heavy == 4 * light


# ---- step 4: caps -----------------------------------------------------------------------------------------------------------


def test_one_task_per_slot_per_paper_never_two_mcq_sets():
    rows = [
        cand("m1", slot="mcq", minutes=5, sig=(90, 90, 90, 90)),
        cand("m2", slot="mcq", minutes=5),
        cand("s1", slot="section", minutes=5),
        cand("f1", slot="formula", minutes=5),
    ]
    sel = cp.compose(rows, ctx(papers=("taxation",), focus_papers=1))
    assert sorted(sel.keys()) == ["f1", "m1", "s1"]  # three tasks already, so the floor never relaxes the slot cap


def test_at_most_four_tasks_per_paper():
    slots = ["mcq", "formula", "section", "practical", "read"]
    rows = [cand(f"t{n}", slot=s, minutes=5, sig=(80 - n, 50, 50, 50)) for n, s in enumerate(slots)]
    sel = cp.compose(rows, ctx(papers=("taxation",), focus_papers=1, budget_minutes=120))
    assert len(sel.picks) == 4


def test_general_pool_holds_at_most_two():
    rows = [
        cand(f"g{n}", paper=None, slot=s, minutes=5) for n, s in enumerate(["recall", "amendment", "challenge", "read"])
    ]
    rows.append(cand("p1", paper="taxation", slot="mcq", minutes=5))  # a third task, so the floor leaves the cap alone
    sel = cp.compose(rows, ctx(budget_minutes=120))
    assert sum(1 for p in sel.picks if p.candidate.paper_key is None) == 2


def test_backlog_smoothing_three_revisions_a_day():
    rows = [
        cand(f"r{n}", paper=p, slot="revision", group="revise", minutes=5, sig=(90, 90, 90, 90))
        for n, p in enumerate(["taxation", "audit", "costing"])
    ]
    rows += [cand("r_extra", paper=None, slot="revision", group="revise", minutes=5)]
    sel = cp.compose(rows, ctx(focus_papers=3, budget_minutes=120))
    assert sum(1 for p in sel.picks if p.candidate.slot == "revision") == 3


def test_task_cap_of_eight():
    rows = [
        cand(f"{paper}-{slot}", paper=paper, slot=slot, minutes=1)
        for paper in ("p1", "p2", "p3")
        for slot in ("mcq", "formula", "section", "practical")
    ]
    sel = cp.compose(rows, ctx(papers=("p1", "p2", "p3"), focus_papers=3, budget_minutes=300))
    assert len(sel.picks) == 8


def test_never_over_the_budget_without_must_do():
    rows = [
        cand(f"s{n}", paper="taxation", slot=s, minutes=10, sig=(80, 50, 50, 50))
        for n, s in enumerate(["mcq", "read", "section"])
    ]
    rows += [cand(f"l{n}", paper="taxation", slot=s, minutes=25) for n, s in enumerate(["formula", "practical"])]
    sel = cp.compose(rows, ctx(papers=("taxation",), focus_papers=1, budget_minutes=60))
    assert sel.planned_minutes <= 60  # three small tasks are in, so the floor never stretches the budget
    assert len(sel.picks) >= 3


# ---- must-do and floors -----------------------------------------------------------------------------------------------------


def test_must_do_goes_first_and_may_stretch_the_budget_to_125_percent():
    rows = [
        cand("must", paper="taxation", slot="read", group="learn", minutes=70, must_do=True),
        cand("small", paper="taxation", slot="mcq", minutes=10),
    ]
    sel = cp.compose(rows, ctx(papers=("taxation",), focus_papers=1, budget_minutes=60))
    assert sel.keys() == ["must"]  # 70 minutes is under 75 (125 percent of 60); nothing else fits
    assert sel.picks[0].breakdown["must_do"] is True


def test_must_do_never_goes_beyond_125_percent():
    rows = [cand("huge", slot="read", group="learn", minutes=80, must_do=True)]
    sel = cp.compose(rows, ctx(budget_minutes=60))
    assert sel.keys() == ["huge"] or sel.planned_minutes <= 75
    if sel.keys():
        assert sel.planned_minutes <= 75


def test_floor_relaxes_the_caps_to_reach_three_tasks():
    rows = [cand(f"m{n}", slot="mcq", minutes=5, sig=(90 - n, 50, 50, 50)) for n in range(4)]
    sel = cp.compose(rows, ctx(papers=("taxation",), focus_papers=1))
    assert len(sel.picks) == 3  # the one-per-slot cap is relaxed, but only up to the floor


def test_floor_stretches_the_budget_up_to_125_percent():
    rows = [cand(f"t{n}", slot=s, minutes=24) for n, s in enumerate(["mcq", "read", "section"])]
    sel = cp.compose(rows, ctx(papers=("taxation",), focus_papers=1, budget_minutes=60))
    assert len(sel.picks) == 3 and sel.planned_minutes == 72 <= 75


def test_an_empty_plan_is_legitimate():
    sel = cp.compose([], ctx())
    assert sel.picks == () and sel.starter is None and sel.planned_minutes == 0


# ---- phases, comeback, anti-nag ---------------------------------------------------------------------------------------------


def test_final_phase_weighs_revision_over_learning():
    rows = [
        cand("learn", slot="read", group="learn", minutes=30, sig=(60, 60, 60, 60)),
        cand("revise", slot="revision", group="revise", minutes=30, sig=(60, 60, 60, 60)),
    ]
    sel = cp.compose(rows, ctx(papers=("taxation",), focus_papers=1, phase="final", days_to_exam=5, budget_minutes=40))
    assert sel.keys() == ["revise"]
    scores = {
        p.candidate.dedupe_key: p.score
        for p in cp.compose(rows, ctx(phase="final", days_to_exam=5, budget_minutes=300)).picks
    }
    assert scores["learn"] == 120 and scores["revise"] == 900  # 600 x 20 percent, 600 x 150 percent


def test_miss_penalty_demotes_a_task_that_keeps_expiring():
    fresh = cp.compose([cand("x")], ctx()).picks[0].score
    nagged = cp.compose([cand("x", miss_count=2)], ctx()).picks[0].score
    capped = cp.compose([cand("x", miss_count=9)], ctx()).picks[0].score
    assert fresh - nagged == 80 and fresh - capped == 120


def test_comeback_ignores_must_do_except_a_near_amendment():
    rows = [
        cand("milestone", slot="read", group="learn", must_do=True, minutes=10),
        cand("amendment", paper=None, slot="amendment", group="news", must_do=True, minutes=10),
    ]
    near = cp.compose(rows, ctx(comeback=True, days_to_exam=10, phase="final", max_tasks=5))
    far = cp.compose(rows, ctx(comeback=True, days_to_exam=40, phase="consolidate", max_tasks=5))
    flags = lambda s: {p.candidate.dedupe_key: p.breakdown["must_do"] for p in s.picks}  # noqa: E731
    assert flags(near) == {"milestone": False, "amendment": True}
    assert flags(far) == {"milestone": False, "amendment": False}


def test_comeback_caps_the_plan_at_five_tasks():
    rows = [
        cand(f"{paper}-{slot}", paper=paper, slot=slot, minutes=1)
        for paper in ("p1", "p2", "p3")
        for slot in ("mcq", "formula", "section", "practical")
    ]
    sel = cp.compose(
        rows, ctx(papers=("p1", "p2", "p3"), focus_papers=3, budget_minutes=300, max_tasks=5, comeback=True)
    )
    assert len(sel.picks) == 5


# ---- rotation ---------------------------------------------------------------------------------------------------------------


def test_a_never_touched_paper_counts_as_starved_so_new_students_rotate():
    papers = tuple(cp.PaperInfo(k, None) for k in ("a", "b", "c"))
    rows = [cand(f"{k}1", paper=k, slot="mcq", sig=(50, 50, 50, 50)) for k in ("a", "b", "c")]
    sel = cp.compose(rows, cp.Context(**{**ctx().__dict__, "papers": papers}))
    assert set(sel.starved) == {"a", "b", "c"}


def test_a_starved_paper_outranks_a_slightly_louder_one():
    rows = [
        cand("loud", paper="taxation", slot="mcq", sig=(60, 60, 60, 60)),  # need 600
        cand("quiet", paper="audit", slot="mcq", sig=(50, 50, 50, 50)),  # need 500 + 150 for six days of silence
    ]
    papers = (cp.PaperInfo("taxation", 0), cp.PaperInfo("audit", 6))
    base = ctx()
    sel = cp.compose(rows, cp.Context(**{**base.__dict__, "papers": papers, "focus_papers": 1}))
    assert sel.focus == ("audit",)
