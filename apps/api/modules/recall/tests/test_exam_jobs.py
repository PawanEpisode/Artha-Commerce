"""R2-W1 upkeep: the nightly walk, the exam-date-change trigger and the re-evaluation of a student's cards."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from core import jobs as core_jobs
from modules.coverage import services as coverage_services
from modules.coverage.models import Enrollment
from modules.recall import jobs, subscribers
from modules.recall.models import RecallCard, RecallItem, RecallScheduleEvent, RecallSettings
from modules.recall.services import exam as exam_service

from .factories import make_card, make_item
from .w5 import ME

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
EXAM_AT = datetime(2026, 12, 11, 4, 0, tzinfo=UTC) - timedelta(hours=5, minutes=30)  # 40 days out


def enrol(scheme, exam: date):
    return Enrollment.objects.create(user_id=ME, scheme=scheme, level=scheme.level, exam_date=exam)


def far_cards(n=4, user=ME, scheme=None):
    """Cards last reviewed 20 days ago whose own due date is two months after the exam."""
    out = []
    for i in range(n):
        item = make_item(user, text=f"far {user} {i} {datetime.now().timestamp()}")
        if scheme is not None:
            RecallItem.objects.filter(pk=item.pk).update(scheme_id=scheme.id)
        out.append(
            make_card(
                item, user, importance=1, state=2, stability=120.0, difficulty=5.0, reps=4,
                last_review_at=NOW - timedelta(days=20),
                due_scheduled_at=EXAM_AT + timedelta(days=60), due_at=EXAM_AT + timedelta(days=60),
            )
        )  # fmt: skip
    return out


def test_cards_beyond_the_cutoff_are_pulled_in_once_and_the_run_is_idempotent(scheme):
    enrol(scheme, date(2026, 12, 11))
    cards = far_cards()
    assert exam_service.reevaluate_student(ME, now=NOW) == 4
    for c in RecallCard.objects.filter(pk__in=[c.pk for c in cards]):
        assert EXAM_AT - timedelta(days=7) <= c.due_at <= EXAM_AT - timedelta(days=3)
        assert c.due_scheduled_at == EXAM_AT + timedelta(days=60)  # the scheduler's own date is a fact
    assert RecallScheduleEvent.objects.filter(kind="horizon", reason_code="exam_horizon").count() == 4
    assert exam_service.reevaluate_student(ME, now=NOW) == 0
    assert RecallScheduleEvent.objects.filter(kind="horizon").count() == 4


def test_after_the_exam_or_with_the_setting_off_the_own_date_comes_back(scheme):
    enrol(scheme, date(2026, 12, 11))
    far_cards(2)
    exam_service.reevaluate_student(ME, now=NOW)
    assert exam_service.reevaluate_student(ME, now=EXAM_AT + timedelta(days=1)) == 2
    assert not RecallCard.objects.filter(user_id=ME).exclude(due_at=EXAM_AT + timedelta(days=60)).exists()
    exam_service.reevaluate_student(ME, now=NOW)
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"exam_horizon": False})
    assert exam_service.reevaluate_student(ME, now=NOW) == 2
    assert not RecallCard.objects.filter(user_id=ME).exclude(due_at=EXAM_AT + timedelta(days=60)).exists()


def test_editing_the_exam_date_queues_a_job_for_that_student_only(scheme, django_capture_on_commit_callbacks):
    subscribers.register()  # other tests clear the event registry
    enr = enrol(scheme, date(2026, 12, 11))
    with django_capture_on_commit_callbacks(execute=True):
        coverage_services.update_enrollment(enr, data={"exam_date": date(2026, 12, 20)})
    queued = list(core_jobs.Job.objects.filter(type=jobs.JOB_EXAM_HORIZON))
    assert len(queued) == 1 and queued[0].payload == {"user_id": str(ME)}
    with django_capture_on_commit_callbacks(execute=True):
        coverage_services.update_enrollment(enr, data={"exam_date": date(2026, 12, 21)})
    assert core_jobs.Job.objects.filter(type=jobs.JOB_EXAM_HORIZON).count() == 1  # merged with the one waiting
    with django_capture_on_commit_callbacks(execute=True):
        coverage_services.update_enrollment(enr, data={"daily_minutes": 60})
    assert core_jobs.Job.objects.filter(type=jobs.JOB_EXAM_HORIZON).count() == 1  # nothing about the exam changed


def test_the_daily_walk_covers_students_with_an_exam_in_the_window_and_skips_the_rest(scheme):
    enrol(scheme, (datetime.now(UTC) + timedelta(days=40)).date())
    out = jobs.exam_horizon_job({})
    assert out["users"] == 1
    Enrollment.objects.all().update(exam_date=(datetime.now(UTC) + timedelta(days=200)).date())
    assert jobs.exam_horizon_job({}) == {"users": 0, "changed": 0}


def test_the_tick_starts_one_walk_a_day_and_runs_it(settings):
    first = jobs.tick()
    again = jobs.tick()
    assert first["jobs_ran"] == 1 and again["jobs_ran"] == 0
    assert core_jobs.Job.objects.filter(type=jobs.JOB_EXAM_HORIZON).count() == 1
