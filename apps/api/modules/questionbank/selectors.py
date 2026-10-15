"""
Question bank read selectors (F-06 ERD 3.2).
Strictly separates PlayableQuestion (no answers) from GradableQuestion / ReviewQuestion.
"""

from __future__ import annotations

import base64
import random
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from django.db.models import Count, Q
from django.utils import timezone

from .domain.filters import QuestionFilter
from .models import (
    CollectionItem,
    Question,
    QuestionTopic,
    QuestionVersion,
    Rubric,
    ShareLink,
)


@dataclass
class Page[T]:
    items: list[T]
    next_cursor: str | None = None
    total: int | None = None


@dataclass
class QuestionCard:
    id: uuid.UUID
    public_id: str
    kind: str
    stem_head: str
    marks: Decimal | None
    difficulty: int | None
    nature: str
    source_name: str
    source_year: int | None
    source_term_code: str
    is_verified: bool
    primary_chapter_id: uuid.UUID | None
    chapter_key: str
    subject_key: str
    tag_slugs: list[str]
    published_at: str | None


@dataclass
class FacetCount:
    value: str | int
    count: int


@dataclass
class PlayableOption:
    id: uuid.UUID
    body_md: str
    pinned: bool


@dataclass
class PlayableQuestion:
    question_id: uuid.UUID
    version_id: uuid.UUID
    version_no: int
    kind: str
    position: int | None
    group: dict[str, Any] | None
    stem_md: str
    marks: Decimal
    negative_applies: bool
    suggested_seconds: int | None
    options: list[PlayableOption]
    numeric: dict[str, Any] | None
    labels: dict[str, Any]
    media: list[dict[str, Any]]
    needs_attention: bool


@dataclass
class GradableQuestion:
    question_id: uuid.UUID
    version_id: uuid.UUID
    kind: str
    marks: Decimal
    negative_marks: Decimal | None
    multi_scoring: str
    correct_option_ids: list[uuid.UUID]
    numeric_key: dict[str, Any] | None
    rubric_id: uuid.UUID | None


@dataclass
class ReviewQuestion:
    question_id: uuid.UUID
    version_id: uuid.UUID
    version_no: int
    kind: str
    position: int | None
    stem_md: str
    marks: Decimal
    negative_marks: Decimal | None
    suggested_seconds: int | None
    options: list[dict[str, Any]]
    correct_option_ids: list[uuid.UUID]
    numeric_key: dict[str, Any] | None
    explanation_md: str
    explanation_source: str
    reference_labels: list[str]
    rubric: dict[str, Any] | None
    labels: dict[str, Any]
    media: list[dict[str, Any]]
    newer_version_available: bool


@dataclass
class Mapping:
    chapter_id: uuid.UUID
    chapter_key: str
    subject_id: uuid.UUID
    subject_key: str
    is_primary: bool
    topic_id: uuid.UUID | None
    status: str


def _apply_filters(qs, viewer_id: uuid.UUID | None, flt: QuestionFilter):
    scope = flt.get("scope", "public")
    if scope == "public":
        qs = qs.filter(visibility=Question.Visibility.PUBLIC, status=Question.Status.ACTIVE)
    elif scope == "mine":
        if not viewer_id:
            return qs.none()
        qs = qs.filter(owner_user_id=viewer_id)
    elif scope == "collection":
        coll_id = flt.get("collection_id")
        if not coll_id:
            return qs.none()
        q_ids = CollectionItem.objects.filter(collection_id=coll_id).values_list("question_id", flat=True)
        qs = qs.filter(id__in=q_ids)

    if flt.get("course"):
        qs = qs.filter(course__code=flt["course"])
    if flt.get("level"):
        qs = qs.filter(level__code=flt["level"])
    if flt.get("subject_key"):
        qs = qs.filter(subject_key=flt["subject_key"])

    if flt.get("chapter_ids"):
        ch_ids = flt["chapter_ids"]
        if flt.get("include_secondary", False):
            matching_q_ids = QuestionTopic.objects.filter(
                chapter_id__in=ch_ids, status=QuestionTopic.Status.CONFIRMED
            ).values_list("question_id", flat=True)
            qs = qs.filter(id__in=matching_q_ids)
        else:
            qs = qs.filter(primary_chapter_id__in=ch_ids)

    if flt.get("topic_id"):
        qs = qs.filter(primary_topic_id=flt["topic_id"])

    if flt.get("kinds"):
        qs = qs.filter(kind__in=flt["kinds"])
    if flt.get("source_kinds"):
        qs = qs.filter(source_kind__in=flt["source_kinds"])
    if flt.get("ownership"):
        qs = qs.filter(ownership__in=flt["ownership"])

    if flt.get("year_from") is not None:
        qs = qs.filter(source_year__gte=flt["year_from"])
    if flt.get("year_to") is not None:
        qs = qs.filter(source_year__lte=flt["year_to"])
    if flt.get("term_codes"):
        qs = qs.filter(source_term_code__in=flt["term_codes"])

    if flt.get("marks_min") is not None:
        qs = qs.filter(marks__gte=flt["marks_min"])
    if flt.get("marks_max") is not None:
        qs = qs.filter(marks__lte=flt["marks_max"])

    if flt.get("difficulty"):
        qs = qs.filter(difficulty__in=flt["difficulty"])
    if flt.get("bloom"):
        qs = qs.filter(bloom__in=flt["bloom"])
    if flt.get("nature"):
        qs = qs.filter(nature__in=flt["nature"])

    if flt.get("verified_only"):
        qs = qs.filter(is_verified=True)

    if flt.get("exclude_ids"):
        qs = qs.exclude(id__in=flt["exclude_ids"])

    if flt.get("q"):
        query = flt["q"]
        qs = qs.filter(Q(search_text__icontains=query) | Q(stem_head__icontains=query))

    return qs


def list_published(
    viewer_id: uuid.UUID | None,
    flt: QuestionFilter,
    *,
    order: str = "newest",
    cursor: str | None = None,
    limit: int = 20,
) -> Page[QuestionCard]:
    """Lists published questions matching QuestionFilter with keyset pagination."""
    qs = Question.objects.select_related("primary_chapter", "primary_subject").filter(
        parent__isnull=True, deleted_at__isnull=True
    )
    qs = _apply_filters(qs, viewer_id, flt)

    if order == "newest":
        qs = qs.order_by("-published_at", "-id")
    elif order == "year_desc":
        qs = qs.order_by("-source_year", "-id")
    elif order == "difficulty":
        qs = qs.order_by("difficulty", "-id")
    else:
        qs = qs.order_by("-id")

    # Cursor decode (offset-based or keyset token)
    offset = 0
    if cursor:
        try:
            offset = int(base64.b64decode(cursor.encode()).decode())
        except Exception:
            offset = 0

    items_qs = list(qs[offset : offset + limit + 1])
    has_next = len(items_qs) > limit
    results = items_qs[:limit]

    cards = [
        QuestionCard(
            id=q.id,
            public_id=q.public_id,
            kind=q.kind,
            stem_head=q.stem_head,
            marks=q.marks,
            difficulty=q.difficulty,
            nature=q.nature,
            source_name=q.source_name,
            source_year=q.source_year,
            source_term_code=q.source_term_code,
            is_verified=q.is_verified,
            primary_chapter_id=q.primary_chapter_id,
            chapter_key=q.chapter_key,
            subject_key=q.subject_key,
            tag_slugs=q.tag_slugs or [],
            published_at=q.published_at.isoformat() if q.published_at else None,
        )
        for q in results
    ]

    next_cursor = None
    if has_next:
        next_cursor = base64.b64encode(str(offset + limit).encode()).decode()

    return Page(items=cards, next_cursor=next_cursor)


def search_ids(
    viewer_id: uuid.UUID | None,
    flt: QuestionFilter,
    *,
    order: Literal["random", "newest", "year_desc", "marks_desc", "difficulty"] = "random",
    seed: int | None = None,
    limit: int = 100,
) -> list[uuid.UUID]:
    """Returns question IDs matching filter for picker resolution (parents of case studies only)."""
    qs = Question.objects.filter(parent__isnull=True, deleted_at__isnull=True)
    qs = _apply_filters(qs, viewer_id, flt)

    ids = list(qs.values_list("id", flat=True)[:2000])
    if not ids:
        return []

    if order == "random":
        rng = random.Random(seed)
        rng.shuffle(ids)
    elif order == "newest":
        ids = list(qs.order_by("-published_at", "-id").values_list("id", flat=True)[:limit])
    elif order == "year_desc":
        ids = list(qs.order_by("-source_year", "-id").values_list("id", flat=True)[:limit])
    elif order == "marks_desc":
        ids = list(qs.order_by("-marks", "-id").values_list("id", flat=True)[:limit])
    elif order == "difficulty":
        ids = list(qs.order_by("difficulty", "-id").values_list("id", flat=True)[:limit])

    return ids[:limit]


def count_matching(viewer_id: uuid.UUID | None, flt: QuestionFilter, *, cap: int = 1000) -> int:
    """Capped count query (Q-3)."""
    qs = Question.objects.filter(parent__isnull=True, deleted_at__isnull=True)
    qs = _apply_filters(qs, viewer_id, flt)
    return min(qs.count(), cap)


def facets(
    viewer_id: uuid.UUID | None,
    flt: QuestionFilter,
    dims: Sequence[str],
) -> dict[str, list[FacetCount]]:
    """Counts matching questions grouped by facet dimensions."""
    qs = Question.objects.filter(parent__isnull=True, deleted_at__isnull=True)
    qs = _apply_filters(qs, viewer_id, flt)

    res: dict[str, list[FacetCount]] = {}
    for dim in dims:
        if dim in ("kind", "difficulty", "source_kind", "source_year", "bloom", "nature"):
            counts = qs.values(dim).annotate(cnt=Count("id")).order_by("-cnt")
            res[dim] = [
                FacetCount(value=row[dim] if row[dim] is not None else "unknown", count=row["cnt"])
                for row in counts
                if row[dim] is not None
            ]
    return res


def can_view(viewer_id: uuid.UUID | None, question_id: uuid.UUID, *, token: str | None = None) -> bool:
    """Visibility rule: true if owner, public+active, valid share link token, or staff."""
    question = Question.objects.filter(id=question_id).first()
    if not question:
        return False

    if viewer_id and question.owner_user_id == viewer_id:
        return True

    if question.visibility == Question.Visibility.PUBLIC and question.status == Question.Status.ACTIVE:
        return True

    if token and question.visibility == Question.Visibility.LINK:
        sl = ShareLink.objects.filter(token=token, revoked_at__isnull=True).first()
        if sl:
            if sl.expires_at and sl.expires_at < timezone.now():
                return False
            if sl.question_id == question_id:
                return True
            if (
                sl.collection_id
                and CollectionItem.objects.filter(collection_id=sl.collection_id, question_id=question_id).exists()
            ):
                return True

    return False


def get_playable(question_id: uuid.UUID, version_id: uuid.UUID | None = None) -> PlayableQuestion:
    """
    Returns PlayableQuestion payload.
    CRITICAL: Never contains is_correct, numeric_value, tolerance, explanation, or rubric!
    """
    question = Question.objects.select_related("parent").get(id=question_id)
    if version_id:
        version = QuestionVersion.objects.get(id=version_id, question=question)
    else:
        version = question.live_version or question.current_version
        if not version:
            raise ValueError(f"Question {question_id} has no version.")

    options = list(version.options.order_by("position").values("id", "body_md", "pinned"))
    playable_opts = [PlayableOption(id=opt["id"], body_md=opt["body_md"], pinned=opt["pinned"]) for opt in options]

    numeric_info = None
    if question.kind == Question.Kind.NUMERIC:
        key = getattr(version, "answer_key", None)
        if key:
            numeric_info = {"unit": key.unit, "unit_required": key.unit_required}

    group_info = None
    if question.parent:
        p_ver = question.parent.live_version or question.parent.current_version
        group_info = {
            "question_id": question.parent.id,
            "stem_md": p_ver.stem_md if p_ver else "",
            "media": [],
        }

    labels = {
        "source_kind": question.source_kind,
        "source_name": question.source_name,
        "source_ref": question.source_ref,
        "source_year": question.source_year,
        "source_term_code": question.source_term_code,
        "difficulty": question.difficulty,
        "nature": question.nature,
        "verified": question.is_verified,
        "ownership": question.ownership,
    }

    return PlayableQuestion(
        question_id=question.id,
        version_id=version.id,
        version_no=version.version_no,
        kind=question.kind,
        position=question.position,
        group=group_info,
        stem_md=version.stem_md,
        marks=version.marks,
        negative_applies=version.negative_marks is not None,
        suggested_seconds=version.suggested_seconds,
        options=playable_opts,
        numeric=numeric_info,
        labels=labels,
        media=[],
        needs_attention=question.needs_attention,
    )


def get_gradables(refs: Sequence[tuple[uuid.UUID, uuid.UUID | None]]) -> dict[uuid.UUID, GradableQuestion]:
    """Returns GradableQuestion items with correct answers for server-side grading."""
    res: dict[uuid.UUID, GradableQuestion] = {}
    for q_id, v_id in refs:
        q = Question.objects.get(id=q_id)
        v = QuestionVersion.objects.get(id=v_id) if v_id else (q.live_version or q.current_version)
        if not v:
            continue

        correct_opt_ids = list(v.options.filter(is_correct=True).values_list("id", flat=True))
        num_key = None
        key = getattr(v, "answer_key", None)
        if key:
            num_key = {
                "numeric_value": key.numeric_value,
                "tolerance_abs": key.tolerance_abs,
                "tolerance_rel": key.tolerance_rel,
                "accepted_values": key.accepted_values,
                "unit": key.unit,
                "unit_required": key.unit_required,
            }

        rubric_id = v.rubric.pk if hasattr(v, "rubric") else None

        res[q_id] = GradableQuestion(
            question_id=q.id,
            version_id=v.id,
            kind=q.kind,
            marks=v.marks,
            negative_marks=v.negative_marks,
            multi_scoring=v.multi_scoring,
            correct_option_ids=correct_opt_ids,
            numeric_key=num_key,
            rubric_id=rubric_id,
        )
    return res


def get_rubric(version_id: uuid.UUID) -> dict[str, Any]:
    """Returns Rubric details for a question version."""
    rubric = Rubric.objects.prefetch_related("steps").get(version_id=version_id)
    steps = [
        {
            "id": step.id,
            "position": step.position,
            "title": step.title,
            "description_md": step.description_md,
            "marks": step.marks,
            "kind": step.kind,
            "mandatory": step.mandatory,
            "partial_allowed": step.partial_allowed,
        }
        for step in rubric.steps.all()
    ]
    return {
        "version_id": rubric.version_id,
        "reference_solution_md": rubric.reference_solution_md,
        "answer_template_md": rubric.answer_template_md,
        "total_marks": rubric.total_marks,
        "steps": steps,
        "keywords": rubric.keywords,
    }


def get_review_view(question_id: uuid.UUID, version_id: uuid.UUID) -> ReviewQuestion:
    """Returns ReviewQuestion payload with answers, explanations, and option feedback."""
    version = QuestionVersion.objects.select_related("question").get(id=version_id, question_id=question_id)
    q = version.question

    opts = list(version.options.order_by("position").values("id", "body_md", "is_correct", "feedback_md", "pinned"))
    correct_opt_ids = [opt["id"] for opt in opts if opt["is_correct"]]

    num_key = None
    if hasattr(version, "answer_key"):
        k = version.answer_key
        num_key = {
            "value": k.numeric_value,
            "tolerance_abs": k.tolerance_abs,
            "tolerance_rel": k.tolerance_rel,
            "unit": k.unit,
        }

    rubric_info = get_rubric(version.id) if hasattr(version, "rubric") else None
    newer_ver = q.live_version_id and q.live_version_id != version.id

    labels = {
        "source_kind": q.source_kind,
        "source_name": q.source_name,
        "source_ref": q.source_ref,
        "source_year": q.source_year,
        "source_term_code": q.source_term_code,
        "difficulty": q.difficulty,
        "nature": q.nature,
        "verified": q.is_verified,
    }

    return ReviewQuestion(
        question_id=q.id,
        version_id=version.id,
        version_no=version.version_no,
        kind=q.kind,
        position=q.position,
        stem_md=version.stem_md,
        marks=version.marks,
        negative_marks=version.negative_marks,
        suggested_seconds=version.suggested_seconds,
        options=opts,
        correct_option_ids=correct_opt_ids,
        numeric_key=num_key,
        explanation_md=version.explanation_md,
        explanation_source=version.explanation_source,
        reference_labels=version.reference_labels,
        rubric=rubric_info,
        labels=labels,
        media=[],
        newer_version_available=bool(newer_ver),
    )


def taxonomy_of(question_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[Mapping]]:
    """Confirmed taxonomy mappings for questions, primary first."""
    topics = QuestionTopic.objects.filter(question_id__in=question_ids, status=QuestionTopic.Status.CONFIRMED).order_by(
        "-is_primary", "chapter_key"
    )

    res: dict[uuid.UUID, list[Mapping]] = {qid: [] for qid in question_ids}
    for t in topics:
        res[t.question_id].append(
            Mapping(
                chapter_id=t.chapter_id,
                chapter_key=t.chapter_key,
                subject_id=t.subject_id,
                subject_key=t.subject_key,
                is_primary=t.is_primary,
                topic_id=t.topic_id,
                status=t.status,
            )
        )
    return res
