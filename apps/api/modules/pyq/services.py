"""
Services for F-09 Previous Year Questions (writes, imports, paper lifecycle, practice start).
Reference: docs/product/erd/F-09-previous-year-questions.md Section 3.2.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.events import emit_domain_event
from modules.practice.services import create_session_from_items
from modules.questionbank.domain.payload import QuestionPayload
from modules.questionbank.services import upsert_from_source
from modules.syllabus.models import Chapter, Course, Level, Scheme, Subject

from .domain.importer import SchemaError, validate_paper_payload
from .domain.marks import validate_marks_tree
from .models import ChoiceGroup, PaperLink, PaperQuestion, PyqPaper

# A timed run of a paper that does not record its own duration. The paper page tells students the same number.
DEFAULT_PAPER_DURATION_MINUTES = 180


@dataclass
class ImportReport:
    paper: PyqPaper | None
    created_questions: int
    is_valid: bool
    issues: list[str]
    # How each leaf question was written: {"created": n, "new_version": n, "unchanged": n, "merged_duplicate": n}.
    outcomes: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PublishIssue:
    code: str
    message: str


def check_publish(paper_id: uuid.UUID) -> list[str]:
    """
    Checks paper readiness for publication:
    - All leaf parts must have an associated Question in questionbank.
    - Delivery hosted must have rights_basis.
    - Marks tree and choice groups must validate without error.
    """
    issues: list[str] = []
    paper = PyqPaper.objects.prefetch_related("questions", "choice_groups", "links").get(id=paper_id)

    leaf_parts = [q for q in paper.questions.all() if q.is_leaf]
    if not leaf_parts:
        issues.append("Paper has no question parts.")

    for q in leaf_parts:
        if not q.question_id:
            issues.append(f"Leaf part Q.{q.number_label} has no associated questionbank question.")

    if paper.delivery == PyqPaper.Delivery.HOSTED and not paper.rights_basis:
        issues.append("Hosted paper must declare a valid rights_basis.")

    # Re-validate marks tree
    parts_data = [
        {
            "id": str(q.id),
            "number_label": q.number_label,
            "parent_id": str(q.parent_id) if q.parent_id else None,
            "marks": q.marks,
            "choice_group_id": str(q.choice_group_id) if q.choice_group_id else None,
        }
        for q in paper.questions.all()
    ]
    cg_data = [
        {
            "id": str(cg.id),
            "label": cg.label,
            "rule_kind": cg.rule_kind,
            "pick_count": cg.pick_count,
            "of_count": cg.of_count,
        }
        for cg in paper.choice_groups.all()
    ]
    marks_issues = validate_marks_tree(
        parts_data,
        paper.total_marks,
        marks_note=paper.marks_note,
        choice_groups=cg_data,
    )
    issues.extend(marks_issues)

    return issues


@transaction.atomic
def import_paper(
    editor_id: uuid.UUID,
    payload: dict[str, Any],
    *,
    dry_run: bool = False,
) -> ImportReport:
    """
    Imports a paper from artha.paper.v1 specification (F-09 ERD 3.2).
    Idempotent on external_ref.
    Creates or updates F-06 questions via questionbank.services.upsert_from_source.
    """
    issues = validate_paper_payload(payload)
    if issues:
        raise SchemaError(issues)

    if dry_run:
        return ImportReport(paper=None, created_questions=0, is_valid=True, issues=[])

    course = Course.objects.get(code=payload["course_code"].lower())
    level = Level.objects.get(course=course, code=payload["level_code"].lower())
    subject = Subject.objects.filter(scheme__level=level, key=payload["subject_key"]).first()
    scheme = (
        Scheme.objects.filter(level=level, status=Scheme.Status.PUBLISHED).first()
        or Scheme.objects.filter(level=level).first()
    )

    external_ref = payload["external_ref"]
    delivery = payload.get("delivery", PyqPaper.Delivery.LINK_OUT)
    rights_basis = payload.get("rights_basis") or ""
    total_marks = Decimal(str(payload.get("total_marks", 100.0)))

    paper, _ = PyqPaper.objects.update_or_create(
        external_ref=external_ref,
        defaults={
            "course": course,
            "level": level,
            "subject_key": payload["subject_key"],
            "subject": subject,
            "scheme": scheme,
            "term_code": payload["term_code"],
            "exam_date": payload.get("exam_date"),
            "variant": payload.get("variant", ""),
            "title": payload["title"],
            "paper_code": payload.get("paper_code", ""),
            "duration_minutes": payload.get("duration_minutes", 180),
            "reading_minutes": payload.get("reading_minutes", 0),
            "total_marks": total_marks,
            "marks_note": payload.get("marks_note", ""),
            "law_note": payload.get("law_note", ""),
            "delivery": delivery,
            "rights_basis": rights_basis,
            "permission_ref": payload.get("permission_ref", ""),
            "source_name": payload.get("source_name", ""),
            "answers_status": payload.get("answers_status", PyqPaper.AnswersStatus.NONE),
            "created_by": editor_id,
        },
    )

    # Clean previous children on re-import
    # Hosted PDFs are published by `publish_pyq_pdfs`, not carried by the payload: a re-import keeps them.
    paper.links.filter(attachment_id__isnull=True).delete()
    paper.choice_groups.all().delete()
    paper.questions.all().delete()

    # 1. Create Links
    for link in payload.get("links", []):
        PaperLink.objects.create(
            paper=paper,
            link_kind=link.get("link_kind", PaperLink.LinkKind.PAPER),
            label=link.get("label", ""),
            url=link["url"],
            host=link.get("host", ""),
            page_hint=link.get("page_hint", ""),
        )
    if paper.links.filter(attachment_id__isnull=False).exists() and paper.delivery != PyqPaper.Delivery.HOSTED:
        paper.delivery = PyqPaper.Delivery.HOSTED
        paper.rights_basis = paper.rights_basis or PyqPaper.RightsBasis.INSTITUTE_MATERIAL
        paper.save(update_fields=["delivery", "rights_basis"])

    # 2. Create ChoiceGroups
    cg_ref_map: dict[str, ChoiceGroup] = {}
    for cg_data in payload.get("choice_groups", []):
        cg = ChoiceGroup.objects.create(
            paper=paper,
            label=cg_data["label"],
            rule_kind=cg_data.get("rule_kind", ChoiceGroup.RuleKind.COMPULSORY),
            pick_count=int(cg_data.get("pick_count", 1)),
            of_count=int(cg_data.get("of_count", 1)),
            section_label=cg_data.get("section_label", ""),
            sort_order=int(cg_data.get("sort_order", 0)),
        )
        ref = cg_data.get("ref") or cg_data.get("label")
        cg_ref_map[ref] = cg

    # 3. Create PaperQuestions and underlying QuestionBank items
    part_ref_map: dict[str, PaperQuestion] = {}
    created_leaf_count = 0
    outcomes: Counter[str] = Counter()
    warnings: list[str] = []

    for p in payload.get("parts", []):
        is_leaf = bool(p.get("is_leaf", True))
        marks = Decimal(str(p.get("marks", 0)))
        number_label = str(p.get("number_label"))
        depth = int(p.get("depth", 0))
        sort_order = int(p.get("sort_order", 0))
        kind = p.get("kind", "long_form")
        descriptor = p.get("descriptor", "")
        ch_key = p.get("chapter_key") or ""
        chapter = Chapter.objects.filter(subject=subject, key=ch_key).first() if (subject and ch_key) else None

        cg_ref = p.get("choice_group_ref")
        choice_group = cg_ref_map.get(cg_ref) if cg_ref else None

        question = None
        if is_leaf:
            created_leaf_count += 1
            # Build F-06 Question payload
            q_ext_ref = f"{external_ref}:{p.get('ref_suffix') or number_label}"
            stem_md = p.get("stem_md")
            if not stem_md:
                # Link-out descriptor stub
                src_name = paper.source_name or "Institute"
                stem_md = (
                    f"**{descriptor or f'Question {number_label}'}**\n\n"
                    f"*(Refer to official {src_name} question paper for original figures & text)*"
                )

            options_data = p.get("options") or []
            rubric_data = p.get("rubric")
            if not rubric_data and kind in ("long_form", "practical"):
                ref_sol = (
                    p.get("reference_solution_md")
                    or f"Refer to official {paper.source_name or 'Institute'} suggested answers {p.get('answer_page_hint', '')}".strip()
                )
                rubric_data = {
                    "reference_solution_md": ref_sol,
                    "steps": [
                        {
                            "position": 0,
                            "title": "Complete solution and working notes",
                            "description_md": "Self-assess against official suggested answer guidelines.",
                            "marks": float(marks),
                            "kind": "concept",
                            "mandatory": True,
                            "partial_allowed": True,
                        }
                    ],
                }

            q_payload: QuestionPayload = {
                "kind": kind,
                "stem_md": stem_md,
                "marks": float(marks),
                "options": options_data,
                "rubric": rubric_data,
                "explanation_md": p.get("explanation_md", ""),
                "explanation_source": p.get("answer_source", ""),
                "labels": {
                    "source_kind": "institute_pyq",
                    "source_name": paper.source_name,
                    "source_ref": external_ref,
                    "source_term_code": paper.term_code,
                    "tags": ["institute_pyq", f"term:{paper.term_code}"]
                    + (["pyq_stub"] if not p.get("stem_md") else []),
                    # None lets the question bank estimate it (domain/difficulty.py) instead of stamping everything "medium".
                    "difficulty": p.get("difficulty"),
                    "source_year": int(paper.term_code[:4]) if paper.term_code[:4].isdigit() else None,
                },
            }
            if p.get("numeric_key"):
                q_payload["numeric_key"] = p["numeric_key"]
            if ch_key:
                q_payload["mapping"] = [
                    {
                        "course": payload["course_code"].lower(),
                        "level": payload["level_code"].lower(),
                        "subject_key": payload["subject_key"],
                        "chapter_key": ch_key,
                        "primary": True,
                    }
                ]

            upsert_res = upsert_from_source(
                origin_module="pyq",
                external_ref=q_ext_ref,
                payload=q_payload,
                ownership="platform",
                rights_status=rights_basis or "institute_material",
                actor_id=editor_id,
                # A part the transcriber was unsure about stays a private draft; the rest go live with the paper.
                auto_publish=bool(p.get("publish", True)),
                mapping_confidence=p.get("mapping_confidence"),
            )
            question = upsert_res.canonical
            outcomes[upsert_res.outcome] += 1
            if upsert_res.duplicate_of is not None:
                outcomes["merged_duplicate"] += 1
            warnings.extend(f"Q.{number_label}: {w}" for w in upsert_res.warnings)

        pq = PaperQuestion.objects.create(
            paper=paper,
            number_label=number_label,
            depth=depth,
            sort_order=sort_order,
            is_leaf=is_leaf,
            question=question,
            marks=marks,
            choice_group=choice_group,
            kind=kind,
            descriptor=descriptor,
            chapter=chapter,
            chapter_key=ch_key[
                :80
            ],  # the column is 80 wide; some syllabus keys are longer, the chapter FK carries the link
            mapping_state=(
                PaperQuestion.MappingState.CONFIRMED
                if chapter and p.get("mapping_state", "confirmed") == "confirmed"
                else PaperQuestion.MappingState.PENDING
            ),
            scheme_relation=PaperQuestion.SchemeRelation.CURRENT if scheme else PaperQuestion.SchemeRelation.UNMAPPED,
            answer_source=p.get("answer_source", PaperQuestion.AnswerSource.NONE),
            answer_page_hint=p.get("answer_page_hint", ""),
            source_page_hint=p.get("source_page_hint", ""),
        )
        ref = p.get("ref") or number_label
        part_ref_map[ref] = pq

    # 4. Link parents in tree
    for p in payload.get("parts", []):
        parent_ref = p.get("parent_ref")
        if parent_ref and parent_ref in part_ref_map:
            ref = p.get("ref") or str(p.get("number_label"))
            child_pq = part_ref_map.get(ref)
            if child_pq:
                child_pq.parent = part_ref_map[parent_ref]
                child_pq.save(update_fields=["parent"])

    paper.question_count = created_leaf_count
    paper.save(update_fields=["question_count", "updated_at"])

    return ImportReport(
        paper=paper,
        created_questions=created_leaf_count,
        is_valid=True,
        issues=[],
        outcomes=dict(outcomes),
        warnings=warnings,
    )


@transaction.atomic
def publish_paper(editor_id: uuid.UUID, paper_id: uuid.UUID) -> PyqPaper:
    """Publishes a paper after validating publish readiness."""
    issues = check_publish(paper_id)
    if issues:
        raise ValueError("; ".join(issues))

    paper = PyqPaper.objects.select_for_update().get(id=paper_id)
    now = timezone.now()
    paper.status = PyqPaper.Status.PUBLISHED
    paper.published_at = now
    paper.save(update_fields=["status", "published_at", "updated_at"])

    leaf_q_ids = list(
        paper.questions.filter(is_leaf=True, question__isnull=False).values_list("question_id", flat=True)
    )

    emit_domain_event(
        "pyq_paper_published",
        {
            "paper_id": str(paper.id),
            "level_id": str(paper.level_id),
            "subject_key": paper.subject_key,
            "term_code": paper.term_code,
            "syllabus_status": paper.syllabus_status,
            "leaf_question_ids": [str(q_id) for q_id in leaf_q_ids],
        },
        actor_id=editor_id,
        key=f"pyq_pub:{paper.id}",
    )

    return paper


@transaction.atomic
def withdraw_paper(
    actor_id: uuid.UUID,
    paper_id: uuid.UUID,
    reason: str,
    *,
    replaced_by: uuid.UUID | None = None,
) -> PyqPaper:
    """Withdraws a paper."""
    paper = PyqPaper.objects.select_for_update().get(id=paper_id)
    paper.status = PyqPaper.Status.WITHDRAWN
    paper.withdrawn_reason = reason
    if replaced_by:
        paper.replaced_by_id = replaced_by
    paper.save(update_fields=["status", "withdrawn_reason", "replaced_by", "updated_at"])

    emit_domain_event(
        "pyq_paper_withdrawn",
        {
            "paper_id": str(paper.id),
            "reason": reason,
            "replaced_by": str(replaced_by) if replaced_by else None,
        },
        actor_id=actor_id,
        key=f"pyq_wdr:{paper.id}",
    )
    return paper


@transaction.atomic
def start_paper_session(
    user_id: uuid.UUID,
    paper_id: uuid.UUID,
    *,
    mode: str = "untimed",
    client_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Launches an F-06 practice session for an entire past paper.
    Orders leaf items in printed sort order with frozen marks.
    """
    paper = PyqPaper.objects.get(id=paper_id)
    leaf_pqs = (
        paper.questions.filter(is_leaf=True, question__isnull=False).order_by("sort_order").select_related("question")
    )
    items = [{"question_id": str(pq.question_id), "marks": float(pq.marks)} for pq in leaf_pqs]
    if not items:
        raise ValueError("Paper has no playable questions.")

    time_limit = (paper.duration_minutes or DEFAULT_PAPER_DURATION_MINUTES) * 60 if mode == "timed" else None

    session = create_session_from_items(
        user_id=user_id,
        items=items,
        origin_module="pyq",
        origin_ref=str(paper.id),
        mode="timed" if mode == "timed" else "untimed",
        title=paper.title,
        time_limit_seconds=time_limit,
        # A timed paper is the exam: the clock does not stop for the student.
        config={"allow_pause": False} if mode == "timed" else None,
        feedback_policy="at_end",
        scoring_profile="official",
        client_id=client_id or uuid.uuid4(),
    )

    return {
        "session_id": str(session.session_id),
        "status": session.status,
        "mode": session.mode,
        "question_count": session.question_count,
        "total_marks": str(session.total_marks),
    }


@transaction.atomic
def start_chapter_session(
    user_id: uuid.UUID,
    chapter_id: uuid.UUID,
    *,
    count: int = 10,
    client_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Launches an F-06 practice session for past paper questions of a specific chapter.
    """
    chapter = Chapter.objects.get(id=chapter_id)
    pqs = (
        PaperQuestion.objects.filter(
            chapter=chapter,
            is_leaf=True,
            question__isnull=False,
            paper__status=PyqPaper.Status.PUBLISHED,
        )
        .order_by("-paper__term_code", "sort_order")
        .values_list("question_id", flat=True)[:count]
    )
    question_ids = list(pqs)
    if not question_ids:
        raise ValueError(f"No past paper questions found for chapter '{chapter.name}'.")

    items = [{"question_id": str(q_id)} for q_id in question_ids]
    session = create_session_from_items(
        user_id=user_id,
        items=items,
        origin_module="pyq",
        origin_ref=f"chapter:{chapter.id}",
        mode="chapter_quiz",
        title=f"PYQs: {chapter.name}",
        feedback_policy="instant",
        scoring_profile="practice",
        client_id=client_id or uuid.uuid4(),
    )

    return {
        "session_id": str(session.session_id),
        "status": session.status,
        "mode": session.mode,
        "question_count": session.question_count,
        "total_marks": str(session.total_marks),
    }
