"""R2-W1 over HTTP: the quick-revision plan, the quick and cram queue sources, the exam block of Today, rebalance near the exam."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from django.utils import timezone

from modules.coverage.models import Enrollment
from modules.recall.models import RecallCard, RecallItem, RecallSettings
from modules.recall.services import catchup

from .factories import make_card, make_item
from .w5 import ME

pytestmark = pytest.mark.django_db
FIXED = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)  # 09:30 in Asia/Kolkata


@pytest.fixture
def clock(monkeypatch):
    """Freeze `timezone.now` so the exam is a known number of days away at any hour the suite runs."""
    state = {"now": FIXED}
    monkeypatch.setattr(timezone, "now", lambda: state["now"])
    return state


def enrol(scheme, exam: date | None):
    return Enrollment.objects.create(user_id=ME, scheme=scheme, level=scheme.level, exam_date=exam)


def mine(scheme, importance=2, state=2, stability=3.0, last_days=30, text=None, **extra):
    item = make_item(ME, text=text or f"Q {uuid.uuid4()}")
    RecallItem.objects.filter(pk=item.pk).update(scheme_id=scheme.id)
    fields = {}
    if state:
        last = FIXED - timedelta(days=last_days)
        fields = {
            "state": state,
            "stability": stability,
            "difficulty": 5.0,
            "reps": 3,
            "last_review_at": last,
            "due_scheduled_at": last + timedelta(days=stability),
            "due_at": last + timedelta(days=stability),
        }
    return make_card(item, ME, importance=importance, **fields, **extra)


def get(api, path, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return api.get(path + (f"?{q}" if q else ""))


def code(res):
    return res.json_body["error"]["code"]


def test_the_plan_needs_an_exam_date_and_a_future_one(api, scheme, clock):
    assert (
        code(get(api, "/recall/quick-revision/plan/")) == "no_exam_date"
        and get(api, "/recall/quick-revision/plan/").status_code == 422
    )
    enr = enrol(scheme, FIXED.date() - timedelta(days=1))
    res = get(api, "/recall/quick-revision/plan/")
    assert res.status_code == 422 and code(res) == "exam_passed"
    enr.exam_date = None
    enr.save()
    ok = get(api, "/recall/quick-revision/plan/", exam_date=(FIXED.date() + timedelta(days=30)).isoformat())
    assert ok.status_code == 200 and ok.json_body["too_few"] is True  # a preview date works without an enrolment date


def test_the_plan_counts_the_cards_at_risk_and_shows_a_sample(api, scheme, clock):
    enrol(scheme, FIXED.date() + timedelta(days=37))
    for _ in range(25):
        mine(scheme)  # mandatory, weak memory, long ago: at risk on exam day
    for _ in range(5):
        mine(scheme, importance=0)  # bullets are never in the plan
    mine(scheme, importance=1, stability=900.0, last_days=2)  # safe
    res = get(api, "/recall/quick-revision/plan/")
    assert res.status_code == 200
    b = res.json_body
    assert (b["candidates"], b["selected"], b["cut_off"], b["too_few"]) == (25, 25, 0, False)
    assert b["days_to_exam"] == 36 and b["window_days"] == 34 and b["per_day"] == 1
    assert len(b["sample"]) == 5 and all(c["importance"] == 2 for c in b["sample"])
    small = get(
        api, "/recall/quick-revision/plan/", minutes=5, exam_date=(FIXED.date() + timedelta(days=5)).isoformat()
    )
    assert (small.json_body["window_days"], small.json_body["selected"], small.json_body["per_day"]) == (2, 25, 13)
    assert get(api, "/recall/quick-revision/plan/", minutes=2).status_code == 400


def test_only_cards_of_my_enrolment_count_and_nobody_sees_anothers(api, other_api, scheme, clock):
    enrol(scheme, FIXED.date() + timedelta(days=20))
    mine(scheme)
    stray = make_item(ME, text="unlinked")
    make_card(
        stray, ME, importance=2, state=2, stability=2.0, difficulty=5.0, reps=2, last_review_at=FIXED - timedelta(days=40),
        due_scheduled_at=FIXED - timedelta(days=30), due_at=FIXED - timedelta(days=30),
    )  # fmt: skip
    assert get(api, "/recall/quick-revision/plan/").json_body["candidates"] == 1
    assert get(other_api, "/recall/quick-revision/plan/").status_code == 422  # the other student has no exam


def test_the_quick_queue_follows_the_plan_and_excludes_what_was_served(api, scheme, clock):
    enrol(scheme, FIXED.date() + timedelta(days=30))
    cards = [mine(scheme, stability=2.0 + i) for i in range(6)]
    first = get(api, "/recall/queue/", source="quick", limit=4).json_body["cards"]
    assert len(first) == 4
    rest = get(api, "/recall/queue/", source="quick", limit=4, exclude=",".join(c["id"] for c in first)).json_body[
        "cards"
    ]
    assert len(rest) == 2 and not {c["id"] for c in rest} & {c["id"] for c in first}
    assert {c["id"] for c in first + rest} == {str(c.id) for c in cards}
    assert first[0]["id"] == str(cards[0].id)  # the weakest memory first


def test_cram_opens_in_the_last_day_and_serves_only_mandatory_cards(api, scheme, clock):
    enrol(scheme, FIXED.date() + timedelta(days=10))
    mine(scheme)
    assert code(get(api, "/recall/queue/", source="cram")) == "cram_not_open"
    clock["now"] = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)  # the exam is 11 Nov 04:00 IST: 10.5 hours left
    mandatory, bullet = mine(scheme), mine(scheme, importance=0)
    res = get(api, "/recall/queue/", source="cram")
    ids = {c["id"] for c in res.json_body["cards"]}
    assert res.status_code == 200 and str(bullet.id) not in ids and str(mandatory.id) in ids


def test_today_carries_the_exam_countdown_the_quick_banner_and_pacing(api, scheme, clock):
    assert get(api, "/recall/today/").json_body["exam"] is None
    enrol(scheme, FIXED.date() + timedelta(days=61))
    for _ in range(3):
        mine(scheme)
    for _ in range(100):
        mine(scheme, importance=1, state=0)  # unseen
    exam_block = get(api, "/recall/today/").json_body["exam"]
    assert exam_block["days_to_exam"] == 60 and exam_block["cram_open"] is False and exam_block["quick"] is None
    p = exam_block["pacing"]
    assert (p["unseen"], p["window_days"], p["new_per_day"]) == (100, 46, 10)
    assert p["introduced_at_limit"] == 100 and p["feasible"] is True
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"new_per_day": 2})
    p = get(api, "/recall/today/").json_body["exam"]["pacing"]
    assert (p["introduced_at_limit"], p["needed_per_day"], p["feasible"]) == (92, 3, False)
    clock["now"] = FIXED + timedelta(days=20)  # 40 days out: the banner appears
    assert get(api, "/recall/today/").json_body["exam"]["quick"]["candidates"] == 3


def test_rebalance_never_pushes_a_card_past_the_exam_cutoff(scheme):
    enrol(scheme, FIXED.date() + timedelta(days=3))
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"reviews_per_day": 20})
    for _ in range(70):
        c = mine(scheme, stability=1.0, last_days=5)
        RecallCard.objects.filter(pk=c.pk).update(due_at=FIXED - timedelta(hours=2))
    out = catchup.rebalance(ME, 7, now=FIXED)
    exam_at = datetime(2026, 11, 4, 4, 0, tzinfo=UTC) - timedelta(hours=5, minutes=30)
    assert out["moved"] == sum(out["per_day"]) and out["moved"] == 20 and out["per_day"][1:] == [0] * 6
    latest = max(
        RecallCard.objects.filter(user_id=ME).values_list("postponed_until", flat=True), key=lambda d: d or FIXED
    )
    assert latest <= exam_at - timedelta(days=2)


# ---------------------------------------------------------------------------------------------- unlock by coverage
def _chapters():
    from modules.syllabus.models import Chapter

    a, b = Chapter.objects.get(key="gst-itc"), Chapter.objects.get(key="residential-status")
    return {"a": a.id, "b": b.id}


def _subscribed_deck(api, chapter_ids, unlock_mode="with_coverage"):
    from modules.recall.services import decks as deck_service

    from .w11 import EDITOR, draft_deck, platform_item

    items = [platform_item(f"U{i}", importance="important", chapter_id=c) for i, c in enumerate(chapter_ids)]
    deck, draft = draft_deck(items)
    deck_service.publish_deck_version(EDITOR, deck.id, draft.id)
    res = api.post(f"/recall/decks/{deck.id}/subscribe/", {"unlock_mode": unlock_mode})
    assert res.status_code == 201, res.json_body
    return deck


def _new_in_queue(api):
    cards = api.get("/recall/queue/?source=today&limit=50").json_body["cards"]
    return {uuid.UUID(c["chapter"]["id"]) for c in cards if c["state"] == 0 and c["chapter"]}


def test_new_cards_of_a_with_coverage_deck_wait_for_the_chapter_to_be_started(api, scheme, clock):
    from modules.coverage.models import ChapterProgress

    CH = _chapters()
    enr = enrol(scheme, FIXED.date() + timedelta(days=100))
    _subscribed_deck(api, [CH["a"], CH["b"], CH["a"]])
    assert _new_in_queue(api) == set()
    ChapterProgress.objects.create(user_id=ME, enrollment=enr, chapter_id=CH["a"], status="reading")
    assert _new_in_queue(api) == {CH["a"]}


def test_an_excluded_or_untouched_chapter_is_not_started(api, scheme, clock):
    from modules.coverage.models import ChapterProgress

    CH = _chapters()
    enr = enrol(scheme, FIXED.date() + timedelta(days=100))
    _subscribed_deck(api, [CH["a"]])
    ChapterProgress.objects.create(user_id=ME, enrollment=enr, chapter_id=CH["a"], status="not_started")
    assert _new_in_queue(api) == set()
    ChapterProgress.objects.filter(user_id=ME).update(status="reading", is_excluded=True)
    assert _new_in_queue(api) == set()


def test_everything_opens_within_sixty_days_of_the_exam_and_for_all_mode_decks(api, scheme, clock):
    CH = _chapters()
    enrol(scheme, FIXED.date() + timedelta(days=100))
    _subscribed_deck(api, [CH["a"]])
    assert _new_in_queue(api) == set()
    clock["now"] = FIXED + timedelta(days=41)  # 59 days out
    assert _new_in_queue(api) == {CH["a"]}


def test_all_mode_decks_chapter_filters_and_her_own_cards_are_never_locked(api, scheme, clock):
    CH = _chapters()
    enrol(scheme, FIXED.date() + timedelta(days=100))
    _subscribed_deck(api, [CH["b"]], unlock_mode="all")
    assert _new_in_queue(api) == {CH["b"]}
    _subscribed_deck(api, [CH["a"]])
    assert CH["a"] not in _new_in_queue(api)
    chosen = api.get(f"/recall/queue/?source=chapter&chapter_id={CH['a']}&limit=50").json_body["cards"]
    assert len(chosen) == 1  # asking for the chapter is starting it
    mine(scheme, state=0)  # one of her own, with no subscription
    today = api.get("/recall/queue/?source=today&limit=50").json_body["cards"]
    assert len(today) == 2 and CH["a"] not in _new_in_queue(api)  # hers and the open deck's, never the locked chapter's
