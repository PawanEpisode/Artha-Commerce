"""R2-W3 C: chapters due for revision (F-02) offer their mandatory cards first (FR-F15-63): daily queue, offline pack, quick plan."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from modules.coverage.models import ChapterProgress, Enrollment
from modules.recall.models import RecallItem, RecallSettings
from modules.recall.selectors import exam as exam_reads
from modules.recall.selectors import load_study, pack_for_device
from modules.recall.selectors import queue as queue_reads
from modules.syllabus.models import Chapter

from .w5 import ME, card, days

pytestmark = pytest.mark.django_db
NOW = days(2)  # 2026-10-11 08:00 UTC
YESTERDAY = date(2026, 10, 10)


@pytest.fixture
def enrolled(scheme):
    return Enrollment.objects.create(user_id=ME, scheme=scheme, level=scheme.level, exam_date=date(2026, 12, 1))


@pytest.fixture
def gst(scheme):
    return Chapter.objects.get(key="gst-itc")


@pytest.fixture
def residential(scheme):
    return Chapter.objects.get(key="residential-status")


def make_due(chapter, enrolled, due=YESTERDAY):
    return ChapterProgress.objects.create(user_id=ME, enrollment=enrolled, chapter=chapter, next_revision_due=due)


def due_review(chapter, importance, overdue_days):
    at = NOW - timedelta(days=overdue_days)
    return card(
        ME,
        chapter_id=chapter.id,
        importance=importance,
        state=2,
        stability=5.0,
        difficulty=5.0,
        reps=2,
        last_review_at=at - timedelta(days=5),
        due_scheduled_at=at,
        due_at=at,
        subject_key=chapter.subject.key,
    )


def fill_the_day(chapter, n=20):
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"reviews_per_day": 20})
    return [due_review(chapter, 1, 30) for _ in range(n)]


def ids_of(queue):
    return list(queue.ids)


def test_a_due_chapters_mandatory_card_is_offered_first_and_survives_the_limit(enrolled, gst, residential):
    fill_the_day(residential)
    mine = due_review(gst, 2, 0.2)
    study = load_study(ME, NOW)
    queue, _ = queue_reads.plan_today(study)
    assert str(mine.id) not in queue.ids  # without the boost the twenty overdue ones fill the day
    make_due(gst, enrolled)
    queue, _ = queue_reads.plan_today(load_study(ME, NOW))
    assert queue.ids[0] == str(mine.id) and len(queue.ids) == 20


def test_only_mandatory_cards_of_due_chapters_are_boosted(enrolled, gst, residential):
    fill_the_day(residential)
    make_due(gst, enrolled)
    important = due_review(gst, 1, 0.2)
    elsewhere = due_review(residential, 2, 0.2)
    study = load_study(ME, NOW)
    boosted = queue_reads.boosted_ids(study)
    assert str(important.id) not in boosted and str(elsewhere.id) not in boosted


def test_a_chapter_not_yet_due_or_excluded_gives_no_boost(enrolled, gst):
    mine = due_review(gst, 2, 1)
    make_due(gst, enrolled, due=date(2026, 10, 12))  # tomorrow
    assert queue_reads.boosted_ids(load_study(ME, NOW)) == frozenset()
    ChapterProgress.objects.filter(chapter=gst).update(next_revision_due=YESTERDAY, is_excluded=True)
    assert queue_reads.boosted_ids(load_study(ME, NOW)) == frozenset() and mine.id


def test_without_an_enrolment_nothing_is_boosted_and_nothing_fails(gst):
    due_review(gst, 2, 1)
    assert queue_reads.boosted_ids(load_study(ME, NOW)) == frozenset()
    queue, _ = queue_reads.plan_today(load_study(ME, NOW))
    assert len(queue.ids) == 1


def test_another_students_due_chapter_does_not_boost_mine(enrolled, gst, scheme):
    other = Enrollment.objects.create(user_id=__import__("uuid").uuid4(), scheme=scheme, level=scheme.level)
    ChapterProgress.objects.create(user_id=other.user_id, enrollment=other, chapter=gst, next_revision_due=YESTERDAY)
    due_review(gst, 2, 1)
    assert queue_reads.boosted_ids(load_study(ME, NOW)) == frozenset()


def test_the_boost_costs_no_extra_query_without_a_due_chapter_and_one_with(enrolled, gst):
    for _ in range(30):
        due_review(gst, 2, 1)
    study = load_study(ME, NOW)
    with CaptureQueriesContext(connection) as without:
        queue_reads.boosted_ids(study)
    make_due(gst, enrolled)
    with CaptureQueriesContext(connection) as with_due:
        found = queue_reads.boosted_ids(study)
    assert len(found) == 30 and len(with_due) == len(without) + 1  # one read of her cards, however many


def test_the_offline_pack_takes_the_boosted_cards_first_when_it_is_capped(enrolled, gst, residential):
    fill_the_day(residential, 40)
    mine = due_review(gst, 2, 0.2)
    pack = pack_for_device(ME, now=NOW, limit=5)
    assert str(mine.id) not in {str(c.card.id) for c in pack.cards}
    make_due(gst, enrolled)
    pack = pack_for_device(ME, now=NOW, limit=5)
    assert str(mine.id) in {str(c.card.id) for c in pack.cards}


def test_the_quick_plan_puts_a_due_chapters_mandatory_cards_first(enrolled, gst, residential, scheme):
    for _ in range(3):
        due_review(
            residential, 2, 0.5
        )  # these get the same predicted recall as the one below, so only the boost decides
    mine = due_review(gst, 2, 0.5)
    RecallItem.objects.filter(owner_user_id=ME).update(
        scheme_id=scheme.id
    )  # "my chapters": the scheme she is enrolled in
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"quick_minutes_per_day": 5})
    study = load_study(ME, NOW)
    plain = exam_reads.quick_plan(study, minutes=5).plan
    make_due(gst, enrolled)
    boosted = exam_reads.quick_plan(load_study(ME, NOW), minutes=5).plan
    assert plain.candidates == boosted.candidates and boosted.ids[0] == str(mine.id)


def test_the_queue_endpoint_serves_the_boosted_card_first(api, enrolled, gst, residential, monkeypatch):
    from django.utils import timezone

    monkeypatch.setattr(timezone, "now", lambda: NOW)
    fill_the_day(residential)
    mine = due_review(gst, 2, 0.2)
    make_due(gst, enrolled)
    body = api.get("/recall/queue/?source=today&limit=5").json_body
    assert body["cards"][0]["id"] == str(mine.id)
