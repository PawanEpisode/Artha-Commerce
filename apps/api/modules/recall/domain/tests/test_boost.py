"""R2-W3 C: the revision boost in the planner and the quick set (pure). With nothing boosted the order is what it always was."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from modules.recall.domain import exam
from modules.recall.domain import scheduling as sc
from modules.recall.domain.fsrs6 import DEFAULT_WEIGHTS

W20 = DEFAULT_WEIGHTS[20]
NOW = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)
DAY_END = NOW + timedelta(hours=16)


def review(i, importance, overdue_days, subject="A"):
    last = NOW - timedelta(days=overdue_days + 5)
    return sc.CardView(i, subject, importance, 2, 5.0, last, NOW - timedelta(days=overdue_days))


def plan(cards, boosted=frozenset(), reviews=20, new=10, mode="off"):
    return sc.plan_queue(cards, NOW, sc.Limits(new, reviews), W20, mode=mode, day_end=DAY_END, boosted=boosted)


def test_no_boosted_cards_changes_nothing():
    cards = [review(f"c{i}", i % 3, i) for i in range(30)] + [
        sc.CardView(f"n{i}", "A", 1, 0, None, None, None, NOW) for i in range(5)
    ]
    assert plan(cards).ids == plan(cards, frozenset()).ids == plan(cards, frozenset({"unknown"})).ids


def test_boosted_reviews_come_first_whatever_their_priority():
    cards = [review("big", 2, 20), review("mid", 1, 10), review("boost", 2, 0)]
    assert plan(cards).ids[0] == "big"
    assert plan(cards, frozenset({"boost"})).ids == ("boost", "big", "mid")


def test_boosted_cards_survive_the_daily_limit_when_others_are_cut():
    others = [review(f"o{i}", 1, 30) for i in range(20)]  # twenty very overdue reviews fill the day
    boosted = review("boost", 2, 0)
    assert "boost" not in plan([*others, boosted]).ids
    out = plan([*others, boosted], frozenset({"boost"}))
    assert out.ids[0] == "boost" and len(out.ids) == 20 and out.reviews == 20  # the limit still holds


def test_the_limits_and_counts_do_not_move_with_a_boost():
    cards = [review(f"c{i}", 1, i) for i in range(10)]
    a, b = plan(cards), plan(cards, frozenset({"c9", "c8"}))
    assert (a.learning, a.reviews, a.new) == (b.learning, b.reviews, b.new) and set(a.ids) == set(b.ids)


def test_learning_cards_still_lead_and_new_cards_boost_among_themselves():
    learning = sc.CardView("learn", "A", 0, 1, 1.0, NOW - timedelta(hours=1), NOW - timedelta(minutes=5))
    new_a = sc.CardView("new-a", "A", 2, 0, None, None, None, NOW - timedelta(days=2))
    new_b = sc.CardView("new-b", "A", 1, 0, None, None, None, NOW - timedelta(days=3))
    out = plan([new_a, new_b, learning], frozenset({"new-b"}), new=1)
    assert out.ids == ("learn", "new-b")  # the boosted new card takes the single new slot over a mandatory one
    assert plan([new_a, new_b, learning], new=1).ids == ("learn", "new-a")


def test_subjects_alternate_inside_each_group_but_the_boosted_group_stays_first():
    cards = [review("b1", 2, 5, "A"), review("b2", 2, 5, "A"), review("x1", 2, 20, "B"), review("x2", 2, 20, "B")]
    out = plan(cards, frozenset({"b1", "b2"}))
    assert out.ids[:2] == ("b1", "b2") and set(out.ids[2:]) == {"x1", "x2"}


def test_the_quick_set_takes_boosted_mandatory_cards_before_the_budget_cut():
    exam_at = NOW + timedelta(days=30)
    risky = exam.QuickCard("risky", 2, 2, 1.0, NOW - timedelta(days=40))  # about to be forgotten
    steady = exam.QuickCard("steady", 2, 2, 12.0, NOW - timedelta(days=1), boosted=True)  # better recall, chapter due
    assert exam.r_exam(12.0, NOW - timedelta(days=1), exam_at, W20) < 0.90  # it qualifies
    assert exam.r_exam(12.0, NOW - timedelta(days=1), exam_at, W20) > exam.r_exam(
        1.0, NOW - timedelta(days=40), exam_at, W20
    )
    one_card = dict(minutes_per_day=1, median_seconds=1680.0)  # 28 days x 60 s / 1680 s = one card fits
    unboosted = exam.QuickCard("steady", 2, 2, 12.0, NOW - timedelta(days=1))
    assert exam.quick_set([risky, unboosted], exam_at, now=NOW, w20=W20, **one_card).ids == ("risky",)  # as before
    boosted = exam.quick_set([risky, steady], exam_at, now=NOW, w20=W20, **one_card)
    assert boosted.ids == ("steady",) and (boosted.candidates, boosted.cut_off) == (2, 1)  # the chapter due goes first


def test_a_boosted_new_mandatory_card_counts_and_a_boosted_bullet_is_ignored():
    exam_at = NOW + timedelta(days=30)
    cards = [
        exam.QuickCard("new-m", 2, 0, None, None, boosted=True),
        exam.QuickCard("bullet", 0, 2, 3.0, NOW - timedelta(days=40), boosted=True),
    ]
    out = exam.quick_set(cards, exam_at, 60, 20.0, NOW, W20)
    assert out.ids == ("new-m",)
