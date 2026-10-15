"""
Tests for Question Bank editor features (CSV import, review queue, reports listing & resolving).
"""

from __future__ import annotations

import uuid

import pytest

from modules.questionbank.models import Question, QuestionVersion, Report, Review


@pytest.mark.django_db
def test_import_questions_csv(editor_api):
    csv_content = """stem_md,kind,marks,option_a,option_b,option_c,option_d,correct_option,explanation_md
Which section of CGST Act deals with Input Tax Credit?,mcq_single,1,Section 15,Section 16,Section 17,Section 18,B,Section 16 covers ITC eligibility and conditions.
What is the standard GST rate for gold jewelry?,mcq_single,1,1%,3%,5%,12%,B,Gold attracts 3% IGST.
"""
    res = editor_api.post("/questionbank/editor/import-csv/", {"csv_text": csv_content, "auto_publish": True})
    assert res.status_code == 201
    assert res.json_body["total_rows"] == 2
    assert res.json_body["imported_count"] == 2
    assert len(res.json_body["errors"]) == 0
    assert Question.objects.filter(origin_module="csv").count() == 2


@pytest.mark.django_db
def test_editor_review_queue(editor_api):
    q = Question.objects.create(
        kind="mcq_single",
        owner_user_id=uuid.uuid4(),
        stem_head="Test question for review queue",
        visibility=Question.Visibility.PRIVATE,
    )
    v = QuestionVersion.objects.create(
        question=q,
        version_no=1,
        state=QuestionVersion.State.IN_REVIEW,
        stem_md="Test question for review queue",
    )
    r = Review.objects.create(
        question=q,
        version=v,
        kind=Review.Kind.NEW_PUBLIC,
        status=Review.Status.PENDING,
    )

    res = editor_api.get("/questionbank/editor/review-queue/")
    assert res.status_code == 200
    assert len(res.json_body["items"]) >= 1
    assert any(item["id"] == str(r.id) for item in res.json_body["items"])


@pytest.mark.django_db
def test_editor_reports_listing_and_resolving(editor_api):
    q = Question.objects.create(
        kind="mcq_single",
        owner_user_id=uuid.uuid4(),
        stem_head="Test question for reports",
        visibility=Question.Visibility.PUBLIC,
    )
    v = QuestionVersion.objects.create(
        question=q,
        version_no=1,
        state=QuestionVersion.State.LIVE,
        stem_md="Test question for reports",
    )
    rep = Report.objects.create(
        question=q,
        version=v,
        reporter_user_id=uuid.uuid4(),
        kind="error",
        message="Option B formula is wrong.",
        status=Report.Status.OPEN,
    )

    # List reports
    list_res = editor_api.get("/questionbank/editor/reports/")
    assert list_res.status_code == 200
    assert any(item["id"] == str(rep.id) for item in list_res.json_body["items"])

    # Resolve report
    res = editor_api.post(
        f"/questionbank/editor/reports/{rep.id}/resolve/", {"status": "fixed", "note": "Fixed typo in formula."}
    )
    assert res.status_code == 200
    rep.refresh_from_db()
    assert rep.status == Report.Status.FIXED
    assert rep.resolution_note == "Fixed typo in formula."
