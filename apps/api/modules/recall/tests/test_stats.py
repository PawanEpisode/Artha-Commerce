"""Stats (FR-F15-71, 72): summary, retention, forecast, chapters, the 60 second ETag, `provide_today`, `due_counts`, `recall_strength`."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.recall import selectors
from modules.recall.models import RecallDailyRollup, RecallSettings
from modules.recall.services import reviews

from .w5 import ME, ev
from .w6 import library

pytestmark = pytest.mark.django_db


def rollup(day_offset, reviews_n, **extra):
    study = selectors.load_study(ME, timezone.now())
    RecallDailyRollup.objects.update_or_create(
        user_id=ME,
        local_date=study.today - timedelta(days=day_offset),
        defaults={"review_reviews": reviews_n, "good": reviews_n, "seconds": reviews_n * 10, **extra},
    )


def test_summary_streak_series_and_totals(api):
    for offset, n in ((0, 6), (1, 5), (2, 9), (3, 2), (4, 7), (5, 8)):
        rollup(offset, n)
    body = api.get("/recall/stats/summary/?range=7d").json_body
    assert body["streak"] == 3 and body["longest_streak"] == 3 and body["reviews"] == 37
    assert [d["reviews"] for d in body["series"]] == [8, 7, 2, 9, 5, 6] and body["minutes"] == 6
    assert body["ratings"]["good"] == 37 and body["range"] == "7d" and body["true_retention"] is None
    assert api.get("/recall/stats/summary/?range=3d").status_code == 400


def test_the_streak_is_not_lost_before_the_day_is_over_and_the_study_day_starts_at_four(api):
    rollup(1, 5)
    rollup(2, 5)
    assert api.get("/recall/stats/summary/").json_body["streak"] == 2  # today has not reached five yet
    s = selectors.load_study(ME, timezone.now())
    from datetime import UTC, datetime

    half_past_midnight_ist = datetime(2026, 10, 9, 19, 0, tzinfo=UTC)  # 00:30 on the 10th in India
    assert selectors.load_study(ME, half_past_midnight_ist).today.isoformat() == "2026-10-09"
    assert s.day_start_hour == 4


def test_the_streak_survives_vacation_because_days_are_not_cut(api):
    rollup(0, 6)
    rollup(1, 5)
    RecallSettings.objects.update_or_create(
        user_id=ME, defaults={"vacation_until": timezone.now().date() + timedelta(days=3)}
    )
    assert api.get("/recall/stats/summary/").json_body["streak"] == 2


def test_true_retention_is_the_share_of_review_phase_answers_that_were_not_again(api):
    now = timezone.now()
    cards = library(10, shape=lambda i: "due")
    for i, c in enumerate(cards):
        reviews.submit_review(ME, ev(c, 1 if i < 2 else 3, now - timedelta(minutes=30 - i)), now=now)
    body = api.get("/recall/stats/summary/").json_body
    assert body["true_retention"] == 0.8
    ret = api.get("/recall/stats/retention/").json_body
    assert ret["overall"] == 0.8 and ret["target"] == 0.9 and ret["series"][0]["reviews"] == 10


def test_forecast_counts_cards_per_study_day_with_overdue_on_day_zero(api):
    now = timezone.now()
    library(6, shape=lambda i: "due")  # 3 days overdue
    cards = library(4, shape=lambda i: "later")  # due in 5 days
    body = api.get("/recall/stats/forecast/").json_body
    assert len(body["days"]) == 30 and body["days"][0]["due"] == 6 and body["overdue"] == 6
    assert sum(d["due"] for d in body["days"][4:7]) == 4 and body["days"][0]["date"] == body["today"]
    assert len(api.get("/recall/stats/forecast/?days=7").json_body["days"]) == 7
    assert cards and now


def test_chapters_show_recall_strength_card_counts_and_due_counts(api):
    ch1, ch2 = uuid.uuid4(), uuid.uuid4()
    library(8, shape=lambda i: "due", chapter_id=ch1)
    library(4, shape=lambda i: "later", chapter_id=ch2)
    library(3, shape=lambda i: "new")
    rows = api.get("/recall/stats/chapters/").json_body["chapters"]
    by = {r["chapter"]["id"] if r["chapter"] else None: r for r in rows}
    assert by[str(ch1)]["cards"] == 8 and by[str(ch1)]["due"] == 8 and by[str(ch2)]["due"] == 0
    assert by[None]["strength"] is None and by[None]["cards"] == 3
    assert 0 < by[str(ch1)]["strength"] < by[str(ch2)]["strength"] <= 1  # overdue cards are weaker
    assert rows[0]["chapter"]["id"] == str(ch1)  # weakest first


@pytest.mark.parametrize("name", ["summary", "retention", "forecast", "chapters"])
def test_reports_send_an_etag_and_answer_304_until_something_changes(api, name):
    library(5, shape=lambda i: "due")
    first = api.get(f"/recall/stats/{name}/")
    tag = first["ETag"]
    assert first["Cache-Control"] == "private, no-cache" and tag
    again = api.c.get(f"/api/v1/recall/stats/{name}/", HTTP_IF_NONE_MATCH=tag)
    assert again.status_code == 304 and again.content == b""
    card = library(1, shape=lambda i: "due")[0]
    reviews.submit_review(ME, ev(card, 3, timezone.now() - timedelta(minutes=1)), now=timezone.now())
    assert api.get(f"/recall/stats/{name}/")["ETag"] != tag


def test_each_student_sees_only_her_own_numbers(api, other_api):
    rollup(0, 9)
    library(5, shape=lambda i: "due")
    assert other_api.get("/recall/stats/summary/").json_body["reviews"] == 0
    assert other_api.get("/recall/stats/forecast/").json_body["days"][0]["due"] == 0
    assert other_api.get("/recall/stats/chapters/").json_body["chapters"] == []


def test_selectors_for_other_features(api):
    now = timezone.now()
    ch = uuid.uuid4()
    library(8, shape=lambda i: ("due", "later", "learning", "new")[i % 4], chapter_id=ch, subjects=("taxation",))
    counts = selectors.due_counts(ME, now=now, chapter_ids=[ch])
    assert (counts.new, counts.learning, counts.due) == (2, 2, 2)
    assert selectors.due_counts(ME, now=now, subject_key="nothing") == selectors.DueCounts(0, 0, 0)
    strength = selectors.recall_strength(ME, [ch], now=now)
    assert strength[ch].cards == 8 and strength[ch].due == 4 and 0 < strength[ch].strength < 1


def test_provide_today_has_the_shape_f13_will_read_and_nothing_registers_it():
    now = timezone.now()
    assert selectors.provide_today(ME, now=now).tasks == []
    cs = library(12, shape=lambda i: "due")
    for c in cs[:6]:
        reviews.submit_review(ME, ev(c, 1, now - timedelta(minutes=3)), now=now)
    type(cs[0]).objects.filter(pk=cs[7].pk).update(needs_recheck=True, recheck_reason="amendment")
    out = selectors.provide_today(ME, now=now)
    assert out.key == "recall" and [t.kind for t in out.tasks] == ["recall_cards", "forgotten_cards", "recheck"]
    assert out.tasks[0].count > 0 and out.tasks[0].tiles and out.tasks[2].count == 1
    import modules.recall.provider as provider

    assert "provide_today" not in vars(provider)
