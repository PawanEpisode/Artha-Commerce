"""The read side (W6): today, queue, pack, forgotten, settings. Selectors are pure reads: no GET ever writes."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from modules.recall.models import RecallCard, RecallQuotaPlan, RecallSettings
from modules.recall.services import reviews

from .w5 import ME, ev
from .w6 import done_today, library

pytestmark = pytest.mark.django_db
WRITES = ("INSERT", "UPDATE", "DELETE")


def get(api, path, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return api.get(path + (f"?{q}" if q else ""))


def set_settings(**fields):
    RecallSettings.objects.update_or_create(user_id=ME, defaults=fields)


# ------------------------------------------------------------------------------------------------------ settings
def test_settings_default_without_creating_a_row_then_validated_updates(api):
    res = api.get("/recall/settings/")
    assert res.status_code == 200 and not RecallSettings.objects.filter(user_id=ME).exists()
    body = res.json_body
    assert (body["desired_retention"], body["new_per_day"], body["reviews_per_day"], body["tz"]) == (
        0.9,
        10,
        100,
        "Asia/Kolkata",
    )
    assert (
        body["learning_steps_min"] == [1, 10]
        and body["vacation_until"] is None
        and body["scheduler_version"] == "fsrs-6.0"
    )
    put = api.put("/recall/settings/", {"desired_retention": 0.93, "new_per_day": 15, "learning_steps_min": [1, 15]})
    assert put.status_code == 200 and put.json_body["desired_retention"] == 0.93
    assert api.get("/recall/settings/").json_body["new_per_day"] == 15
    assert api.put("/recall/settings/", {"new_per_day": 500}).status_code == 422
    assert api.put("/recall/settings/", {"vacation_until": "2030-01-01"}).status_code == 400  # has its own endpoint
    assert api.put("/recall/settings/", {"nonsense": 1}).status_code == 400


def test_one_student_never_sees_anothers_settings(api, other_api):
    api.put("/recall/settings/", {"new_per_day": 33})
    assert other_api.get("/recall/settings/").json_body["new_per_day"] == 10


# ------------------------------------------------------------------------------------------------------ today
def test_today_on_an_empty_library_is_a_calm_zero(api):
    body = api.get("/recall/today/").json_body
    assert (
        body["mode"] == "normal" and body["queue_size"] == 0 and body["counts"] == {"new": 0, "learning": 0, "due": 0}
    )
    assert body["est_minutes"] == 0 and body["next_due_at"] is None and body["forgotten"] == [] and body["exam"] is None
    assert body["limits"] == {"new_per_day": 10, "reviews_per_day": 100, "new_done": 0, "reviews_done": 0}


def test_today_counts_and_kind_tiles(api):
    library(40)
    body = api.get("/recall/today/").json_body
    assert body["counts"] == {"new": 10, "learning": 10, "due": 10} and body["queue_size"] == 30
    assert body["new_available"] == 10 and body["next_due_at"] is not None
    assert sum(t["total"] for t in body["tiles"]) == 30
    assert {t["subject_key"] for t in body["tiles"]} == {"taxation", "laws"}
    assert body["est_minutes"] >= 1


def test_catchup_starts_above_twice_the_daily_limit_and_pauses_new_cards(api):
    set_settings(reviews_per_day=20)
    library(41, shape=lambda i: "due" if i < 41 else "new")
    library(5, shape=lambda i: "new")
    body = api.get("/recall/today/").json_body
    assert body["mode"] == "catchup" and body["counts"]["new"] == 0 and body["counts"]["due"] == 20
    assert body["deferred"] == 21 and body["days_to_clear"] == 3 and body["catchup"]["active"]
    set_settings(pause_new_in_catchup=False)
    assert api.get("/recall/today/").json_body["counts"]["new"] == 5
    set_settings(catchup_mode="off", pause_new_in_catchup=True)
    assert api.get("/recall/today/").json_body["mode"] == "normal"


def test_catchup_also_starts_when_the_oldest_card_is_over_three_days_late(api):
    set_settings(reviews_per_day=20)
    library(30, shape=lambda i: "due")  # 30 is under 2 x 20 but is more than one day of work
    RecallCard.objects.filter(user_id=ME).update(due_at=timezone.now() - timedelta(days=2, hours=20))
    assert api.get("/recall/today/").json_body["mode"] == "normal"  # not yet over three days late
    RecallCard.objects.filter(user_id=ME).update(due_at=timezone.now() - timedelta(days=4))
    assert api.get("/recall/today/").json_body["mode"] == "catchup"


def test_the_daily_limits_cut_the_queue_and_do_20_more_lifts_the_review_limit(api):
    set_settings(reviews_per_day=20, new_per_day=3)
    library(20, shape=lambda i: "due")
    library(10, shape=lambda i: "new")
    done_today(reviews=15, new=1)
    body = api.get("/recall/today/").json_body
    assert body["counts"]["due"] == 5 and body["counts"]["new"] == 2 and body["deferred"] == 15
    assert body["limits"]["reviews_done"] == 15 and body["limits"]["new_done"] == 1
    base = get(api, "/recall/queue/", source="today", limit=50).json_body["cards"]
    more = get(api, "/recall/queue/", source="today", limit=50, extra=20).json_body["cards"]
    assert (len(base), len(more)) == (7, 22)


def test_vacation_empties_today_and_the_queue(api):
    library(10, shape=lambda i: "due")
    api.put("/recall/vacation/", {"until": (timezone.now() + timedelta(days=2)).date().isoformat()})
    assert RecallSettings.objects.get(user_id=ME).vacation_until
    body = api.get("/recall/today/").json_body
    assert body["mode"] == "vacation" and body["queue_size"] == 0
    assert get(api, "/recall/queue/").json_body["cards"] == []
    assert api.get("/recall/pack/").json_body["cards"] == []


def test_the_time_zone_parameter_moves_the_study_day(api):
    assert api.get("/recall/today/?tz=Pacific/Auckland").json_body["tz"] == "Pacific/Auckland"
    assert api.get("/recall/today/?tz=Mars/Base").status_code == 422


# ------------------------------------------------------------------------------------------------------ queue
def test_the_queue_puts_learning_first_then_reviews_by_risk_with_new_cards_woven_in(api):
    library(40)
    cards = get(api, "/recall/queue/", limit=50).json_body["cards"]
    states = [c["state"] for c in cards]
    assert states[:10] == [1] * 10 and 0 in states[10:14]  # a new card after every third review
    assert set(states) == {0, 1, 2} and len(cards) == 30
    first = cards[0]
    assert set(first) >= {
        "id",
        "rev",
        "item_version_id",
        "kind",
        "front_md",
        "back_md",
        "badges",
        "previews",
        "preview_days",
        "state",
        "chapter",
        "source",
    }
    assert set(first["previews"]) == {"1", "2", "3", "4"} and first["front_md"].startswith("Question")


def test_subjects_alternate_in_the_review_order_unless_interleaving_is_off(api):
    set_settings(new_per_day=0)
    library(3, shape=lambda i: "due", subjects=("taxation",), importance=2)
    library(3, shape=lambda i: "due", subjects=("laws",), importance=1)

    def order():
        cards = get(api, "/recall/queue/", limit=12).json_body["cards"]
        return [RecallCard.objects.get(pk=c["id"]).subject_key for c in cards]

    assert order() == ["taxation", "laws"] * 3
    set_settings(interleave=False)
    assert order() == ["taxation"] * 3 + ["laws"] * 3


def test_buried_suspended_and_deleted_cards_are_not_served(api):
    set_settings(new_per_day=0)
    cs = library(5, shape=lambda i: "due")
    RecallCard.objects.filter(pk=cs[0].pk).update(buried_until=timezone.now() + timedelta(hours=5))
    RecallCard.objects.filter(pk=cs[1].pk).update(status="suspended", suspend_reason="manual")
    RecallCard.objects.filter(pk=cs[2].pk).update(status="deleted", deleted_at=timezone.now())
    ids = {c["id"] for c in get(api, "/recall/queue/").json_body["cards"]}
    assert ids == {str(cs[3].id), str(cs[4].id)}
    RecallCard.objects.filter(pk=cs[0].pk).update(buried_until=timezone.now() - timedelta(minutes=1))
    assert str(cs[0].id) in {c["id"] for c in get(api, "/recall/queue/").json_body["cards"]}


def test_exclude_limit_and_unknown_sources(api):
    library(8, shape=lambda i: "due")
    first = get(api, "/recall/queue/", limit=3).json_body["cards"]
    assert len(first) == 3
    skip = ",".join(c["id"] for c in first)
    rest = get(api, "/recall/queue/", limit=50, exclude=skip).json_body["cards"]
    assert len(rest) == 5 and not {c["id"] for c in rest} & {c["id"] for c in first}
    assert get(api, "/recall/queue/", limit=51).status_code == 400
    assert get(api, "/recall/queue/", source="nonsense").status_code == 400
    assert get(api, "/recall/queue/", exclude="not-a-uuid").status_code == 400


@pytest.mark.parametrize("source", ["quick", "cram"])
def test_quick_and_cram_are_not_in_this_release(api, source):
    res = get(api, "/recall/queue/", source=source)
    assert res.status_code == 422 and res.json_body["error"]["code"] == "not_in_this_release"


def test_chapter_deck_and_review_ahead_sources(api):
    from modules.recall.models import RecallDeckItem
    from modules.recall.tests.factories import make_deck

    chapter = uuid.uuid4()
    inside = library(4, shape=lambda i: "due", chapter_id=chapter)
    library(4, shape=lambda i: "due")
    got = get(api, "/recall/queue/", source="chapter", chapter_id=chapter).json_body["cards"]
    assert {c["id"] for c in got} == {str(c.id) for c in inside}
    deck = make_deck(ME)
    RecallDeckItem.objects.create(deck=deck, item=inside[0].item)
    got = get(api, "/recall/queue/", source="deck", deck_id=deck.id).json_body["cards"]
    assert [c["id"] for c in got] == [str(inside[0].id)]
    library(3, shape=lambda i: "later")
    ahead = get(api, "/recall/queue/", source="review_ahead").json_body["cards"]
    assert len(ahead) == 3 and all(c["state"] == 2 for c in ahead)


def test_the_catchup_source_is_the_riskiest_cards_up_to_the_daily_limit(api):
    set_settings(reviews_per_day=20)
    library(30, shape=lambda i: "due")
    library(5, shape=lambda i: "new")
    got = get(api, "/recall/queue/", source="catchup", limit=50).json_body["cards"]
    assert len(got) == 20 and all(c["state"] == 2 for c in got)


def test_the_interval_previews_equal_what_the_review_then_schedules(api):
    set_settings(new_per_day=0)
    (c,) = library(1, shape=lambda i: "due")
    res = get(api, "/recall/queue/").json_body
    card = res["cards"][0]
    now = res["server_time"]
    out = api.post(
        "/recall/reviews/", {"id": str(uuid.uuid4()), "card_id": card["id"], "rating": 3, "reviewed_at": now}
    ).json_body["card"]
    row = RecallCard.objects.get(pk=c.pk)
    scheduled = (row.due_at - row.last_review_at).total_seconds() / 86400
    assert abs(scheduled - card["preview_days"]["3"]) < 1e-5 and out["due_at"]


def test_the_source_of_a_selection_card_travels_with_it(api):
    made = api.post(
        "/recall/cards/from-selection/",
        {
            "client_id": str(uuid.uuid4()),
            "origin": "note_highlight",
            "selection_text": "Input tax credit is blocked for motor cars.",
            "source": {"module": "notes", "object_id": str(uuid.uuid4()), "locator": {}},
        },
    )
    assert made.status_code == 201, made.json_body
    RecallCard.objects.filter(user_id=ME).update(state=0)
    got = get(api, "/recall/queue/").json_body["cards"][0]
    assert got["source"]["module"] == "notes" and "new" in got["badges"]


def test_a_card_flagged_for_recheck_and_a_tricky_card_carry_badges(api):
    set_settings(new_per_day=0)
    a, b = library(2, shape=lambda i: "due")
    RecallCard.objects.filter(pk=a.pk).update(needs_recheck=True, recheck_reason="amendment")
    RecallCard.objects.filter(pk=b.pk).update(leech=True)
    badges = {c["id"]: c["badges"] for c in get(api, "/recall/queue/").json_body["cards"]}
    assert badges[str(a.id)] == ["amendment"] and badges[str(b.id)] == ["tricky"]


# ------------------------------------------------------------------------------------------------------ forgotten
def test_forgotten_ranks_by_lapses_agains_and_importance_and_ignores_undone_reviews(api):
    now = timezone.now()
    low, high = library(2, shape=lambda i: "due", importance=0)[0], library(1, shape=lambda i: "due", importance=2)[0]
    quiet = library(1, shape=lambda i: "due")[0]

    def lapse(card, minutes_ago):
        card.refresh_from_db()
        reviews.submit_review(ME, ev(card, 1, now - timedelta(minutes=minutes_ago)), now=now)

    for c in (low, high):
        lapse(c, 30)
    lapse(low, 20)
    reviews.submit_review(ME, ev(quiet, 3, now - timedelta(minutes=10)), now=now)
    rows = api.get("/recall/forgotten/").json_body["items"]
    assert [r["card_id"] for r in rows] == [str(high.id), str(low.id)]
    assert (
        rows[0]["score"] > rows[1]["score"]
        and rows[0]["importance"] == 2
        and rows[0]["front_md"].startswith("Question")
    )
    assert rows[1]["agains"] == 2 and "last_again_at" in rows[1]
    only = api.get(f"/recall/forgotten/?subject_key={high.subject_key}").json_body["items"]
    assert all(r["subject_key"] == high.subject_key for r in only)
    # undoing the only lapse of `high` removes it from the list
    from modules.recall.models import RecallReviewLog

    row = RecallReviewLog.objects.filter(user_id=ME, card_id=high.id, rating=1).first()
    reviews.undo_review(ME, uuid.uuid4(), row.id, now=now)
    assert str(high.id) not in {r["card_id"] for r in api.get("/recall/forgotten/").json_body["items"]}
    assert quiet.id not in {uuid.UUID(r["card_id"]) for r in api.get("/recall/forgotten/").json_body["items"]}


def test_today_shows_the_top_five_forgotten(api):
    now = timezone.now()
    for c in library(7, shape=lambda i: "due"):
        reviews.submit_review(ME, ev(c, 1, now - timedelta(minutes=5)), now=now)
    assert len(api.get("/recall/today/").json_body["forgotten"]) == 5


# ------------------------------------------------------------------------------------------------------ pack
def test_the_pack_carries_content_memory_weights_settings_and_counters(api):
    library(40, shape=lambda i: ("due", "new", "later", "learning", "learning_tomorrow")[i % 5])
    done_today(new=2, reviews=3)
    pack = api.get("/recall/pack/").json_body
    assert len(pack["weights"]) == 21 and pack["scheduler_version"] == "fsrs-6.0" and pack["pack_id"]
    assert pack["expires_at"] > pack["generated_at"] and pack["settings"]["new_per_day"] == 10
    assert pack["counters"]["new_done_today"] == 2 and pack["counters"]["reviews_done_today"] == 3
    states = [c["state"] for c in pack["cards"]]
    assert states.count(1) == 16  # 8 learning now and 8 learning tomorrow
    card = pack["cards"][0]
    assert set(card) >= {
        "stability",
        "difficulty",
        "due_scheduled_at",
        "last_review_at",
        "reps",
        "lapses",
        "step",
        "front_md",
        "back_md",
        "previews",
    }
    assert states.count(0) == 8  # the allowance (10) less the 2 already done


def test_the_pack_is_cut_to_the_plan_size_and_the_environment_cap(api, settings):
    library(30, shape=lambda i: "due")
    RecallQuotaPlan.objects.filter(pk="free").update(pack_size=12)
    assert len(api.get("/recall/pack/").json_body["cards"]) == 12
    assert len(api.get("/recall/pack/?limit=5").json_body["cards"]) == 5
    assert len(api.get("/recall/pack/?limit=900").json_body["cards"]) == 12
    settings.RECALL_PACK_MAX = 7
    assert len(api.get("/recall/pack/").json_body["cards"]) == 7


def test_the_pack_has_no_new_cards_during_catchup(api):
    set_settings(reviews_per_day=20)
    library(45, shape=lambda i: "due")
    library(5, shape=lambda i: "new")
    cards = api.get("/recall/pack/").json_body["cards"]
    assert len(cards) == 45 and all(c["state"] == 2 for c in cards)


def test_a_student_only_ever_receives_her_own_cards(api, other_api):
    library(6, shape=lambda i: "due", user=uuid.uuid4())
    assert api.get("/recall/pack/").json_body["cards"] == [] and get(api, "/recall/queue/").json_body["cards"] == []
    mine = library(2, shape=lambda i: "due")
    assert {c["id"] for c in other_api.get("/recall/pack/").json_body["cards"]} & {str(c.id) for c in mine} == set()


# ------------------------------------------------------------------------------------------------------ no writes, few queries
READ_PATHS = [
    "/recall/today/",
    "/recall/queue/",
    "/recall/queue/?source=catchup",
    "/recall/queue/?source=forgotten",
    "/recall/queue/?source=review_ahead",
    "/recall/pack/",
    "/recall/forgotten/",
    "/recall/settings/",
    "/recall/stats/summary/",
    "/recall/stats/retention/",
    "/recall/stats/forecast/",
    "/recall/stats/chapters/",
]


@pytest.mark.parametrize("path", READ_PATHS)
def test_a_get_never_writes(api, path):
    library(30)
    api.get("/recall/today/")  # warm anything lazy
    with CaptureQueriesContext(connection) as ctx:
        assert api.get(path).status_code == 200
    writes = [q["sql"][:80] for q in ctx.captured_queries if q["sql"].lstrip().upper().startswith(WRITES)]
    assert writes == []
    assert not RecallSettings.objects.filter(user_id=ME).exists()


@pytest.mark.parametrize("path", READ_PATHS)
def test_the_number_of_queries_does_not_grow_with_the_library(api, path):
    def count(n):
        RecallCard.objects.filter(user_id=ME).delete()
        library(n, shape=lambda i: ("due", "new", "later", "learning")[i % 4], chapter_id=uuid.uuid4())
        api.get(path)
        with CaptureQueriesContext(connection) as ctx:
            assert api.get(path).status_code == 200
        return len(ctx.captured_queries)

    small, large = count(40), count(5000)
    assert small == large and large <= 20, (path, small, large)
