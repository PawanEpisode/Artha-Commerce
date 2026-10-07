"""GET thought/today/ and the service behind it: one message per student per local day, no repeat within 60 days."""

from datetime import UTC, date, datetime, timedelta

import pytest

from modules.coverage.models import Enrollment
from modules.notifications.domain.enums import MessageStatus
from modules.notifications.models import MessageShown, Preference
from modules.notifications.selectors import motivation as motivation_selectors
from modules.notifications.services import settings as settings_service
from modules.notifications.services import thought as thought_service
from modules.notifications.tests.motivation_helpers import OTHER, USER, library, message

pytestmark = pytest.mark.django_db
URL = "/api/v1/notifications/thought/today/"
TODAY = date(2026, 10, 7)


def thought(client):
    r = client.get(URL)
    assert r.status_code == 200
    return r.json()["thought"]


# --- first open and reload --------------------------------------------------------------------------------------------


def test_requires_sign_in(client):
    assert client.get(URL).status_code in (401, 403)


def test_the_first_open_of_the_day_picks_one_published_message_and_records_it(auth_client, clock):
    only = message("Open the book for ten minutes.", attribution="Artha")
    assert thought(auth_client) == {
        "id": str(MessageShown.objects.get().id),
        "body": "Open the book for ten minutes.",
        "attribution": "Artha",
        "shown_on": "2026-10-07",
    }
    row = MessageShown.objects.get()
    assert (row.user_id, row.message_id, row.shown_on, row.channel) == (USER, only.id, TODAY, "inapp")


def test_a_reload_that_day_shows_the_same_message_even_when_better_ones_were_published(auth_client, clock):
    library(5)
    first = thought(auth_client)
    message("Published after the first open.")
    clock.advance(hours=9)  # still the same local day
    assert thought(auth_client) == first
    assert MessageShown.objects.count() == 1


def test_the_next_local_day_gets_a_new_message(auth_client, clock):
    library(5)
    day_one = thought(auth_client)
    clock.advance(days=1)
    day_two = thought(auth_client)
    assert day_two["shown_on"] == "2026-10-08" and day_two["id"] != day_one["id"]
    assert MessageShown.objects.count() == 2


def test_students_do_not_share_a_day(client, make_token, clock):
    library(5)
    mine = client.get(URL, HTTP_AUTHORIZATION=f"Bearer {make_token()}").json()["thought"]
    theirs = client.get(URL, HTTP_AUTHORIZATION=f"Bearer {make_token(sub=str(OTHER))}").json()["thought"]
    assert mine["id"] != theirs["id"]
    assert set(MessageShown.objects.values_list("user_id", flat=True)) == {USER, OTHER}


# --- the student's own local day --------------------------------------------------------------------------------------


def test_the_day_follows_the_time_zone_in_settings(auth_client, clock):
    library(5)
    clock.set(datetime(2026, 10, 7, 19, 0, tzinfo=UTC))  # 00:30 on the 8th in India, 15:00 on the 7th in New York
    assert thought(auth_client)["shown_on"] == "2026-10-08"
    MessageShown.objects.all().delete()
    settings_service.update_settings(USER, {"timezone": "America/New_York"}, now=clock.now)
    assert thought(auth_client)["shown_on"] == "2026-10-07"


def test_midnight_in_the_students_zone_starts_a_new_day_across_a_clock_change(auth_client, clock):
    library(5)
    settings_service.update_settings(USER, {"timezone": "America/New_York"}, now=clock.now)
    clock.set(datetime(2026, 11, 1, 3, 30, tzinfo=UTC))  # 23:30 on 31 October (EDT)
    before = thought(auth_client)
    clock.set(datetime(2026, 11, 1, 4, 30, tzinfo=UTC))  # 00:30 on 1 November, still EDT: clocks go back at 02:00
    after = thought(auth_client)
    clock.set(datetime(2026, 11, 2, 4, 59, tzinfo=UTC))  # 23:59 on 1 November (EST, a 25 hour day)
    late = thought(auth_client)
    assert (before["shown_on"], after["shown_on"], late["shown_on"]) == ("2026-10-31", "2026-11-01", "2026-11-01")
    assert after["id"] == late["id"]


# --- 60 days, empty and exhausted libraries ---------------------------------------------------------------------------


def test_nothing_repeats_for_sixty_days_and_nothing_is_shown_rather_than_a_repeat(auth_client, clock):
    lines = {m.body: m for m in library(3)}
    shown = []
    for _ in range(3):
        shown.append(thought(auth_client)["body"])
        clock.advance(days=1)
    assert sorted(shown) == sorted(lines)  # three days, three different lines

    for day in (3, 10, 30, 59):  # every line was seen in the last 60 days
        clock.set(datetime(2026, 10, 7, 6, 30, tzinfo=UTC) + timedelta(days=day))
        assert thought(auth_client) is None
    assert MessageShown.objects.count() == 3  # an unavailable day records nothing

    clock.set(datetime(2026, 10, 7, 6, 30, tzinfo=UTC) + timedelta(days=60))
    assert thought(auth_client)["body"] == shown[0]  # exactly sixty days later the first line may come back
    clock.advance(days=1)
    assert thought(auth_client)["body"] == shown[1]


def test_sixty_days_in_a_row_use_sixty_different_lines(auth_client, clock):
    library(60)
    bodies = []
    for _ in range(60):
        bodies.append(thought(auth_client)["body"])
        clock.advance(days=1)
    assert len(set(bodies)) == 60


def test_an_empty_library_shows_no_card(auth_client, clock):
    assert thought(auth_client) is None
    assert not MessageShown.objects.exists()


def test_drafts_retired_lines_and_other_languages_are_never_shown(auth_client, clock):
    message("A draft.", status=MessageStatus.DRAFT)
    message("Retired.", status=MessageStatus.RETIRED)
    message("Un mensaje.", locale="es")
    assert thought(auth_client) is None
    message("The one published line.")
    assert thought(auth_client)["body"] == "The one published line."


# --- who a line is for ------------------------------------------------------------------------------------------------


def enroll(scheme, user=USER, exam_date=None):
    return Enrollment.objects.create(user_id=user, scheme=scheme, level=scheme.level, exam_date=exam_date)


def test_a_student_gets_general_lines_and_those_for_their_own_course_and_level(auth_client, clock, scheme):
    from modules.syllabus.models import Course, Level

    general = message("General.")
    own_level = message("For CA Intermediate.", course=scheme.level.course, level=scheme.level)
    own_course = message("For CA.", course=scheme.level.course)
    other_course = message("For CMA.", course=Course.objects.get(code="cma"))
    final = Level.objects.get(course=scheme.level.course, code="final")
    other_level = message("For CA Final.", course=scheme.level.course, level=final)
    enroll(scheme)
    ctx = motivation_selectors.student_context(USER, TODAY)
    ids = {c.id for c in motivation_selectors.candidates(ctx)}
    assert ids == {general.id, own_level.id, own_course.id}
    assert other_course.id not in ids and other_level.id not in ids


def test_a_student_without_a_course_only_gets_general_lines(auth_client, clock, scheme):
    message("For CA Intermediate.", course=scheme.level.course, level=scheme.level)
    assert thought(auth_client) is None
    general = message("General.")
    assert thought(auth_client)["body"] == general.body


def test_the_exam_phase_prefers_lines_written_for_it(auth_client, clock, scheme):
    enroll(scheme, exam_date=TODAY + timedelta(days=3))  # the final week
    message("An ordinary day.")
    week = message("Last week, breathe.", phase="final_week")
    message("Exam day, go.", phase="exam_day")
    message("Plenty of time.", phase="far")
    assert thought(auth_client)["body"] == week.body


def test_the_students_tone_is_preferred(auth_client, clock):
    message("Calm one.", tone="calm")
    driven = message("Driven one.", tone="driven")
    settings_service.update_settings(USER, {"nudge_tone": "driven"}, now=clock.now)
    assert thought(auth_client)["body"] == driven.body


# --- switches -----------------------------------------------------------------------------------------------------


def test_switching_the_daily_thought_off_for_the_app_hides_the_card_and_records_nothing(auth_client, clock):
    library(3)
    Preference.objects.create(user_id=USER, category="motivation", channel="inbox", enabled=False)
    assert thought(auth_client) is None
    assert not MessageShown.objects.exists()


def test_switching_only_the_push_off_keeps_the_card(auth_client, clock):
    library(3)
    Preference.objects.create(user_id=USER, category="motivation", channel="push", enabled=False)
    assert thought(auth_client) is not None


def test_it_answers_403_when_notifications_are_off(auth_client, clock, settings, monkeypatch):
    library(3)
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    r = auth_client.get(URL)
    assert r.status_code == 403 and r.json()["error"]["code"] == "notifications_disabled"
    assert not MessageShown.objects.exists()


def test_it_answers_403_when_the_environment_switch_is_off(auth_client, clock, settings):
    library(3)
    settings.NOTIFICATIONS_ENABLED = False
    assert auth_client.get(URL).status_code == 403


def test_reads_are_throttled_like_the_rest_of_the_module(auth_client, clock):
    library(3)
    codes = [auth_client.get(URL).status_code for _ in range(121)]
    assert codes[:120] == [200] * 120 and codes[120] == 429


def test_only_get_is_allowed(auth_client, clock):
    assert auth_client.post(URL, {}, content_type="application/json").status_code == 405


# --- sharing the day with the nudge, and races -----------------------------------------------------------------------


def test_a_message_the_nudge_already_used_today_is_the_one_the_card_shows(auth_client, clock):
    library(5)
    reservation = thought_service.reserve_message(USER, local_date=TODAY, tone="calm", channel="push", now=clock.now)
    card = thought(auth_client)
    assert card["body"] == reservation.message.body
    assert MessageShown.objects.get().channel == "push"  # the first use of the day keeps the day


def test_a_lost_race_returns_the_winners_message_and_writes_nothing_more(clock, monkeypatch):
    library(5)
    winner = thought_service.reserve_message(USER, local_date=TODAY, tone="calm", channel="inapp", now=clock.now)
    real = motivation_selectors.shown_on
    calls = iter([None])  # the loser looked before the winner wrote
    monkeypatch.setattr(motivation_selectors, "shown_on", lambda *a: next(calls, None) or real(*a))
    loser = thought_service.reserve_message(USER, local_date=TODAY, tone="calm", channel="push", now=clock.now)
    assert loser.created is False and loser.shown.id == winner.shown.id
    assert MessageShown.objects.count() == 1


def test_an_unexpected_database_error_is_not_swallowed_as_a_race(clock, monkeypatch):
    from django.db import IntegrityError

    library(2)

    def boom(**kwargs):
        raise IntegrityError("something else")

    monkeypatch.setattr(MessageShown.objects, "create", boom)
    with pytest.raises(IntegrityError):
        thought_service.reserve_message(USER, local_date=TODAY, tone="calm", channel="inapp", now=clock.now)


def test_a_line_retired_after_it_was_shown_still_shows_for_the_rest_of_that_day(auth_client, clock):
    only = message("Shown then retired.")
    assert thought(auth_client)["body"] == only.body
    only.status = MessageStatus.RETIRED
    only.save()
    assert thought(auth_client)["body"] == "Shown then retired."  # history keeps its text
    clock.advance(days=1)
    assert thought(auth_client) is None
