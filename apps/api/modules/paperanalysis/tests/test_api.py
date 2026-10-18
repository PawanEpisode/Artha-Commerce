"""
API integration tests for F-11 Paper Analysis and Recommendations.
Tests:
- Authentication (401)
- Feature flag fail-closed (403 feature_disabled)
- Student recommendation endpoints (PriorityView, stats, patterns, history)
- Plan workflow (preview, adopt, get active, replan, update item, delete)
- Editorial workflows (create paper, import, allocate, confirm, publish)
- Public SEO endpoint
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from modules.paperanalysis.models import (
    Allocation,
    Paper,
    PaperQuestion,
)
from modules.paperanalysis.services import create_paper, refresh_paper_stats

BASE = "/paperanalysis"


@pytest.fixture
def published_setup(syllabus_tree):
    scheme = syllabus_tree
    subject = scheme.subjects.first()
    chapters = list(subject.chapters.all())
    editor_id = uuid.uuid4()

    c1, c2 = chapters[:2]
    terms = ["2024-05", "2024-11", "2025-05"]
    last_paper = None

    for term in terms:
        paper = create_paper(
            editor_id=editor_id,
            subject_id=subject.id,
            term_code=term,
            paper_kind="exam",
            total_marks=Decimal("100.0"),
        )
        last_paper = paper

        pq1 = PaperQuestion.objects.create(
            paper=paper,
            label="Q1",
            position=1,
            marks=Decimal("60.0"),
            format="descriptive",
        )
        pq2 = PaperQuestion.objects.create(
            paper=paper,
            label="Q2",
            position=2,
            marks=Decimal("40.0"),
            format="descriptive",
        )

        Allocation.objects.create(
            paper_question=pq1,
            chapter=c1,
            subject=subject,
            scheme=scheme,
            subject_key=subject.key,
            chapter_key=c1.key,
            marks=Decimal("60.0"),
            share=Decimal("1.000"),
            status=Allocation.Status.CONFIRMED,
            decided_by=editor_id,
            decided_at=timezone.now(),
        )
        pq1.alloc_state = PaperQuestion.AllocState.CONFIRMED
        pq1.save()

        Allocation.objects.create(
            paper_question=pq2,
            chapter=c2,
            subject=subject,
            scheme=scheme,
            subject_key=subject.key,
            chapter_key=c2.key,
            marks=Decimal("40.0"),
            share=Decimal("1.000"),
            status=Allocation.Status.CONFIRMED,
            decided_by=editor_id,
            decided_at=timezone.now(),
        )
        pq2.alloc_state = PaperQuestion.AllocState.CONFIRMED
        pq2.save()

        paper.status = Paper.Status.PUBLISHED
        paper.confirmed_marks = Decimal("100.0")
        paper.save()

        refresh_paper_stats(paper.id)

    paper = last_paper

    return {
        "scheme": scheme,
        "subject": subject,
        "chapters": chapters,
        "paper": paper,
        "editor_id": editor_id,
    }


@pytest.mark.django_db
def test_feature_flag_fail_closed(student_api, pa_flags):
    # Disable paper_analysis flag
    pa_flags(False)

    res = student_api.get(f"{BASE}/recommendations/")
    assert res.status_code == 403
    assert res.json_body.get("error", {}).get("code") == "feature_disabled"

    res_sub = student_api.get(f"{BASE}/subjects/")
    assert res_sub.status_code == 403
    assert res_sub.json_body.get("error", {}).get("code") == "feature_disabled"


@pytest.mark.django_db
def test_unauthenticated_request_rejected(client):
    res = client.get(f"/api/v1{BASE}/recommendations/")
    assert res.status_code == 401


@pytest.mark.django_db
def test_student_recommendations_and_stats(student_api, published_setup):
    setup = published_setup
    subject = setup["subject"]
    c1 = setup["chapters"][0]

    # Recommendations (PriorityView)
    res = student_api.get(f"{BASE}/recommendations/")
    assert res.status_code == 200
    body = res.json_body
    assert body["v"] == 1
    assert "snapshot_id" in body
    assert body["disclaimer_key"] == "history_not_guarantee_v1"
    assert len(body["subjects"]) >= 1

    # Subject statuses
    res_sub = student_api.get(f"{BASE}/subjects/")
    assert res_sub.status_code == 200
    assert len(res_sub.json_body["subjects"]) >= 1

    # Chapter stats
    res_stats = student_api.get(f"{BASE}/subjects/{subject.key}/stats/")
    assert res_stats.status_code == 200
    assert "chapters" in res_stats.json_body

    # Patterns
    res_pat = student_api.get(f"{BASE}/subjects/{subject.key}/patterns/")
    assert res_pat.status_code == 200
    assert "formats" in res_pat.json_body

    # Chapter history
    res_hist = student_api.get(f"{BASE}/chapters/{c1.key}/history/")
    assert res_hist.status_code == 200
    assert "history" in res_hist.json_body


@pytest.mark.django_db
def test_student_settings(student_api):
    # GET settings
    res = student_api.get(f"{BASE}/settings/")
    assert res.status_code == 200
    assert res.json_body["window"] == 6

    # PUT settings
    res_put = student_api.put(f"{BASE}/settings/", {"window": 8, "hide_tiers": True})
    assert res_put.status_code == 200
    assert res_put.json_body["window"] == 8
    assert res_put.json_body["hide_tiers"] is True


@pytest.mark.django_db
def test_plan_workflow(student_api, published_setup):
    client_id = uuid.uuid4()

    # 1. Preview plan
    prev_payload = {
        "days": 10,
        "hours_per_day": 3.0,
        "balance_subjects": False,
    }
    res_prev = student_api.post(f"{BASE}/plan/preview/", prev_payload)
    assert res_prev.status_code == 200
    prev_body = res_prev.json_body
    assert "budget_hours" in prev_body
    assert "hours_used" in prev_body
    assert "items" in prev_body

    # 2. Adopt plan
    adopt_payload = {
        "client_id": str(client_id),
        "days": 10,
        "hours_per_day": 3.0,
        "balance_subjects": False,
    }
    res_adopt = student_api.post(f"{BASE}/plan/adopt/", adopt_payload)
    assert res_adopt.status_code == 201
    plan_data = res_adopt.json_body
    assert plan_data["client_id"] == str(client_id)
    assert plan_data["days"] == 10
    assert len(plan_data["items"]) >= 1

    item_id = plan_data["items"][0]["id"]

    # 3. Get active plan
    res_active = student_api.get(f"{BASE}/plan/active/")
    assert res_active.status_code == 200
    assert res_active.json_body["plan"]["id"] == plan_data["id"]

    # 4. Mark item done
    res_item = student_api.patch(f"{BASE}/plan/items/{item_id}/", {"state": "done"})
    assert res_item.status_code == 200
    assert res_item.json_body["state"] == "done"

    # 5. Replan
    res_replan = student_api.post(f"{BASE}/plan/replan/", {"days_remaining": 5, "hours_per_day": 4.0})
    assert res_replan.status_code == 200
    assert res_replan.json_body["days"] == 5

    # 6. End active plan
    res_del = student_api.delete(f"{BASE}/plan/active/")
    assert res_del.status_code == 200
    assert res_del.json_body["status"] == "ended"

    res_empty = student_api.get(f"{BASE}/plan/active/")
    assert res_empty.status_code == 200
    assert res_empty.json_body["plan"] is None


@pytest.mark.django_db
def test_editorial_endpoints_permission_and_flow(editor_api, student_api, published_setup):
    setup = published_setup
    subject = setup["subject"]
    c1, c2 = setup["chapters"][:2]

    # Student cannot create or list editorial papers (403)
    res_denied = student_api.get(f"{BASE}/papers/")
    assert res_denied.status_code == 403

    # Editor can create paper
    create_payload = {
        "subject_id": str(subject.id),
        "term_code": "2026-05",
        "paper_kind": "exam",
        "total_marks": 100.0,
    }
    res_create = editor_api.post(f"{BASE}/papers/", create_payload)
    assert res_create.status_code == 201
    paper_id = res_create.json_body["id"]

    # Import skeleton CSV
    csv_content = f"""label,position,marks,format,nature,section,choice_group,pick_n,of_m,chapter_key,topic_key,share,source_ref,tag_hint
Q1,1,50.0,descriptive,practical,Sec A,,,1.0,{c1.key},,1.0,,Hint 1
Q2,2,50.0,descriptive,theory,Sec A,,,1.0,{c2.key},,1.0,,Hint 2
"""
    res_import = editor_api.post(f"{BASE}/papers/{paper_id}/import/", {"csv_content": csv_content, "dry_run": False})
    assert res_import.status_code == 200
    assert res_import.json_body["questions_created"] == 2

    # Get paper detail
    res_detail = editor_api.get(f"{BASE}/papers/{paper_id}/")
    assert res_detail.status_code == 200
    q1 = res_detail.json_body["questions"][0]
    q2 = res_detail.json_body["questions"][1]

    # Confirm Q1 and Q2
    res_conf1 = editor_api.post(f"{BASE}/questions/{q1['id']}/confirm/", {"rev": q1["rev"]})
    assert res_conf1.status_code == 200

    res_conf2 = editor_api.post(f"{BASE}/questions/{q2['id']}/confirm/", {"rev": q2["rev"]})
    assert res_conf2.status_code == 200

    # Publish paper
    res_paper = editor_api.get(f"{BASE}/papers/{paper_id}/")
    res_pub = editor_api.post(f"{BASE}/papers/{paper_id}/publish/", {"rev": res_paper.json_body["rev"]})
    assert res_pub.status_code == 200
    assert res_pub.json_body["status"] == "published"


@pytest.mark.django_db
def test_public_seo_endpoint(client, published_setup, pa_flags):
    setup = published_setup
    subject = setup["subject"]
    level = setup["scheme"].level
    course = level.course

    res = client.get(f"/api/v1{BASE}/public/{course.code}/{level.code}/{subject.key}/")
    assert res.status_code == 200
    assert res.json()["subject_key"] == subject.key
    assert "chapters" in res.json()
    assert "patterns" in res.json()
