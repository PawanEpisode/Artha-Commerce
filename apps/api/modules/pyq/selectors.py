"""
Selectors for F-09 Previous Year Questions (read operations and projections).
Reference: docs/product/erd/F-09-previous-year-questions.md Section 3.2.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import Any

from django.db.models import Prefetch

from modules.practice.selectors import get_question_states

from .models import ChoiceGroup, PaperLink, PaperQuestion, PyqPaper


@dataclass
class PaperCardData:
    id: str
    external_ref: str
    course_code: str
    level_code: str
    subject_key: str
    term_code: str
    title: str
    paper_code: str
    duration_minutes: int | None
    total_marks: str
    delivery: str
    answers_status: str
    syllabus_status: str
    status: str
    question_count: int
    attempted_count: int = 0
    correct_count: int = 0


@dataclass
class PaperQuestionItemData:
    id: str
    parent_id: str | None
    number_label: str
    depth: int
    sort_order: int
    is_leaf: bool
    question_id: str | None
    marks: str
    kind: str
    descriptor: str
    chapter_id: str | None
    chapter_key: str | None
    scheme_relation: str
    answer_source: str
    answer_page_hint: str
    source_page_hint: str
    choice_group_id: str | None
    choice_group_label: str | None
    section_label: str | None
    # User state overlay
    user_state: dict[str, Any] | None = None


def list_papers(
    *,
    course_code: str | None = None,
    level_code: str | None = None,
    subject_key: str | None = None,
    term_code: str | None = None,
    status: str = "published",
    user_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    if user_id and (not course_code or not level_code):
        from modules.coverage import selectors as coverage_selectors

        summary = coverage_selectors.course_summary(user_id)
        if summary:
            course_code = course_code or summary.course_code
            level_code = level_code or summary.level_code

    qs = PyqPaper.objects.select_related("course", "level").filter(status=status)

    if course_code:
        qs = qs.filter(course__code=course_code.lower())
    if level_code:
        qs = qs.filter(level__code=level_code.lower())
    if subject_key:
        qs = qs.filter(subject_key=subject_key)
    if term_code:
        qs = qs.filter(term_code=term_code)

    qs = qs.order_by("-term_code", "paper_code", "title")

    papers_data: list[dict[str, Any]] = []
    for paper in qs:
        card = PaperCardData(
            id=str(paper.id),
            external_ref=paper.external_ref,
            course_code=paper.course.code,
            level_code=paper.level.code,
            subject_key=paper.subject_key,
            term_code=paper.term_code,
            title=paper.title,
            paper_code=paper.paper_code,
            duration_minutes=paper.duration_minutes,
            total_marks=str(paper.total_marks),
            delivery=paper.delivery,
            answers_status=paper.answers_status,
            syllabus_status=paper.syllabus_status,
            status=paper.status,
            question_count=paper.question_count,
        )
        papers_data.append(asdict(card))

    return papers_data


def get_paper_detail(
    paper_id_or_ref: str,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    """Returns full paper breakdown including question tree, choice groups, and links."""
    qs = PyqPaper.objects.select_related("course", "level", "subject", "scheme").prefetch_related(
        Prefetch("choice_groups", queryset=ChoiceGroup.objects.order_by("sort_order")),
        Prefetch("links", queryset=PaperLink.objects.all()),
        Prefetch("questions", queryset=PaperQuestion.objects.select_related("choice_group").order_by("sort_order")),
    )

    try:
        val_uuid = uuid.UUID(str(paper_id_or_ref))
        paper = qs.filter(id=val_uuid).first()
    except (ValueError, AttributeError):
        paper = qs.filter(external_ref=paper_id_or_ref).first()

    if not paper:
        return None

    # Load question states if user_id is provided
    user_states_map: dict[uuid.UUID, Any] = {}
    if user_id:
        leaf_q_ids = [q.question_id for q in paper.questions.all() if q.is_leaf and q.question_id]
        if leaf_q_ids:
            states = get_question_states(user_id, leaf_q_ids)
            user_states_map = {s.question_id: s for s in states}

    questions_data: list[dict[str, Any]] = []
    for q in paper.questions.all():
        u_state = None
        if q.question_id and q.question_id in user_states_map:
            st = user_states_map[q.question_id]
            u_state = {
                "attempts": st.attempts,
                "correct_count": st.correct_count,
                "last_result": st.last_result,
                "bookmarked": st.bookmarked,
                "box": st.box,
            }

        item = PaperQuestionItemData(
            id=str(q.id),
            parent_id=str(q.parent_id) if q.parent_id else None,
            number_label=q.number_label,
            depth=q.depth,
            sort_order=q.sort_order,
            is_leaf=q.is_leaf,
            question_id=str(q.question_id) if q.question_id else None,
            marks=str(q.marks),
            kind=q.kind,
            descriptor=q.descriptor,
            chapter_id=str(q.chapter_id) if q.chapter_id else None,
            chapter_key=q.chapter_key,
            scheme_relation=q.scheme_relation,
            answer_source=q.answer_source,
            answer_page_hint=q.answer_page_hint,
            source_page_hint=q.source_page_hint,
            choice_group_id=str(q.choice_group_id) if q.choice_group_id else None,
            choice_group_label=q.choice_group.label if q.choice_group else None,
            section_label=q.choice_group.section_label if q.choice_group else None,
            user_state=u_state,
        )
        questions_data.append(asdict(item))

    links_data = [
        {
            "id": str(link.id),
            "link_kind": link.link_kind,
            "label": link.label,
            "url": link.url,
            "hosted": link.attachment_id is not None,
            "host": link.host,
            "page_hint": link.page_hint,
            "link_status": link.link_status,
            "verified": link.verified,
        }
        for link in paper.links.all()
    ]

    cg_data = [
        {
            "id": str(cg.id),
            "label": cg.label,
            "rule_kind": cg.rule_kind,
            "pick_count": cg.pick_count,
            "of_count": cg.of_count,
            "section_label": cg.section_label,
            "sort_order": cg.sort_order,
        }
        for cg in paper.choice_groups.all()
    ]

    return {
        "id": str(paper.id),
        "external_ref": paper.external_ref,
        "course_code": paper.course.code,
        "level_code": paper.level.code,
        "subject_key": paper.subject_key,
        "term_code": paper.term_code,
        "title": paper.title,
        "paper_code": paper.paper_code,
        "duration_minutes": paper.duration_minutes,
        "reading_minutes": paper.reading_minutes,
        "total_marks": str(paper.total_marks),
        "marks_note": paper.marks_note,
        "law_note": paper.law_note,
        "delivery": paper.delivery,
        "answers_status": paper.answers_status,
        "syllabus_status": paper.syllabus_status,
        "source_name": paper.source_name,
        "status": paper.status,
        "question_count": paper.question_count,
        "links": links_data,
        "choice_groups": cg_data,
        "questions": questions_data,
    }


def list_chapter_pyqs(
    chapter_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    term_range: str | None = None,
    scheme_relation: str | None = None,
) -> list[dict[str, Any]]:
    """Lists past paper questions that map to a specific chapter."""
    qs = PaperQuestion.objects.select_related("paper", "choice_group").filter(
        chapter_id=chapter_id,
        is_leaf=True,
        question__isnull=False,
        paper__status="published",
    )

    if scheme_relation:
        qs = qs.filter(scheme_relation=scheme_relation)

    qs = qs.order_by("-paper__term_code", "sort_order")

    items: list[dict[str, Any]] = []
    q_ids = [pq.question_id for pq in qs]
    user_states_map = {}
    if user_id and q_ids:
        states = get_question_states(user_id, q_ids)
        user_states_map = {s.question_id: s for s in states}

    for pq in qs:
        u_state = None
        if pq.question_id in user_states_map:
            st = user_states_map[pq.question_id]
            u_state = {
                "attempts": st.attempts,
                "correct_count": st.correct_count,
                "last_result": st.last_result,
                "bookmarked": st.bookmarked,
            }

        items.append(
            {
                "id": str(pq.id),
                "question_id": str(pq.question_id),
                "paper_id": str(pq.paper_id),
                "paper_title": pq.paper.title,
                "term_code": pq.paper.term_code,
                "number_label": pq.number_label,
                "marks": str(pq.marks),
                "kind": pq.kind,
                "descriptor": pq.descriptor,
                "scheme_relation": pq.scheme_relation,
                "answer_source": pq.answer_source,
                "delivery": pq.paper.delivery,
                "user_state": u_state,
            }
        )

    return items


def paper_blueprint(paper_id: uuid.UUID) -> dict[str, Any]:
    """Returns paper blueprint for practice runner and test generators."""
    paper = PyqPaper.objects.prefetch_related("choice_groups", "questions").get(id=paper_id)
    return {
        "paper_id": str(paper.id),
        "external_ref": paper.external_ref,
        "duration_minutes": paper.duration_minutes,
        "total_marks": str(paper.total_marks),
        "choice_groups": [
            {
                "id": str(cg.id),
                "label": cg.label,
                "rule_kind": cg.rule_kind,
                "pick_count": cg.pick_count,
                "of_count": cg.of_count,
            }
            for cg in paper.choice_groups.all()
        ],
        "parts": [
            {
                "id": str(q.id),
                "number_label": q.number_label,
                "marks": str(q.marks),
                "question_id": str(q.question_id) if q.question_id else None,
                "is_leaf": q.is_leaf,
                "choice_group_id": str(q.choice_group_id) if q.choice_group_id else None,
            }
            for q in paper.questions.all().order_by("sort_order")
        ],
    }
