import json
import uuid
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.test import Client

from core import feature_flags
from modules.profiles.models import Profile
from modules.questionbank.models import (
    AnswerKey,
    Option,
    Question,
    QuestionVersion,
)
from modules.syllabus.tests.helpers import make_scheme

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


class Api:
    def __init__(self, token: str):
        self.c = Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _send(self, method, path, body=None, **headers):
        if not path.startswith("/api/v1"):
            path = f"/api/v1{path}"
        res = getattr(self.c, method)(
            path,
            data=json.dumps(body) if body is not None else None,
            content_type="application/json",
            **headers,
        )
        res.json_body = res.json() if res.content else None
        return res

    def get(self, path, **headers):
        return self._send("get", path, **headers)

    def post(self, path, body=None):
        return self._send("post", path, body or {})

    def put(self, path, body=None):
        return self._send("put", path, body or {})

    def patch(self, path, body=None):
        return self._send("patch", path, body or {})

    def delete(self, path, body=None):
        return self._send("delete", path, body)


@pytest.fixture(autouse=True)
def _fresh_throttle_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def qb_flag(settings, monkeypatch):
    """Enables question_bank feature flag."""

    def _set(on: bool):
        class Client_:
            def get_feature_flag(self, key, distinct_id, **kwargs):
                return on if key == "question_bank" else None

        settings.POSTHOG_API_KEY = "phc_test"
        monkeypatch.setattr(feature_flags, "_client", Client_())
        feature_flags.clear_flag_cache()

    _set(True)
    yield _set
    feature_flags.clear_flag_cache()


@pytest.fixture
def api(make_token, qb_flag, db):
    Profile.objects.update_or_create(
        id=USER,
        defaults={"email": "student@example.com", "full_name": "Student"},
    )
    return Api(make_token(sub=str(USER)))


@pytest.fixture
def events():
    emitted = []

    def _handler(name):
        return lambda **kw: emitted.append({"name": name, **kw})

    from core import events as core_events

    handlers = []
    for ev in ("practice_session_completed", "practice_session_started"):
        h = _handler(ev)
        core_events.subscribe(ev, h)
        handlers.append((ev, h))
    yield emitted
    for ev, h in handlers:
        core_events.unsubscribe(ev, h)


@pytest.fixture
def sample_questions(db):
    scheme = make_scheme()
    level = scheme.level
    course = level.course
    subject = scheme.subjects.first()
    chapter = subject.chapters.first()

    # 1. MCQ Single
    q1 = Question.objects.create(
        course=course,
        level=level,
        primary_subject=subject,
        primary_chapter=chapter,
        kind="mcq_single",
        difficulty=1,
        visibility=Question.Visibility.PUBLIC,
        status=Question.Status.ACTIVE,
        source_name="RTP",
        source_year=2024,
    )
    v1 = QuestionVersion.objects.create(
        question=q1,
        version_no=1,
        state=QuestionVersion.State.LIVE,
        stem_md="Which of the following is correct?",
        stem_text="Which of the following is correct?",
        explanation_md="Option A is correct according to Section 10.",
        explanation_source="Study Material Module 1",
        marks=Decimal("2.0"),
        negative_marks=Decimal("0.5"),
    )
    q1.live_version = v1
    q1.save(update_fields=["live_version"])
    opt1_1 = Option.objects.create(
        version=v1,
        body_md="Option A",
        body_text="Option A",
        is_correct=True,
        position=1,
    )
    opt1_2 = Option.objects.create(
        version=v1,
        body_md="Option B",
        body_text="Option B",
        is_correct=False,
        position=2,
    )

    # 2. MCQ Multi
    q2 = Question.objects.create(
        course=course,
        level=level,
        primary_subject=subject,
        primary_chapter=chapter,
        kind="mcq_multi",
        difficulty=2,
        visibility=Question.Visibility.PUBLIC,
        status=Question.Status.ACTIVE,
        source_name="MTP",
        source_year=2024,
    )
    v2 = QuestionVersion.objects.create(
        question=q2,
        version_no=1,
        state=QuestionVersion.State.LIVE,
        stem_md="Select all true statements.",
        stem_text="Select all true statements.",
        explanation_md="Statements 1 and 2 are true.",
        marks=Decimal("2.0"),
        negative_marks=Decimal("0.5"),
        multi_scoring=QuestionVersion.MultiScoring.ALL_OR_NOTHING,
    )
    q2.live_version = v2
    q2.save(update_fields=["live_version"])
    opt2_1 = Option.objects.create(
        version=v2,
        body_md="Statement 1",
        body_text="Statement 1",
        is_correct=True,
        position=1,
    )
    opt2_2 = Option.objects.create(
        version=v2,
        body_md="Statement 2",
        body_text="Statement 2",
        is_correct=True,
        position=2,
    )
    opt2_3 = Option.objects.create(
        version=v2,
        body_md="Statement 3",
        body_text="Statement 3",
        is_correct=False,
        position=3,
    )

    # 3. Numeric
    q3 = Question.objects.create(
        course=course,
        level=level,
        primary_subject=subject,
        primary_chapter=chapter,
        kind="numeric",
        difficulty=3,
        visibility=Question.Visibility.PUBLIC,
        status=Question.Status.ACTIVE,
        source_name="Past Exam",
        source_year=2023,
    )
    v3 = QuestionVersion.objects.create(
        question=q3,
        version_no=1,
        state=QuestionVersion.State.LIVE,
        stem_md="Calculate total tax payable.",
        stem_text="Calculate total tax payable.",
        explanation_md="Tax is 42 rupees.",
        marks=Decimal("4.0"),
        negative_marks=Decimal("1.0"),
    )
    q3.live_version = v3
    q3.save(update_fields=["live_version"])
    AnswerKey.objects.create(
        version=v3,
        numeric_value=Decimal("42.0"),
        tolerance_abs=Decimal("1.0"),
        accepted_values=["42.5"],
    )

    return {
        "course": course,
        "level": level,
        "subject": subject,
        "chapter": chapter,
        "q1": q1,
        "v1": v1,
        "opt1_1": opt1_1,
        "opt1_2": opt1_2,
        "q2": q2,
        "v2": v2,
        "opt2_1": opt2_1,
        "opt2_2": opt2_2,
        "opt2_3": opt2_3,
        "q3": q3,
        "v3": v3,
    }
