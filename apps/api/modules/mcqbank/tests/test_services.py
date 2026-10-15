"""
Service layer tests for MCQ Bank (F-05 ERD 3.2).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from modules.mcqbank.models import (
    AdaptiveRun,
    ExternalLog,
    McqSet,
    PatternProfile,
)
from modules.mcqbank.services import (
    log_external_result,
    publish_set,
    save_preset,
    start_adaptive,
    stop_adaptive,
    use_preset,
    verify_pattern,
    withdraw_set,
)
from modules.questionbank.models import Collection, CollectionItem, Question

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
EDITOR = uuid.UUID("11111111-2222-3333-4444-555555555555")


@pytest.mark.django_db
def test_publish_hosted_set_validations(syllabus_tree):
    course = syllabus_tree.level.course
    level = syllabus_tree.level
    chapter = syllabus_tree.subjects.first().chapters.first()

    empty_coll = Collection.objects.create(title="Empty", kind=Collection.Kind.CURATED)
    s = McqSet.objects.create(
        slug="test-hosted",
        title="Test Hosted",
        delivery=McqSet.Delivery.HOSTED,
        collection=empty_coll,
        rights_basis="original",
        course=course,
        level=level,
        subject_key="law",
    )
    with pytest.raises(ValidationError, match="cannot be empty"):
        publish_set(EDITOR, s.id)

    q = Question.objects.create(
        kind="mcq_single",
        stem_head="Test question",
        visibility=Question.Visibility.PUBLIC,
        course=course,
        level=level,
        primary_chapter=chapter,
        status="published",
        rights_status="original",
    )
    CollectionItem.objects.create(collection=empty_coll, question=q, position=1)

    published = publish_set(EDITOR, s.id)
    assert published.status == McqSet.Status.PUBLISHED
    assert published.question_count == 1
    assert published.published_at is not None


@pytest.mark.django_db
def test_publish_linkout_set_validations(syllabus_tree):
    course = syllabus_tree.level.course
    level = syllabus_tree.level
    s = McqSet.objects.create(
        slug="test-linkout",
        title="Test Linkout",
        delivery=McqSet.Delivery.LINK_OUT,
        source_url="https://icmai.in/mcq/portal",
        course=course,
        level=level,
        subject_key="law",
    )
    published = publish_set(EDITOR, s.id)
    assert published.status == McqSet.Status.PUBLISHED


@pytest.mark.django_db
def test_withdraw_set(syllabus_tree):
    course = syllabus_tree.level.course
    level = syllabus_tree.level
    s = McqSet.objects.create(
        slug="test-withdraw",
        title="Test Withdraw",
        status=McqSet.Status.PUBLISHED,
        delivery=McqSet.Delivery.LINK_OUT,
        source_url="https://icmai.in/mcq",
        course=course,
        level=level,
        subject_key="law",
        published_at=datetime.datetime.now(datetime.UTC),
    )
    withdraw_set(EDITOR, s.id, reason="takedown")
    s.refresh_from_db()
    assert s.status == McqSet.Status.WITHDRAWN
    assert s.withdrawn_reason == "takedown"


@pytest.mark.django_db
def test_log_external_result(syllabus_tree):
    course = syllabus_tree.level.course
    level = syllabus_tree.level
    chapter = syllabus_tree.subjects.first().chapters.first()

    s = McqSet.objects.create(
        slug="test-ext-log",
        title="Test External Set",
        status=McqSet.Status.PUBLISHED,
        delivery=McqSet.Delivery.LINK_OUT,
        source_url="https://icmai.in/mcq",
        course=course,
        level=level,
        subject_key="law",
        chapter=chapter,
    )
    d = datetime.date(2026, 10, 15)
    log = log_external_result(
        user_id=USER,
        set_id=s.id,
        score=Decimal("16"),
        max_score=Decimal("20"),
        taken_on=d,
        client_id=uuid.uuid4(),
    )
    assert log.score == Decimal("16")
    assert log.max_score == Decimal("20")
    assert log.score_pct == Decimal("80.0")

    # Second log on same day replaces first (upsert)
    log2 = log_external_result(
        user_id=USER,
        set_id=s.id,
        score=Decimal("18"),
        max_score=Decimal("20"),
        taken_on=d,
        client_id=uuid.uuid4(),
    )
    assert log2.id == log.id
    assert log2.score == Decimal("18")
    assert log2.score_pct == Decimal("90.0")
    assert ExternalLog.objects.filter(user_id=USER).count() == 1


@pytest.mark.django_db
def test_presets_limit_and_use():
    p = save_preset(
        user_id=USER,
        name="My Sprint",
        kind="builder",
        mode="timed",
        picker="filter",
        spec={"count": 10},
        time_limit_seconds=900,
    )
    assert p.name == "My Sprint"
    assert p.user_id == USER

    session_spec = use_preset(USER, p.id)
    assert session_spec["picker"] == "filter"
    assert session_spec["mode"] == "timed"
    assert session_spec["time_limit_seconds"] == 900
    p.refresh_from_db()
    assert p.use_count == 1


@pytest.mark.django_db
def test_verify_pattern(syllabus_tree):
    course = syllabus_tree.level.course
    level = syllabus_tree.level

    p = PatternProfile.objects.create(
        course=course,
        level=level,
        subject_key="tax",
        effective_from=datetime.date(2024, 1, 1),
        format=PatternProfile.Format.ALL_MCQ,
        mcq_count=15,
        mcq_total_marks=Decimal("30.0"),
    )
    assert p.verified is False

    verified = verify_pattern(EDITOR, p.id)
    assert verified.verified is True
    assert verified.verified_by == EDITOR
    assert verified.status == PatternProfile.Status.ACTIVE


@pytest.mark.django_db
def test_adaptive_run_and_stop():
    run = start_adaptive(
        user_id=USER,
        scope_type="subject",
        scope_id=uuid.uuid4(),
        subject_key="costing",
        client_id=uuid.uuid4(),
    )
    assert run.status == AdaptiveRun.Status.ACTIVE

    run2 = start_adaptive(
        user_id=USER,
        scope_type="subject",
        scope_id=run.scope_id,
        subject_key="costing",
        client_id=uuid.uuid4(),
    )
    assert run2.id == run.id

    stop_adaptive(USER, run.id)
    run.refresh_from_db()
    assert run.status == AdaptiveRun.Status.STOPPED


@pytest.mark.django_db
def test_seed_commands():
    from django.core.management import call_command

    # Run seed_cma_pyq
    call_command("seed_cma_pyq")
    from modules.pyq.models import PyqPaper

    assert PyqPaper.objects.filter(course__code="cma").count() >= 5

    # Run seed_mcq_bank
    call_command("seed_mcq_bank")
    assert PatternProfile.objects.filter(course__code="cma").count() >= 6
    assert McqSet.objects.filter(course__code="cma").count() >= 4
