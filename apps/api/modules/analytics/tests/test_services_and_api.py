"""
Integration tests for Analytics services, idempotency, and API endpoints.
"""

from decimal import Decimal
import uuid
from datetime import date, timedelta
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from modules.analytics import selectors, services
from modules.analytics.models import (
    ChapterFact,
    MistakeTag,
    ReadinessProfile,
    Report,
    SessionRun,
    Settings,
    TopicFact,
    UserState,
)
from modules.syllabus.models import Course, Scheme, Level, Subject, Chapter

User = get_user_model()


@pytest.fixture
def auth_user():
    return User.objects.create_user(username="testuser", email="test@example.com")


@pytest.fixture
def api_client(auth_user):
    client = APIClient()
    client.force_authenticate(user=auth_user)
    return client


@pytest.fixture
def sample_syllabus(db):
    course, _ = Course.objects.get_or_create(code="ca", defaults={"name": "Chartered Accountancy"})
    level, _ = Level.objects.get_or_create(course=course, code="inter", defaults={"name": "Intermediate"})
    scheme, _ = Scheme.objects.get_or_create(level=level, code="2024", defaults={"name": "Scheme 2024"})
    subject, _ = Subject.objects.get_or_create(scheme=scheme, key="taxation", defaults={"name": "Taxation"})
    chapter, _ = Chapter.objects.get_or_create(subject=subject, key="salaries", defaults={"name": "Income from Salaries"})
    profile, _ = ReadinessProfile.objects.get_or_create(
        course=course,
        level=level,
        version=1,
        defaults={
            "status": "active",
            "effective_from": date(2026, 1, 1),
        },
    )
    return {
        "course": course,
        "level": level,
        "scheme": scheme,
        "subject": subject,
        "chapter": chapter,
        "profile": profile,
    }


@pytest.mark.django_db
def test_refresh_session_and_idempotency(auth_user, sample_syllabus, monkeypatch):
    session_id = uuid.uuid4()
    chapter = sample_syllabus["chapter"]

    # Mock practice adapter to return fake session and answers
    monkeypatch.setattr(
        "modules.analytics.integrations.practice.get_session",
        lambda u, s: {
            "id": s,
            "user_id": u,
            "mode": "untimed",
            "origin_module": "practice",
            "status": "submitted",
            "local_date": timezone.localdate(),
            "created_at": timezone.now(),
        },
    )
    monkeypatch.setattr(
        "modules.analytics.integrations.practice.get_session_answers",
        lambda u, s: [
            {
                "position": 1,
                "question_id": uuid.uuid4(),
                "question_version_id": uuid.uuid4(),
                "chapter_id": chapter.id,
                "kind": "mcq_single",
                "result": "correct",
                "marks_awarded": Decimal("1.00"),
                "marks_max": Decimal("1.00"),
                "time_spent_ms": 12000,
                "mistake_reason": None,
                "is_repeat": False,
            }
        ],
    )
    monkeypatch.setattr(
        "modules.analytics.integrations.questionbank.get_labels_of_versions",
        lambda vids: {
            vids[0]: {
                "difficulty": 2,
                "source_kind": "platform",
                "suggested_seconds": 60,
                "primary_topic_id": None,
                "subject_key": "taxation",
                "chapter_key": "salaries",
            }
        },
    )

    # 1. First refresh -> changes=True
    res1 = services.refresh_session(auth_user.id, session_id)
    assert res1.changed is True
    assert res1.fact_rows == 1
    assert ChapterFact.objects.filter(session_id=session_id).count() == 1

    # Check UserState bumped
    state = UserState.objects.get(user_id=auth_user.id)
    assert state.facts_version == 1

    # 2. Second refresh with same data -> changes=False (Idempotent!)
    res2 = services.refresh_session(auth_user.id, session_id)
    assert res2.changed is False
    assert ChapterFact.objects.filter(session_id=session_id).count() == 1
    state.refresh_from_db()
    assert state.facts_version == 1  # Unchanged!


@pytest.mark.django_db
def test_analytics_api_endpoints(api_client, auth_user, sample_syllabus):
    # Pre-populate 1 fact
    chapter = sample_syllabus["chapter"]
    session_id = uuid.uuid4()
    today = timezone.localdate()

    SessionRun.objects.create(
        session_id=session_id,
        user_id=auth_user.id,
        origin_module="practice",
        mode="untimed",
        completion="submitted",
        session_created_at=timezone.now(),
        local_date=today,
    )
    ChapterFact.objects.create(
        session_id=session_id,
        chapter_id=chapter.id,
        kind="mcq_single",
        difficulty=2,
        source_kind="platform",
        is_repeat=False,
        local_date=today,
        user_id=auth_user.id,
        subject_key="taxation",
        chapter_key="salaries",
        mode="untimed",
        answered=5,
        correct=4,
        credit_sum=Decimal("4.000"),
        time_n=5,
        time_ms_sum=50000,
        sugg_n=5,
        sugg_ms_sum=60000,
    )
    UserState.objects.create(user_id=auth_user.id, facts_version=1)

    # 1. Overview & 304 ETag check
    resp = api_client.get(reverse("analytics-overview"))
    assert resp.status_code == 200
    assert resp.data["total_answered"] == 5
    assert resp.data["total_correct"] == 4
    etag = resp.headers.get("ETag")
    assert etag is not None

    # Test 304 Not Modified
    resp_304 = api_client.get(reverse("analytics-overview"), HTTP_IF_NONE_MATCH=etag)
    assert resp_304.status_code == 304

    # 2. Performance Explorer
    resp_perf = api_client.get(reverse("analytics-performance") + "?by=chapter")
    assert resp_perf.status_code == 200
    assert len(resp_perf.data["items"]) == 1

    # 3. Trends
    resp_trends = api_client.get(reverse("analytics-trends"))
    assert resp_trends.status_code == 200
    assert len(resp_trends.data["items"]) >= 1

    # 4. Speed
    resp_speed = api_client.get(reverse("analytics-speed"))
    assert resp_speed.status_code == 200
    assert resp_speed.data["timed_answers_count"] == 5

    # 5. Readiness
    resp_readiness = api_client.get(reverse("analytics-readiness"))
    assert resp_readiness.status_code == 200
    assert resp_readiness.data["state"] in ("sparse", "ready", "early", "none")

    # 6. Settings
    resp_sett = api_client.get(reverse("analytics-settings"))
    assert resp_sett.status_code == 200
    resp_patch = api_client.patch(reverse("analytics-settings"), {"target_accuracy": "0.75"}, format="json")
    assert resp_patch.status_code == 200
    assert resp_patch.data["target_accuracy"] == "0.75"

    # 7. Reports & Shares (R2)
    resp_rep = api_client.post(reverse("analytics-reports"), {"period_kind": "30d"}, format="json")
    assert resp_rep.status_code == 201
    rep_id = resp_rep.data["id"]

    resp_share = api_client.post(reverse("analytics-shares"), {"report_id": rep_id, "scopes": ["overview"]}, format="json")
    assert resp_share.status_code == 201
    token = resp_share.data["token"]

    # Public unauthenticated open of share
    unauth_client = APIClient()
    resp_public = unauth_client.get(reverse("analytics-share-detail", kwargs={"token": token}))
    assert resp_public.status_code == 200
    assert "data" in resp_public.data

    # 8. DPDP Erasure
    erasure_counts = services.delete_all_for_user(auth_user.id)
    assert erasure_counts["chapter_facts"] == 1
    assert ChapterFact.objects.filter(user_id=auth_user.id).count() == 0


@pytest.mark.django_db
def test_payload_variants_and_edge_cases(api_client, auth_user, sample_syllabus, monkeypatch):
    chapter = sample_syllabus["chapter"]

    # 1. User reported error: Reports POST with 7d
    resp_7d = api_client.post(
        reverse("analytics-reports"),
        {
            "period_kind": "7d",
            "include_name": True,
            "include_mistakes": True,
            "include_time": True,
        },
        format="json",
    )
    assert resp_7d.status_code == 201
    assert "id" in resp_7d.data
    assert resp_7d.data["status"] == "ready"

    # 2. Refresh with limit=50 (what frontend sends)
    resp_refresh = api_client.post(reverse("analytics-refresh"), {"limit": 50}, format="json")
    assert resp_refresh.status_code == 200
    assert "refreshed_sessions" in resp_refresh.data

    # 3. Fix set with topic_id and limit (what frontend FixDialog sends)
    topic_id = uuid.uuid4()
    mock_session = type("MockSession", (), {"id": uuid.uuid4(), "title": "Fix drill", "mode": "untimed"})
    monkeypatch.setattr(
        "modules.analytics.integrations.practice.create_fix_session",
        lambda **kwargs: mock_session,
    )
    resp_fix = api_client.post(
        reverse("analytics-fix-sets"),
        {"topic_id": str(topic_id), "limit": 10},
        format="json",
    )
    assert resp_fix.status_code == 201
    assert resp_fix.data["session_id"] == str(mock_session.id)
    assert resp_fix.data["item_count"] == 0

    # Also test /fix/ alias
    resp_fix_alias = api_client.post(
        reverse("analytics-fix"),
        {"chapter_id": str(chapter.id), "limit": 10},
        format="json",
    )
    assert resp_fix_alias.status_code == 201

    # 4. Goals with target_kind and target_value (frontend format)
    resp_goal = api_client.post(
        reverse("analytics-goals"),
        {"target_kind": "questions", "target_value": "50"},
        format="json",
    )
    assert resp_goal.status_code == 201
    assert resp_goal.data["target_kind"] == "questions"
    assert Decimal(resp_goal.data["target_value"]) == Decimal("50")

    # 5. Settings target_accuracy normalization (85 -> 0.85)
    resp_sett = api_client.patch(
        reverse("analytics-settings"),
        {"target_accuracy": "85"},
        format="json",
    )
    assert resp_sett.status_code == 200
    assert resp_sett.data["target_accuracy"] == "0.85"

    # 6. Weak topics with invalid limit parameter string
    resp_weak = api_client.get(reverse("analytics-weak-topics") + "?limit=invalid")
    assert resp_weak.status_code == 200
    assert "items" in resp_weak.data

