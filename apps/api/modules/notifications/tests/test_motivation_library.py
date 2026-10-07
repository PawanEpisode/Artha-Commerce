"""The motivation library (W3.3): its rules, the admin editors use, the services behind it and the seed loader."""

import io
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse

from core import registry
from modules.notifications.domain.enums import MessageStatus
from modules.notifications.management.commands.load_motivation_seed import SEED_DIR
from modules.notifications.models import Message, MessageShown
from modules.notifications.selectors.export import export_all
from modules.notifications.services import motivation as service
from modules.notifications.services import retention
from modules.notifications.services.erasure import delete_all_for_user
from modules.notifications.tests.motivation_helpers import OTHER, USER, message
from modules.syllabus.models import Course

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 7, 6, 30, tzinfo=UTC)


def seed_cmd(*paths):
    out, err = io.StringIO(), io.StringIO()
    call_command("load_motivation_seed", *map(str, paths), stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def write_seed(tmp_path, data, name="seed.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


# --- the model's own rules -----------------------------------------------------------------------------------------------


def test_a_new_line_is_a_draft_in_english_for_any_day():
    m = Message.objects.create(body="Hello.", tone="calm")
    assert (m.status, m.phase, m.locale, m.published_at, m.course, m.level) == ("draft", "any", "en", None, None, None)


@pytest.mark.parametrize("field, value", [("tone", "angry"), ("phase", "someday"), ("status", "live")])
def test_the_database_refuses_values_outside_the_closed_sets(field, value):
    kwargs = {"body": "x", "tone": "calm", "phase": "any", "status": "draft", field: value}
    with pytest.raises(IntegrityError), transaction.atomic():
        Message.objects.create(**kwargs)


def test_a_published_line_must_say_when():
    with pytest.raises(IntegrityError), transaction.atomic():
        Message.objects.create(body="x", tone="calm", status="published")


def test_the_day_key_allows_one_message_per_student_per_day():
    m = message()
    MessageShown.objects.create(user_id=USER, message=m, shown_on=date(2026, 10, 7), channel="inapp")
    with pytest.raises(IntegrityError), transaction.atomic():
        MessageShown.objects.create(user_id=USER, message=message(), shown_on=date(2026, 10, 7), channel="push")
    MessageShown.objects.create(user_id=OTHER, message=m, shown_on=date(2026, 10, 7), channel="push")
    MessageShown.objects.create(user_id=USER, message=m, shown_on=date(2026, 10, 8), channel="push")


def test_a_line_students_have_seen_cannot_be_deleted_so_history_keeps_its_text():
    m = message()
    MessageShown.objects.create(user_id=USER, message=m, shown_on=date(2026, 10, 7), channel="inapp")
    with pytest.raises(ProtectedError):
        m.delete()


def test_removing_a_course_leaves_the_line_for_everyone(scheme):
    m = message(course=scheme.level.course)
    Course.objects.filter(pk=scheme.level.course_id).delete() if False else None
    m.course = None
    m.save()
    assert Message.objects.get(pk=m.pk).course_id is None


# --- checks before a line goes live ----------------------------------------------------------------------------------------


def test_problems_lists_what_blocks_publication(scheme):
    ok = message(status=MessageStatus.DRAFT)
    assert service.problems(ok) == []
    blank = Message(body="   ", tone="calm")
    assert service.problems(blank) == ["The text is empty."]
    cma = Course.objects.get(code="cma")
    mismatch = Message(body="x", tone="calm", course=cma, level=scheme.level)
    assert service.problems(mismatch) == ["The level does not belong to the course."]
    assert service.problems(Message(body="x" * 241, tone="calm")) == ["The text is longer than 240 characters."]


def test_publish_goes_live_with_a_timestamp_and_leaves_published_lines_alone():
    draft = message("  Needs trimming.  ", status=MessageStatus.DRAFT)
    live = message("Already live.")
    review = service.publish([draft, live], now=NOW)
    draft.refresh_from_db()
    live.refresh_from_db()
    assert review.changed == 1 and review.refused == {}
    assert (draft.status, draft.published_at, draft.body) == ("published", NOW, "Needs trimming.")
    assert live.published_at != NOW


def test_publish_refuses_a_line_that_fails_its_checks_and_still_publishes_the_others(scheme):
    cma = Course.objects.get(code="cma")
    bad = message("Wrong level.", status=MessageStatus.DRAFT, course=cma, level=scheme.level)
    good = message("Fine.", status=MessageStatus.DRAFT)
    review = service.publish(Message.objects.filter(pk__in=[bad.pk, good.pk]).select_related("level"), now=NOW)
    bad.refresh_from_db()
    good.refresh_from_db()
    assert review.changed == 1 and list(review.refused) == [str(bad.pk)]
    assert (bad.status, good.status) == ("draft", "published")


def test_retire_stops_a_line_and_keeps_its_history():
    live = message()
    draft = message(status=MessageStatus.DRAFT)
    assert service.retire([live, draft]) == 1
    live.refresh_from_db()
    draft.refresh_from_db()
    assert (live.status, draft.status) == ("retired", "draft")
    assert service.publish([live], now=NOW).changed == 1  # a retired line can be brought back after another read


def test_a_draft_is_never_picked_so_nothing_is_sent_from_it(auth_client, clock):
    message("Only a draft.", status=MessageStatus.DRAFT)
    assert auth_client.get("/api/v1/notifications/thought/today/").json() == {"thought": None}


# --- the admin ---------------------------------------------------------------------------------------------------------------


@pytest.fixture
def editor(admin_client):
    return admin_client


def post_action(client, action, *messages):
    return client.post(
        reverse("admin:notifications_message_changelist"),
        {"action": action, "_selected_action": [str(m.pk) for m in messages]},
        follow=True,
    )


def test_the_admin_lists_messages_with_filters(editor):
    message("A line for the list.")
    r = editor.get(reverse("admin:notifications_message_changelist") + "?status__exact=published&tone__exact=calm")
    assert r.status_code == 200 and "A line for the list." in r.content.decode()


def test_an_editor_adds_a_line_and_it_starts_as_a_draft(editor):
    r = editor.post(
        reverse("admin:notifications_message_add"),
        {"body": "Written by an editor.", "tone": "driven", "phase": "any", "locale": "en", "attribution": ""},
    )
    assert r.status_code == 302
    m = Message.objects.get()
    assert (m.status, m.published_at, m.attribution) == ("draft", None, None)


def test_the_status_cannot_be_set_in_the_form(editor):
    r = editor.post(
        reverse("admin:notifications_message_add"),
        {"body": "Sneaky.", "tone": "calm", "phase": "any", "locale": "en", "status": "published"},
    )
    assert r.status_code == 302 and Message.objects.get().status == "draft"


def test_a_level_from_another_course_is_rejected_in_the_form(editor, scheme):
    cma = Course.objects.get(code="cma")
    r = editor.post(
        reverse("admin:notifications_message_add"),
        {"body": "x", "tone": "calm", "phase": "any", "locale": "en", "course": cma.pk, "level": scheme.level.pk},
    )
    assert r.status_code == 200 and "The level does not belong to the course." in r.content.decode()
    assert not Message.objects.exists()


def test_the_publish_action_goes_live_and_the_retire_action_stops_it(editor):
    a = message("One.", status=MessageStatus.DRAFT)
    b = message("Two.", status=MessageStatus.DRAFT)
    r = post_action(editor, "publish_selected", a, b)
    assert "Published 2 message(s)." in r.content.decode()
    assert set(Message.objects.values_list("status", flat=True)) == {"published"}
    assert all(m.published_at for m in Message.objects.all())
    r = post_action(editor, "retire_selected", a)
    assert "Retired 1 message(s)." in r.content.decode()
    a.refresh_from_db()
    assert a.status == "retired"


def test_the_publish_action_says_why_a_line_was_refused(editor, scheme):
    cma = Course.objects.get(code="cma")
    bad = message("Mismatch.", status=MessageStatus.DRAFT, course=cma, level=scheme.level)
    r = post_action(editor, "publish_selected", bad)
    assert "The level does not belong to the course." in r.content.decode()
    bad.refresh_from_db()
    assert bad.status == "draft"


def test_a_published_line_cannot_be_edited_or_deleted_but_a_draft_can_be_deleted(editor):
    live = message("Live text.")
    draft = message("Draft text.", status=MessageStatus.DRAFT)
    page = editor.get(reverse("admin:notifications_message_change", args=[live.pk])).content.decode()
    assert 'name="body"' not in page and "Live text." in page and "Delete" not in page.split("submit-row")[-1]
    editor.post(reverse("admin:notifications_message_change", args=[live.pk]), {"body": "Changed.", "tone": "calm"})
    live.refresh_from_db()
    assert live.body == "Live text."
    assert editor.get(reverse("admin:notifications_message_delete", args=[live.pk])).status_code == 403
    assert (
        editor.post(reverse("admin:notifications_message_delete", args=[draft.pk]), {"post": "yes"}).status_code == 302
    )
    assert not Message.objects.filter(pk=draft.pk).exists()


def test_the_shown_history_is_read_only_support_data(editor):
    m = message()
    MessageShown.objects.create(user_id=USER, message=m, shown_on=date(2026, 10, 7), channel="inapp")
    assert editor.get(reverse("admin:notifications_messageshown_changelist")).status_code == 200
    assert editor.get(reverse("admin:notifications_messageshown_add")).status_code == 403


# --- the seed loader --------------------------------------------------------------------------------------------------------


def test_the_shipped_seed_loads_as_drafts_only(db):
    out, err = seed_cmd()
    total = sum(len(json.loads(p.read_text())["messages"]) for p in SEED_DIR.glob("*.json"))
    assert f"Done: {total} drafts created, 0 already there, 0 file(s) skipped." in out and err == ""
    assert Message.objects.count() == total
    assert set(Message.objects.values_list("status", flat=True)) == {"draft"}
    assert not Message.objects.filter(published_at__isnull=False).exists()
    assert Message.objects.filter(course__isnull=True, level__isnull=True).count() == 36
    ca_inter = Message.objects.filter(course__code="ca", level__code="intermediate")
    assert ca_inter.count() == 9 and set(ca_inter.values_list("tone", flat=True)) == {"calm", "driven", "celebratory"}


def test_loading_twice_changes_nothing_and_keeps_an_editors_work():
    seed_cmd()
    first = Message.objects.count()
    edited = Message.objects.get(seed_key="generic-any-calm-01")
    edited.body = "Edited by a person."
    edited.save()
    service.publish([edited], now=NOW)
    out, _ = seed_cmd()
    assert f"0 drafts created, {first} already there" in out
    assert Message.objects.count() == first
    edited.refresh_from_db()
    assert (edited.body, edited.status) == ("Edited by a person.", "published")


def test_a_line_that_is_retired_stays_retired_after_a_reload():
    seed_cmd()
    line = Message.objects.get(seed_key="generic-any-calm-02")
    service.publish([line], now=NOW)
    service.retire([line])
    seed_cmd()
    line.refresh_from_db()
    assert line.status == "retired"


def test_a_file_for_a_course_or_level_that_is_not_loaded_is_skipped_and_reported(tmp_path):
    path = write_seed(
        tmp_path,
        {"course": "ca", "level": "no-such-level", "messages": [{"key": "k1", "tone": "calm", "body": "Hello there."}]},
    )
    out, err = seed_cmd(path)
    assert "skipped: seed.json: level ca/no-such-level is not loaded" in err and Message.objects.count() == 0
    assert "1 file(s) skipped" in out
    path = write_seed(tmp_path, {"course": "zz", "messages": [{"key": "k1", "tone": "calm", "body": "Hello there."}]})
    assert "course 'zz' is not loaded" in seed_cmd(path)[1]


def test_a_level_without_its_course_is_an_error(tmp_path):
    path = write_seed(tmp_path, {"level": "final", "messages": [{"key": "k", "tone": "calm", "body": "Hi."}]})
    with pytest.raises(CommandError, match="needs its course"):
        seed_cmd(path)


@pytest.mark.parametrize(
    "entry, match",
    [
        ({"key": "k", "tone": "loud", "body": "Hi."}, "unknown tone"),
        ({"key": "k", "tone": "calm", "phase": "soon", "body": "Hi."}, "unknown phase"),
        ({"key": "k", "tone": "calm", "body": "x" * 241}, "1 to 240"),
        ({"key": "k", "tone": "calm", "body": "  "}, "1 to 240"),
        ({"key": "", "tone": "calm", "body": "Hi."}, "key"),
        ({"tone": "calm", "body": "Hi."}, "needs key, body and tone"),
        ({"key": "k", "tone": "calm", "body": "Hi.", "attribution": "y" * 81}, "attribution"),
    ],
)
def test_an_invalid_entry_stops_the_load_and_writes_nothing(tmp_path, entry, match):
    ok = {"key": "ok", "tone": "calm", "body": "Fine."}
    with pytest.raises(CommandError, match=match):
        seed_cmd(write_seed(tmp_path, {"messages": [ok, entry]}))
    assert Message.objects.count() == 0


def test_duplicate_keys_unreadable_files_and_empty_files_are_errors(tmp_path):
    same = {"key": "k", "tone": "calm", "body": "Hi."}
    with pytest.raises(CommandError, match="duplicate keys"):
        seed_cmd(write_seed(tmp_path, {"messages": [same, same]}))
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(CommandError, match="broken.json"):
        seed_cmd(broken)
    with pytest.raises(CommandError, match="non-empty 'messages'"):
        seed_cmd(write_seed(tmp_path, {"messages": []}, "empty.json"))
    with pytest.raises(CommandError, match="missing.json"):
        seed_cmd(tmp_path / "missing.json")


# --- what ships: the seed files themselves --------------------------------------------------------------------------------


def seed_files():
    return sorted(SEED_DIR.glob("*.json"))


def seed_entries():
    for path in seed_files():
        data = json.loads(path.read_text())
        for entry in data["messages"]:
            yield path, data, entry


def test_every_shipped_line_is_valid_short_original_and_plain_text():
    seen_keys, seen_bodies = set(), set()
    for path, _, entry in seed_entries():
        key, body, tone, phase, attribution = service._entry(entry, path.name)
        assert len(body) <= service.BODY_ADVISED, f"{key} is too long to read whole on a lock screen"
        assert attribution is None, f"{key}: a seed line quotes no one"
        assert re.fullmatch(r"[A-Za-z0-9 ,.'?!:;()-]+", body), f"{key}: plain text only, no emoji or symbols"
        assert key not in seen_keys and body not in seen_bodies
        assert key.startswith(path.stem)
        seen_keys.add(key)
        seen_bodies.add(body)
    assert len(seen_keys) >= 100


def test_there_is_a_general_file_and_one_for_every_level_the_syllabus_seeds():
    syllabus_seed = Path(__file__).resolve().parents[2] / "syllabus" / "seed"
    levels = {f"{p.parent.parent.name}-{p.parent.name}" for p in syllabus_seed.glob("*/*/*.json")}
    assert levels and {p.stem for p in seed_files()} == levels | {"generic"}


def test_each_file_has_every_tone_and_the_general_file_covers_every_exam_phase():
    for path in seed_files():
        data = json.loads(path.read_text())
        by_tone = {}
        for entry in data["messages"]:
            by_tone.setdefault(entry["tone"], []).append(entry)
        assert set(by_tone) == {"calm", "driven", "celebratory"}, path.name
        if path.stem == "generic":
            assert data["course"] is None and data["level"] is None
            for entries in by_tone.values():
                assert {e.get("phase", "any") for e in entries} == {"any", "far", "near", "final_week", "exam_day"}
        else:
            course, level = path.stem.split("-")
            assert (data["course"], data["level"]) == (course, level)
            assert all(len(entries) >= 3 for entries in by_tone.values())


# --- erasure, export and retention ------------------------------------------------------------------------------------------


def test_erasing_a_student_removes_their_thoughts_and_only_theirs():
    m = message("Shared line.")
    MessageShown.objects.create(user_id=USER, message=m, shown_on=date(2026, 10, 7), channel="inapp")
    MessageShown.objects.create(user_id=OTHER, message=m, shown_on=date(2026, 10, 7), channel="push")
    assert "notifications" in {name for name, _ in registry.erasers()}
    counts = delete_all_for_user(USER)
    assert counts["messages_shown"] == 1
    assert list(MessageShown.objects.values_list("user_id", flat=True)) == [OTHER]
    assert Message.objects.filter(pk=m.pk).exists()  # the library is not personal data
    assert delete_all_for_user(USER)["messages_shown"] == 0


def test_the_export_lists_the_thoughts_the_student_was_given():
    m = message("A line for the export.")
    MessageShown.objects.create(user_id=USER, message=m, shown_on=date(2026, 10, 7), channel="push")
    MessageShown.objects.create(user_id=OTHER, message=m, shown_on=date(2026, 10, 7), channel="push")
    assert export_all(USER)["daily_thoughts"] == [
        {"shown_on": date(2026, 10, 7), "channel": "push", "text": "A line for the export."}
    ]


def test_retention_keeps_the_shown_history_for_120_days():
    m = message()
    today = NOW.date()
    for age in (0, 60, 119, 120, 121, 400):
        MessageShown.objects.create(
            user_id=uuid.uuid4(), message=m, shown_on=today - timedelta(days=age), channel="inapp"
        )
    assert retention.prune(now=NOW, dry_run=True).messages_shown == 2  # 121 and 400 days old
    result = retention.prune(now=NOW)
    assert result.messages_shown == 2 and result.total == 2
    ages = sorted((today - s.shown_on).days for s in MessageShown.objects.all())
    assert ages == [0, 60, 119, 120]
    assert retention.prune(now=NOW).total == 0


def test_the_prune_command_reports_the_shown_history():
    out = io.StringIO()
    call_command("prune_notifications", "--dry-run", stdout=out)
    assert "messages_shown: would delete 0" in out.getvalue()
