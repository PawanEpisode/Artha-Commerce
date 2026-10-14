"""The database enforces the ERD's constraints (ERD 2): what the services must never be able to break."""

import uuid
from datetime import date, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.today.models import DayPlan, ProviderConfig, Task, TaskEvidence, TodaySettings

pytestmark = pytest.mark.django_db

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
DAY = date(2026, 10, 14)


def plan(**over):
    fields = dict(user_id=USER, local_date=DAY, tz="Asia/Kolkata")
    fields.update(over)
    return DayPlan.objects.create(**fields)


def task(p, **over):
    fields = dict(
        user_id=USER,
        plan=p,
        local_date=p.local_date,
        origin="provider",
        provider="coverage.revision",
        kind="revise_chapter",
        slot="revision",
        dedupe_key="revise:abc:3",
        title="Revise GST: ITC",
        est_minutes=20,
    )
    fields.update(over)
    return Task.objects.create(**fields)


def rejected(make):
    with pytest.raises(IntegrityError), transaction.atomic():
        make()


# ---- plan -------------------------------------------------------------------------------------------------------------------


def test_one_plan_per_student_per_local_day():
    plan()
    rejected(plan)
    plan(local_date=DAY + timedelta(days=1))
    plan(user_id=uuid.uuid4())


def test_plan_checks():
    rejected(lambda: plan(local_date=DAY + timedelta(days=2), status="open"))
    rejected(lambda: plan(local_date=DAY + timedelta(days=2), phase="panic"))
    rejected(lambda: plan(local_date=DAY + timedelta(days=2), budget_minutes=5))
    rejected(lambda: plan(local_date=DAY + timedelta(days=2), budget_minutes=301))
    rejected(lambda: plan(local_date=DAY + timedelta(days=2), budget_source="vibes"))
    rejected(lambda: plan(local_date=DAY + timedelta(days=2), generation_no=0))  # only a draft may be generation 0
    plan(local_date=DAY + timedelta(days=2), status="draft", generation_no=0)


def test_selection_log_is_kept_small():
    rejected(lambda: plan(selection_log={"x": "y" * 5000}))
    plan(local_date=DAY + timedelta(days=1), selection_log={"v": 1, "candidates": 3})


# ---- task -------------------------------------------------------------------------------------------------------------------


def test_a_provider_task_needs_a_provider_and_a_key_but_an_own_task_needs_neither():
    p = plan()
    rejected(lambda: task(p, provider=""))
    rejected(lambda: task(p, dedupe_key=""))
    task(p, origin="user", provider="", dedupe_key="user:1", slot="custom", kind="custom")


def test_one_live_row_per_unit_of_work_per_day():
    p = plan()
    task(p)
    rejected(lambda: task(p))  # the same key again, even if the first was skipped or done
    second = task(p, dedupe_key="revise:abc:4")
    second.state, second.end_reason = "expired", "regenerated"
    second.save()
    task(p, dedupe_key="revise:abc:4")  # an expired row frees the key (regeneration)
    q = plan(local_date=DAY + timedelta(days=1))
    task(q)  # the same key on another day is a different row


def test_soft_deleted_own_tasks_free_their_key():
    p = plan()
    t = task(p, origin="user", provider="", dedupe_key="user:1", slot="custom", kind="custom")
    t.deleted_at = timezone.now()
    t.save()
    task(p, origin="user", provider="", dedupe_key="user:1", slot="custom", kind="custom")


def test_client_id_is_unique_per_student():
    p = plan()
    cid = uuid.uuid4()
    task(p, client_id=cid)
    rejected(lambda: task(p, dedupe_key="other", client_id=cid))
    task(p, dedupe_key="other", client_id=None)
    task(p, dedupe_key="other2", client_id=None)  # nulls never collide


def test_task_value_checks():
    p = plan()
    rejected(lambda: task(p, dedupe_key="a", origin="robot"))
    rejected(lambda: task(p, dedupe_key="b", slot="nope"))
    rejected(lambda: task(p, dedupe_key="c", state="paused"))
    rejected(lambda: task(p, dedupe_key="d", est_minutes=0))
    rejected(lambda: task(p, dedupe_key="e", est_minutes=181))
    rejected(lambda: task(p, dedupe_key="f", target_value=0))
    rejected(lambda: task(p, dedupe_key="g", target_value=101))
    rejected(lambda: task(p, dedupe_key="h", progress_value=-1))
    rejected(lambda: task(p, dedupe_key="i", link_path="https://evil.example"))
    rejected(lambda: task(p, dedupe_key="j", link_path="/api/v1/today/open"))
    task(p, dedupe_key="ok", link_path="/app/revision", target_value=5, est_minutes=180)


def test_state_columns_only_exist_in_their_own_state():
    p = plan()
    now = timezone.now()
    rejected(lambda: task(p, dedupe_key="a", state="done"))  # done needs completed_at
    rejected(lambda: task(p, dedupe_key="b", completed_at=now))  # completed_at needs done
    rejected(lambda: task(p, dedupe_key="c", completed_via="manual"))
    rejected(lambda: task(p, dedupe_key="d", state="snoozed"))  # snoozed needs a date
    rejected(lambda: task(p, dedupe_key="e", snoozed_until=DAY))
    rejected(lambda: task(p, dedupe_key="f", skip_reason="no_time"))
    rejected(lambda: task(p, dedupe_key="g", end_reason="day_ended"))
    rejected(lambda: task(p, dedupe_key="h", state="skipped", skip_reason="bored"))
    rejected(lambda: task(p, dedupe_key="i", state="expired", end_reason="whim"))
    rejected(lambda: task(p, dedupe_key="j", state="done", completed_at=now, completed_via="telepathy"))
    task(p, dedupe_key="ok1", state="done", completed_at=now, completed_via="event")
    task(p, dedupe_key="ok2", state="snoozed", snoozed_until=DAY + timedelta(days=1))
    task(p, dedupe_key="ok3", state="skipped", skip_reason="swapped")
    task(p, dedupe_key="ok4", state="expired", end_reason="no_longer_needed")


def test_payload_is_kept_small():
    p = plan()
    rejected(lambda: task(p, payload={"x": "y" * 5000}))
    task(p, dedupe_key="ok", payload={"v": 1, "mode": "chapter_quiz", "n": 5})


def test_deleting_a_plan_removes_its_tasks_and_their_evidence():
    p = plan()
    t = task(p)
    TaskEvidence.objects.create(
        task=t, user_id=USER, event_name="coverage_event_recorded", event_key="e1", delta=1, occurred_at=timezone.now()
    )
    p.delete()
    assert Task.objects.count() == 0 and TaskEvidence.objects.count() == 0


# ---- evidence ---------------------------------------------------------------------------------------------------------------


def test_evidence_is_idempotent_per_task_event_and_key():
    t = task(plan())
    now = timezone.now()
    make = lambda key: TaskEvidence.objects.create(  # noqa: E731
        task=t, user_id=USER, event_name="practice_session_completed", event_key=key, delta=3, occurred_at=now
    )
    make("s1")
    rejected(lambda: make("s1"))  # a replayed event adds nothing
    make("s2")
    assert TaskEvidence.objects.filter(task=t).count() == 2


# ---- settings and provider config -------------------------------------------------------------------------------------------


def test_settings_checks():
    rejected(lambda: TodaySettings.objects.create(user_id=uuid.uuid4(), minutes_per_day=14))
    rejected(lambda: TodaySettings.objects.create(user_id=uuid.uuid4(), minutes_per_day=241))
    rejected(lambda: TodaySettings.objects.create(user_id=uuid.uuid4(), focus_papers=0))
    rejected(lambda: TodaySettings.objects.create(user_id=uuid.uuid4(), focus_papers=5))
    rejected(lambda: TodaySettings.objects.create(user_id=uuid.uuid4(), lite_mode="max"))
    s = TodaySettings.objects.create(user_id=uuid.uuid4())
    assert (s.minutes_per_day, s.focus_papers, s.lite_mode, s.show_tomorrow, s.celebrate) == (
        None,
        None,
        "auto",
        True,
        True,
    )


def test_provider_config_defaults_and_checks():
    cfg = ProviderConfig.objects.create(provider="coverage.revision")
    assert cfg.enabled is True and cfg.weight_pct == 100
    rejected(lambda: ProviderConfig.objects.create(provider="a.b", weight_pct=301))
    rejected(lambda: ProviderConfig.objects.create(provider="a.c", max_candidates=51))
    rejected(lambda: ProviderConfig.objects.create(provider="a.d", timeout_ms=99))
    ProviderConfig.objects.create(provider="a.e", weight_pct=0, max_candidates=1, timeout_ms=2000)
