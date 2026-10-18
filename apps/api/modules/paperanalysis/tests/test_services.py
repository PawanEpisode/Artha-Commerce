"""
Unit and integration tests for F-11 Paper Analysis services and background jobs.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from modules.paperanalysis.domain.types import AllocationIn
from modules.paperanalysis.errors import (
    AiBudgetExceeded,
    AllocationSumMismatch,
    PaperConflict,
    PaperExists,
    PaperNotReady,
)
from modules.paperanalysis.jobs import (
    run_suggest,
)
from modules.paperanalysis.models import (
    Allocation,
    Paper,
    PaperQuestion,
)
from modules.paperanalysis.services import (
    confirm_question,
    create_paper,
    import_skeleton_csv,
    publish_paper,
    set_allocations,
    unpublish_paper,
)


@pytest.fixture
def paper_setup(syllabus_tree):
    scheme = syllabus_tree
    subject = scheme.subjects.first()
    chapters = list(subject.chapters.all())
    editor_id = uuid.uuid4()

    paper = create_paper(
        editor_id=editor_id,
        subject_id=subject.id,
        term_code="2025-05",
        paper_kind="exam",
        total_marks=Decimal("100.0"),
    )

    return {
        "scheme": scheme,
        "subject": subject,
        "chapters": chapters,
        "paper": paper,
        "editor_id": editor_id,
    }


@pytest.mark.django_db
def test_create_paper_and_duplicate_prevention(paper_setup):
    setup = paper_setup
    # Duplicate creation with same term_code and paper_kind should raise PaperExists
    with pytest.raises(PaperExists):
        create_paper(
            editor_id=setup["editor_id"],
            subject_id=setup["subject"].id,
            term_code="2025-05",
            paper_kind="exam",
            total_marks=Decimal("100.0"),
        )


@pytest.mark.django_db
def test_import_skeleton_csv(paper_setup):
    setup = paper_setup
    paper = setup["paper"]
    c1, c2 = setup["chapters"][:2]

    csv_data = f"""label,position,marks,format,nature,section,choice_group,pick_n,of_m,chapter_key,topic_key,share,source_ref,tag_hint
1(a),1,10.0,descriptive,practical,Sec A,,,1.0,{c1.key},,1.0,,Depreciation basics
1(b),2,10.0,descriptive,theory,Sec A,,,1.0,{c2.key},,1.0,,Inventory valuation
2,3,20.0,descriptive,practical,Sec B,cg1,1,2,{c1.key},,0.5,,Capital budgeting part 1
2,3,20.0,descriptive,practical,Sec B,cg1,1,2,{c2.key},,0.5,,Capital budgeting part 2
"""
    # Dry run
    res_dry = import_skeleton_csv(setup["editor_id"], paper.id, csv_data, dry_run=True)
    assert len(res_dry.errors) == 0
    assert res_dry.questions_created == 3
    assert paper.questions.count() == 0

    # Real import
    res_real = import_skeleton_csv(setup["editor_id"], paper.id, csv_data, dry_run=False)
    assert len(res_real.errors) == 0
    assert paper.questions.count() == 3

    q1 = paper.questions.get(label="1(a)")
    assert q1.marks == Decimal("10.0")
    assert q1.allocations.count() == 1
    assert q1.allocations.first().chapter_key == c1.key

    q2 = paper.questions.get(label="2")
    assert q2.marks == Decimal("20.0")
    assert q2.choice_group is not None
    assert q2.choice_group.pick_n == 1
    assert q2.choice_group.of_m == 2
    assert q2.allocations.count() == 2


@pytest.mark.django_db
def test_set_allocations_and_exact_sum(paper_setup):
    setup = paper_setup
    paper = setup["paper"]
    c1, c2 = setup["chapters"][:2]

    pq = PaperQuestion.objects.create(
        paper=paper,
        label="Q1",
        position=1,
        marks=Decimal("10.0"),
        format="descriptive",
    )

    # Sum does not equal marks -> raises AllocationSumMismatch
    bad_allocs = [
        AllocationIn(chapter_id=c1.id, marks=Decimal("6.0")),
        AllocationIn(chapter_id=c2.id, marks=Decimal("3.0")),
    ]
    with pytest.raises(AllocationSumMismatch):
        set_allocations(
            editor_id=setup["editor_id"],
            paper_question_id=pq.id,
            rows=bad_allocs,
            rev=1,
        )

    # Valid split: 6.0 and 4.0 = 10.0
    good_allocs = [
        AllocationIn(chapter_id=c1.id, marks=Decimal("6.0"), rationale="Part A"),
        AllocationIn(chapter_id=c2.id, marks=Decimal("4.0"), rationale="Part B"),
    ]
    res_pq = set_allocations(
        editor_id=setup["editor_id"],
        paper_question_id=pq.id,
        rows=good_allocs,
        rev=1,
    )
    assert res_pq.rev == 2
    pq.refresh_from_db()
    assert pq.rev == 2
    assert pq.allocations.count() == 2
    assert sum(a.marks for a in pq.allocations.all()) == Decimal("10.0")

    # Stale rev raises PaperConflict
    with pytest.raises(PaperConflict):
        set_allocations(
            editor_id=setup["editor_id"],
            paper_question_id=pq.id,
            rows=good_allocs,
            rev=1,  # Stale, should be 2
        )


@pytest.mark.django_db
def test_confirm_and_publish_guard(paper_setup):
    setup = paper_setup
    paper = setup["paper"]
    c1 = setup["chapters"][0]

    pq1 = PaperQuestion.objects.create(
        paper=paper,
        label="Q1",
        position=1,
        marks=Decimal("50.0"),
        format="descriptive",
    )
    pq2 = PaperQuestion.objects.create(
        paper=paper,
        label="Q2",
        position=2,
        marks=Decimal("50.0"),
        format="descriptive",
    )

    Allocation.objects.create(
        paper_question=pq1,
        chapter=c1,
        subject=paper.subject,
        scheme=paper.scheme,
        subject_key=paper.subject_key,
        chapter_key=c1.key,
        marks=Decimal("50.0"),
        share=Decimal("1.000"),
        status=Allocation.Status.SUGGESTED,
    )
    Allocation.objects.create(
        paper_question=pq2,
        chapter=c1,
        subject=paper.subject,
        scheme=paper.scheme,
        subject_key=paper.subject_key,
        chapter_key=c1.key,
        marks=Decimal("50.0"),
        share=Decimal("1.000"),
        status=Allocation.Status.SUGGESTED,
    )

    # Trying to publish with 0% confirmed marks -> PaperNotReady
    with pytest.raises(PaperNotReady):
        publish_paper(editor_id=setup["editor_id"], paper_id=paper.id, rev=paper.rev)

    # Confirm Q1 only (50% confirmed) -> still PaperNotReady even with exception note
    confirm_question(editor_id=setup["editor_id"], paper_question_id=pq1.id, rev=pq1.rev)
    paper.refresh_from_db()
    with pytest.raises(PaperNotReady):
        publish_paper(
            editor_id=setup["editor_id"],
            paper_id=paper.id,
            rev=paper.rev,
            exception_note="Partial paper",
        )

    # Confirm Q2 (100% confirmed) -> Publish succeeds!
    confirm_question(editor_id=setup["editor_id"], paper_question_id=pq2.id, rev=pq2.rev)
    paper.refresh_from_db()
    pub_paper = publish_paper(editor_id=setup["editor_id"], paper_id=paper.id, rev=paper.rev)
    assert pub_paper.status == Paper.Status.PUBLISHED
    paper.refresh_from_db()
    assert paper.status == Paper.Status.PUBLISHED

    # Unpublish reverts to unpublished
    un_paper = unpublish_paper(editor_id=setup["editor_id"], paper_id=paper.id, reason="Correction needed")
    assert un_paper.status == Paper.Status.UNPUBLISHED
    paper.refresh_from_db()
    assert paper.status == Paper.Status.UNPUBLISHED


@pytest.mark.django_db
def test_ai_suggestion_job_with_fake_client(paper_setup, monkeypatch):
    setup = paper_setup
    paper = setup["paper"]
    c1, c2 = setup["chapters"][:2]

    pq = PaperQuestion.objects.create(
        paper=paper,
        label="Q1",
        position=1,
        marks=Decimal("10.0"),
        format="descriptive",
        tag_hint="Explain the conditions for claiming input tax credit.",
    )

    # Mock Gemini response
    fake_gemini_response = MagicMock()
    fake_gemini_response.text = f"""{{
        "allocations": [
            {{
                "chapter_key": "{c1.key}",
                "topic_key": null,
                "share": 0.6,
                "confidence": 0.9,
                "rationale": "Directly relates to input tax credit provisions."
            }},
            {{
                "chapter_key": "{c2.key}",
                "topic_key": null,
                "share": 0.4,
                "confidence": 0.85,
                "rationale": "Secondary rules on documentation."
            }}
        ]
    }}"""
    fake_gemini_response.model = "gemini-test"

    monkeypatch.setattr("integrations.gemini.generate_structured", lambda *args, **kwargs: fake_gemini_response)

    # Run suggest job
    res = run_suggest({"paper_id": str(paper.id), "question_ids": [str(pq.id)]})
    assert res["suggested"] == 1
    assert res["invalid"] == 0

    pq.refresh_from_db()
    assert pq.alloc_state == PaperQuestion.AllocState.SUGGESTED
    assert pq.allocations.count() == 2
    assert sum(a.marks for a in pq.allocations.all()) == Decimal("10.0")


@pytest.mark.django_db
def test_ai_suggestion_budget_exceeded(paper_setup, monkeypatch):
    from django.core.cache import cache
    cache.clear()

    setup = paper_setup
    paper = setup["paper"]

    pq = PaperQuestion.objects.create(
        paper=paper,
        label="Q1",
        position=1,
        marks=Decimal("10.0"),
        format="descriptive",
        tag_hint="Question text",
    )

    # Set budget limit to 0
    monkeypatch.setattr("modules.paperanalysis.jobs.DEFAULT_DAILY_AI_BUDGET", 0)

    with pytest.raises(AiBudgetExceeded):
        run_suggest({"paper_id": str(paper.id), "question_ids": [str(pq.id)]})


@pytest.mark.django_db
def test_ai_suggestion_discards_invalid_output(paper_setup, monkeypatch):
    from django.core.cache import cache
    cache.clear()

    setup = paper_setup
    paper = setup["paper"]

    pq = PaperQuestion.objects.create(
        paper=paper,
        label="Q1",
        position=1,
        marks=Decimal("10.0"),
        format="descriptive",
        tag_hint="Question text",
    )

    # Invalid: non-existent chapter key
    fake_gemini_response = MagicMock()
    fake_gemini_response.text = """{
        "allocations": [
            {
                "chapter_key": "non_existent_chapter",
                "share": 1.0,
                "confidence": 0.9,
                "rationale": "Invalid"
            }
        ]
    }"""
    monkeypatch.setattr("integrations.gemini.generate_structured", lambda *args, **kwargs: fake_gemini_response)

    res = run_suggest({"paper_id": str(paper.id), "question_ids": [str(pq.id)]})
    assert res["suggested"] == 0
    assert res["invalid"] == 1
    assert pq.allocations.count() == 0
