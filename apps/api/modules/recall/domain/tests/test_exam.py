"""Exam horizon, retention boost, R_exam, quick set, cram window and pacing (pure). Hand-checked numbers plus properties."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from modules.recall.domain import exam
from modules.recall.domain.fsrs6 import DEFAULT_WEIGHTS, retrievability

W20 = DEFAULT_WEIGHTS[20]
EXAM = datetime(2026, 12, 20, 0, 0, tzinfo=UTC)
NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)  # 39.6 days out
SLOT0 = "ffffffff-0000-4000-8000-000000000000"  # 0xffffffff mod 5 = 0
SLOT3 = "00000003-0000-4000-8000-000000000000"  # 3 mod 5 = 3


def d(days: float) -> timedelta:
    return timedelta(days=days)


def test_the_slot_is_the_first_eight_hex_digits_mod_five():
    assert exam.slot_of(SLOT0) == 0 and exam.slot_of(SLOT3) == 3
    assert {exam.slot_of(f"{i:08x}-0000-4000-8000-000000000000") for i in range(50)} == {0, 1, 2, 3, 4}


def test_a_card_due_after_the_exam_moves_into_the_final_window():
    due = EXAM + d(10)
    assert exam.horizon(due, NOW - d(30), EXAM, SLOT0, NOW) == EXAM - d(7)
    assert exam.horizon(due, NOW - d(30), EXAM, SLOT3, NOW) == EXAM - d(4)


def test_a_card_due_before_the_cutoff_or_reviewed_recently_or_with_the_setting_off_stays():
    keep = EXAM - d(2) - timedelta(minutes=1)
    assert exam.horizon(keep, NOW - d(30), EXAM, SLOT0, NOW) == keep
    late = EXAM + d(10)
    assert exam.horizon(late, EXAM - d(5), EXAM, SLOT0, NOW) == late  # seen within the last 6 days of the exam
    assert exam.horizon(late, NOW - d(30), EXAM, SLOT0, NOW, enabled=False) == late
    assert exam.horizon(late, NOW - d(30), None, SLOT0, NOW) == late
    assert exam.horizon(None, None, EXAM, SLOT0, NOW) is None


def test_outside_ninety_days_and_inside_the_last_day_nothing_moves():
    late = EXAM + d(10)
    assert exam.horizon(late, NOW, EXAM, SLOT0, EXAM - d(91)) == late
    assert exam.horizon(late, NOW, EXAM, SLOT0, EXAM - d(89), enabled=True) != late
    assert exam.horizon(late, NOW, EXAM, SLOT0, EXAM - timedelta(hours=20)) == late
    assert exam.horizon(late, NOW, EXAM, SLOT0, EXAM + d(1)) == late  # the exam has passed


def test_never_earlier_than_tomorrow_and_never_later_than_the_own_due_date():
    assert exam.horizon(EXAM + d(3), None, EXAM, SLOT0, EXAM - d(3)) == EXAM - d(2)  # now + 1 day
    inside = EXAM - d(1)
    assert exam.horizon(inside, NOW - d(40), EXAM, SLOT3, NOW) == min(inside, EXAM - d(4)) == EXAM - d(4)


@pytest.mark.parametrize("seed", range(30))
def test_horizon_properties(seed):
    rnd = random.Random(seed)
    now = NOW + d(rnd.uniform(-5, 45))
    due = now + d(rnd.uniform(0, 200))
    last = now - d(rnd.uniform(0, 120))
    card = f"{rnd.getrandbits(32):08x}-0000-4000-8000-000000000000"
    out = exam.horizon(due, last, EXAM, card, now)
    assert out <= due  # never later than the scheduler's own date
    assert exam.horizon(out, last, EXAM, card, now) == out  # idempotent
    if out != due:
        assert out >= now + d(1) and out <= EXAM - d(2) + d(1)  # in front of the exam


def test_mandatory_cards_get_a_higher_retention_only_in_the_last_thirty_days():
    assert exam.retention_for(2, 0.90, 29.9) == 0.95
    assert exam.retention_for(2, 0.97, 10) == 0.97  # never lowers a higher setting
    assert exam.retention_for(2, 0.90, 31) == 0.90
    assert exam.retention_for(1, 0.90, 10) == 0.90
    assert exam.retention_for(2, 0.90, 10, enabled=False) == 0.90
    assert exam.retention_for(2, 0.90, None) == 0.90 and exam.retention_for(2, 0.90, -1) == 0.90


def test_r_exam_is_retrievability_at_the_gap_between_last_review_and_the_exam():
    last = EXAM - d(30)
    assert exam.r_exam(10.0, last, EXAM, W20) == pytest.approx(retrievability(10.0, 30.0, W20))
    assert exam.r_exam(None, last, EXAM, W20) is None and exam.r_exam(10.0, None, EXAM, W20) is None


def qc(i, importance=2, phase=2, stability=5.0, last_days=20):
    return exam.QuickCard(f"c{i:03d}", importance, phase, stability, NOW - d(last_days))


def test_the_quick_set_keeps_important_cards_at_risk_and_unseen_mandatory_and_orders_by_risk():
    cards = [
        qc(1, importance=0),  # bullets never
        qc(2, importance=1, stability=500.0),  # safe on exam day
        qc(3, importance=1, stability=4.0),
        qc(4, importance=2, stability=4.0),  # same risk as 3 but mandatory: first
        exam.QuickCard("new-m", 2, 0, None, None),
        exam.QuickCard("new-i", 1, 0, None, None),  # unseen but only important: not included
    ]
    plan = exam.quick_set(cards, EXAM, 30, 12.0, NOW, W20)
    assert set(plan.ids) == {"c003", "c004", "new-m"}
    assert plan.ids[0] == "new-m" and plan.ids.index("c004") < plan.ids.index("c003")
    assert (plan.candidates, plan.selected, plan.cut_off, plan.too_few) == (3, 3, 0, True)
    assert plan.days_to_exam == 39 and plan.window_days == 37


def test_the_minute_budget_cuts_the_set_and_the_plan_says_how_many_were_left_out():
    cards = [qc(i, importance=2, stability=3.0) for i in range(100)]
    plan = exam.quick_set(cards, EXAM, 5, 30.0, NOW, W20)  # 5 min x 37 days x 60 / 30 s = 370: all fit
    assert plan.selected == 100 and plan.cut_off == 0 and not plan.too_few
    small = exam.quick_set(cards, EXAM, 5, 30.0, EXAM - d(5), W20)  # 3 days x 10 cards = 30
    assert (small.window_days, small.selected, small.cut_off) == (3, 30, 70)
    assert small.per_day == 10 and small.minutes_per_day == 5


def test_with_two_days_or_fewer_left_the_plan_is_empty():
    plan = exam.quick_set([qc(1)], EXAM, 30, 12.0, EXAM - d(2), W20)
    assert plan.ids == () and plan.window_days == 0 and plan.per_day == 0 and plan.minutes_per_day == 0


@pytest.mark.parametrize("seed", range(20))
def test_quick_set_properties(seed):
    rnd = random.Random(seed)
    cards = [
        qc(i, rnd.randint(0, 2), rnd.choice([0, 2, 2, 3]), rnd.uniform(1, 80), rnd.randint(1, 60)) for i in range(60)
    ]
    cards = [c if c.phase else exam.QuickCard(c.id, c.importance, 0, None, None) for c in cards]
    a = exam.quick_set(cards, EXAM, rnd.choice([5, 30, 120]), 15.0, NOW, W20)
    b = exam.quick_set(list(reversed(cards)), EXAM, 30, 15.0, NOW, W20)
    assert len(set(a.ids)) == len(a.ids) and a.selected + a.cut_off == a.candidates
    wide = exam.quick_set(cards, EXAM, 240, 15.0, NOW, W20)
    assert set(a.ids) <= set(wide.ids)  # a bigger budget only adds cards
    assert exam.quick_set(list(reversed(cards)), EXAM, 240, 15.0, NOW, W20).ids == wide.ids  # input order is irrelevant
    assert b.candidates == exam.quick_set(cards, EXAM, 30, 15.0, NOW, W20).candidates


def test_the_cram_window_is_the_last_twenty_four_hours():
    assert exam.cram_open(EXAM - timedelta(hours=24), EXAM) and exam.cram_open(EXAM - timedelta(minutes=1), EXAM)
    assert not exam.cram_open(EXAM - timedelta(hours=24, minutes=1), EXAM)
    assert not exam.cram_open(EXAM, EXAM) and not exam.cram_open(EXAM + d(1), EXAM) and not exam.cram_open(NOW, None)


def test_pacing_says_what_the_limit_introduces_and_what_it_would_take():
    p = exam.pacing(600, 60.4, 10)  # 46 days to introduce in: exam - 14d
    assert (p.window_days, p.introduced_at_limit, p.needed_per_day, p.feasible) == (46, 460, 14, False)
    ok = exam.pacing(300, 60.4, 10)
    assert (ok.introduced_at_limit, ok.needed_per_day, ok.feasible) == (300, 7, True)
    late = exam.pacing(40, 10, 10)  # inside the last 14 days: nothing can be introduced in time
    assert (late.window_days, late.introduced_at_limit, late.feasible) == (0, 0, False)
    assert exam.pacing(0, 5, 10).feasible and exam.pacing(0, 5, 10).needed_per_day == 0
