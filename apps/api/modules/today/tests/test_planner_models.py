"""The database enforces the ERD's planner constraints (ERD 2.6 to 2.8) and the admin shows plans read-only."""

import uuid
from datetime import date, timedelta

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from modules.today.models import Milestone, ReplanEvent, StudyPlan

pytestmark = pytest.mark.django_db

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
ENROLMENT = uuid.UUID("5a1d0c3e-2b7f-4e11-9c55-7d2f4a9b1e20")
EXAM = date(2027, 1, 14)


def plan(**over) -> StudyPlan:
    fields = dict(user_id=USER, enrollment_id=ENROLMENT, scheme_id=uuid.uuid4(), exam_date=EXAM, daily_minutes=180)
    fields.update(over)
    return StudyPlan.objects.create(**fields)


def milestone(p: StudyPlan, **over) -> Milestone:
    fields = dict(
        plan=p,
        user_id=USER,
        subject_key="audit",
        kind="finish_reading",
        target_date=date(2026, 12, 1),
        original_target_date=date(2026, 12, 1),
    )
    fields.update(over)
    return Milestone.objects.create(**fields)


def event(p: StudyPlan, **over) -> ReplanEvent:
    fields = dict(plan=p, user_id=USER, trigger="weekly", health_before="on_track", health_after="on_track")
    fields.update(over)
    return ReplanEvent.objects.create(**fields)


def rejected(make):
    with pytest.raises(IntegrityError), transaction.atomic():
        make()


# ---- study plan -------------------------------------------------------------------------------------------------------------


def test_a_plan_has_the_erd_defaults():
    p = plan()
    assert (p.status, p.health, p.utilisation_pct, p.replan_no, p.version, p.shortfall_minutes) == (
        "active",
        "unknown",
        70,
        0,
        1,
        0,
    )
    assert p.params == {} and p.reading_deadline is None and p.id and p.created_at


def test_one_active_plan_per_student_and_enrolment_but_history_is_free():
    first = plan()
    rejected(plan)
    other_enrolment = plan(enrollment_id=uuid.uuid4())
    first.status = "superseded"
    first.save()
    again = plan()  # the superseded one made room
    plan(status="archived")
    plan(status="archived")
    assert StudyPlan.objects.filter(user_id=USER, status="active").count() == 2
    assert again.pk != first.pk and other_enrolment.pk


@pytest.mark.parametrize(
    "over",
    [
        dict(status="paused"),
        dict(health="fine"),
        dict(daily_minutes=29),
        dict(daily_minutes=721),
        dict(utilisation_pct=29),
        dict(utilisation_pct=101),
        dict(capacity_minutes=-1),
        dict(remaining_minutes=-1),
        dict(shortfall_minutes=-1),
        dict(remaining_minutes=100, capacity_minutes=40, shortfall_minutes=59),  # not remaining - capacity
        dict(remaining_minutes=100, capacity_minutes=40, shortfall_minutes=61),
        dict(remaining_minutes=10, capacity_minutes=40, shortfall_minutes=1),  # nothing is short when it fits
        dict(reading_deadline=EXAM + timedelta(days=1)),
        dict(params={"x": "y" * 2100}),
    ],
)
def test_the_database_rejects_a_plan_that_breaks_a_rule(over):
    rejected(lambda: plan(**over))


def test_the_database_accepts_the_edges_of_every_range():
    plan(daily_minutes=30, utilisation_pct=30, enrollment_id=uuid.uuid4())
    plan(daily_minutes=720, utilisation_pct=100, enrollment_id=uuid.uuid4())
    plan(
        remaining_minutes=100,
        capacity_minutes=40,
        shortfall_minutes=60,
        reading_deadline=EXAM,
        enrollment_id=uuid.uuid4(),
    )
    plan(remaining_minutes=40, capacity_minutes=100, shortfall_minutes=0, enrollment_id=uuid.uuid4(), health="on_track")


# ---- milestones -------------------------------------------------------------------------------------------------------------


def test_a_milestone_is_unique_per_plan_kind_and_paper_and_deleted_with_its_plan():
    p = plan()
    milestone(p)
    rejected(lambda: milestone(p))
    milestone(p, kind="first_revision")
    milestone(p, subject_key="costing")
    milestone(plan(enrollment_id=uuid.uuid4()))  # another plan may have the same paper and kind
    assert Milestone.objects.filter(plan=p).count() == 3
    p.delete()
    assert Milestone.objects.filter(plan_id=p.pk).count() == 0


@pytest.mark.parametrize(
    "over",
    [
        dict(kind="final_exam"),
        dict(status="late"),
        dict(remaining_minutes=-5),
        dict(kind="exam_week", subject_key="audit"),  # the plan's own milestone has no paper
        dict(kind="mock", subject_key=""),  # and every paper milestone has one
        dict(status="done"),  # a done milestone says when
        dict(status="pending", done_at=timezone.now()),  # and only a done one does
    ],
)
def test_the_database_rejects_a_milestone_that_breaks_a_rule(over):
    rejected(lambda: milestone(plan(), **over))


def test_the_whole_plan_milestone_and_a_done_milestone_are_accepted():
    p = plan()
    milestone(
        p,
        kind="exam_week",
        subject_key="",
        target_date=EXAM - timedelta(days=7),
        original_target_date=EXAM - timedelta(days=7),
    )
    done = milestone(p, status="done", done_at=timezone.now())
    assert done.status == "done" and Milestone.objects.get(pk=done.pk).done_at is not None


def test_a_milestone_keeps_its_stable_key_when_the_subject_row_is_removed():
    from modules.syllabus.tests.helpers import make_scheme

    subject = make_scheme().subjects.first()
    m = milestone(plan(), subject=subject, subject_key=subject.key)
    subject.delete()
    m.refresh_from_db()
    assert m.subject_id is None and m.subject_key


# ---- re-plan events ---------------------------------------------------------------------------------------------------------


def test_a_replan_event_is_pending_until_an_option_is_chosen():
    p = plan()
    e = event(p)
    assert e.option_chosen is None and e.summary == {} and e.moved_count == 0 and e.created_at
    e.option_chosen = "more_time"
    e.save()
    for choice in ("skim_low_weight", "next_attempt", "none"):
        event(p, option_chosen=choice)
    assert ReplanEvent.objects.filter(plan=p).count() == 4


@pytest.mark.parametrize(
    "over",
    [
        dict(trigger="daily"),
        dict(health_before="great"),
        dict(health_after="great"),
        dict(option_chosen="give_up"),
        dict(option_chosen=""),
        dict(shortfall_before=-1),
        dict(shortfall_after=-1),
        dict(moved_count=-1),
        dict(summary={"v": 1, "x": "y" * 8200}),  # more than 8 KB
    ],
)
def test_the_database_rejects_a_replan_event_that_breaks_a_rule(over):
    rejected(lambda: event(plan(), **over))


def test_every_trigger_and_every_health_value_of_the_erd_is_accepted_and_events_go_with_their_plan():
    p = plan()
    for trigger in ("missed_days", "weekly", "manual", "exam_date", "scheme_switch"):
        event(p, trigger=trigger)
    for health in ("unknown", "on_track", "slightly_behind", "at_risk"):
        event(p, health_before=health, health_after=health)
    p.delete()
    assert ReplanEvent.objects.filter(plan_id=p.pk).count() == 0


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="the summary size check counts jsonb text, which only PostgreSQL renders"
)
def test_a_summary_the_planner_considers_small_enough_is_accepted_by_the_database():
    from datetime import date as d

    from modules.today.planner import capacity as cap
    from modules.today.planner import constants as pc
    from modules.today.planner import replan as rp

    papers = [cap.PaperInput(f"p{i}", i, 100) for i in range(1, 9)]
    chapters = [
        cap.ChapterInput(f"chapter-{i:04d}-" + "x" * 30, f"p{1 + i % 8}", est_minutes=120, marks_weight=1 + i % 7)
        for i in range(400)
    ]
    params = cap.freeze_deadline(cap.PlanParams(d(2026, 10, 15), EXAM, 60))
    stored = rp.build_plan(params, papers, [cap.ChapterInput("k", "p1", est_minutes=10)]).milestones
    result = rp.replan(stored, params.but(today=d(2026, 11, 20)), papers, chapters, next_exam_date=d(2027, 5, 1))
    summary = rp.summary_json(result)
    saved = event(plan(), summary=summary)
    assert saved.pk and ReplanEvent.objects.get(pk=saved.pk).summary["v"] == pc.PLANNER_VERSION


# ---- admin ------------------------------------------------------------------------------------------------------------------


@pytest.fixture
def staff(client):
    user = get_user_model().objects.create_superuser("ops2", "ops2@example.com", "pw-ops-12345")
    client.force_login(user)
    return client


def test_plans_and_replans_are_visible_to_staff_read_only(staff, settings):
    p = plan()
    milestone(p)
    e = event(p)
    base = f"/{settings.ADMIN_PATH.strip('/')}"
    assert staff.get(f"{base}/today/studyplan/").status_code == 200
    assert staff.get(f"{base}/today/studyplan/{p.pk}/change/").status_code == 200  # the page with its milestones listed
    assert staff.get(f"{base}/today/replanevent/").status_code == 200
    for model in ("studyplan", "replanevent"):
        assert staff.get(f"{base}/today/{model}/add/").status_code == 403
    assert staff.post(f"{base}/today/studyplan/{p.pk}/delete/", {"post": "yes"}).status_code == 403
    assert staff.post(f"{base}/today/replanevent/{e.pk}/delete/", {"post": "yes"}).status_code == 403
    assert StudyPlan.objects.filter(pk=p.pk).exists() and ReplanEvent.objects.filter(pk=e.pk).exists()
    assert Milestone in {i.model for r in [admin.site._registry[StudyPlan]] for i in r.get_inline_instances(None)}
