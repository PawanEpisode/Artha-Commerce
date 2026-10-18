"""
MCQ Bank read selectors (F-05 ERD 3.2, 5).
Optimized, indexed reads. Strict zero-answer-leakage guarantee.
"""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Sequence
from typing import Any

from django.db.models import Q
from django.utils import timezone

from modules.coverage import selectors as coverage_selectors
from modules.practice import selectors as practice_selectors
from modules.questionbank import selectors as qb_selectors
from modules.syllabus import selectors as syllabus_selectors
from modules.syllabus.models import Chapter

from .domain.blueprint import allocate_quotas
from .domain.pattern import resolve_pattern_profile
from .domain.suggest import ChapterMetrics, rank_suggestions
from .models import ExternalLog, McqSet, PatternProfile, RefSource, TestPreset


def enrolled_course_level(user_id: uuid.UUID) -> tuple[str, str]:
    """The course and level the student is working on (CMA Intermediate when nothing is set)."""
    summary = coverage_selectors.course_summary(user_id)
    return (
        summary.course_code if summary else "cma",
        summary.level_code if summary else "intermediate",
    )


def home(user_id: uuid.UUID) -> dict[str, Any]:
    """Returns MCQ Home view: suggestion, open sessions, due count, subject cards."""
    summary = coverage_selectors.course_summary(user_id)
    course_code = summary.course_code if summary else "cma"
    level_code = summary.level_code if summary else "intermediate"

    level = syllabus_selectors.get_level(course_code, level_code)
    scheme = syllabus_selectors.get_current_scheme(level) if level else None
    subjects = list(syllabus_selectors.list_subjects(scheme)) if scheme else []
    subject_cards = []

    for s in subjects:
        total_mcqs = qb_selectors.count_matching(
            user_id,
            {"subject_key": s.key, "kind_groups": ["choice"]},
        )
        subject_cards.append(
            {
                "code": s.key,
                "name": s.name,
                "paper_number": getattr(s, "paper_number", None),
                "total_mcqs": total_mcqs,
            }
        )

    open_sessions_page = practice_selectors.list_sessions(
        user_id,
        status="open",
        limit=5,
    )
    open_sessions = [
        {
            "id": str(s.id),
            "title": s.title,
            "mode": s.mode,
            "status": s.status,
            "question_count": s.question_count,
            "created_at": s.created_at,
        }
        for s in open_sessions_page.items
    ]

    suggestion = suggest_quick_set(user_id, count=10)

    return {
        "course": course_code,
        "level": level_code,
        "subjects": subject_cards,
        "open_sessions": open_sessions,
        "suggestion": suggestion,
    }


def chapter_tiles(
    user_id: uuid.UUID,
    subject_key: str,
    *,
    course: str = "cma",
    level: str = "intermediate",
) -> list[dict[str, Any]]:
    """Returns progress tiles for all chapters in a subject."""
    subject = syllabus_selectors.get_subject_by_keys(course, level, subject_key)
    if not subject:
        return []
    chapters = list(syllabus_selectors.list_chapters(subject))
    if not chapters:
        return []

    chapter_ids = [c.id for c in chapters]
    progress_map = practice_selectors.progress_by_chapter(user_id, chapter_ids)

    tiles = []
    for c in chapters:
        prog = progress_map.get(c.id)
        available = qb_selectors.count_matching(
            user_id,
            {"chapter_id": c.id, "kind_groups": ["choice"]},
        )
        attempted = prog.attempted if prog else 0
        unseen = max(0, available - attempted)
        wrong = prog.wrong_last if prog else 0
        due = prog.due if prog else 0
        bookmarked = prog.bookmarked if prog else 0

        tiles.append(
            {
                "chapter_id": str(c.id),
                "chapter_key": c.key,
                "name": c.name,
                "section": getattr(c, "section", ""),
                "available": available,
                "unseen": unseen,
                "wrong_last": wrong,
                "bookmarked": bookmarked,
                "due": due,
                "accuracy_recent": (
                    round((prog.correct_last / prog.attempted) * 100.0, 1) if prog and prog.attempted > 0 else None
                ),
                "last_practised_at": str(prog.last_attempt_at) if prog and prog.last_attempt_at else None,
            }
        )
    return tiles


def chapter_detail(
    user_id: uuid.UUID,
    subject_key: str,
    chapter_key: str,
    *,
    course: str = "cma",
    level: str = "intermediate",
) -> dict[str, Any]:
    """Returns chapter details: topics with counts, difficulty split, and published sets."""
    chapter = syllabus_selectors.get_chapter_by_keys(
        course_code=course, level_code=level, subject_key=subject_key, chapter_key=chapter_key
    )
    if not chapter:
        return {}

    topics = list(syllabus_selectors.list_topics(chapter))
    topic_cards = []
    for t in topics:
        cnt = qb_selectors.count_matching(
            user_id,
            {"topic_id": t.id, "kind_groups": ["choice"]},
        )
        topic_cards.append(
            {
                "id": str(t.id),
                "code": t.key,
                "name": t.name,
                "count": cnt,
            }
        )

    # Difficulty split
    easy = qb_selectors.count_matching(
        user_id, {"chapter_id": chapter.id, "difficulty": [2], "kind_groups": ["choice"]}
    )
    med = qb_selectors.count_matching(user_id, {"chapter_id": chapter.id, "difficulty": [3], "kind_groups": ["choice"]})
    hard = qb_selectors.count_matching(
        user_id, {"chapter_id": chapter.id, "difficulty": [5], "kind_groups": ["choice"]}
    )

    # Sets in this chapter
    sets = list_sets(user_id, subject_key=subject_key, chapter_key=chapter_key).get("items", [])

    return {
        "chapter_id": str(chapter.id),
        "chapter_key": chapter.key,
        "name": chapter.name,
        "section": getattr(chapter, "section", ""),
        "topics": topic_cards,
        "difficulty_split": {"easy": easy, "medium": med, "hard": hard},
        "sets": sets,
    }


def suggest_quick_set(
    user_id: uuid.UUID,
    *,
    course_id: uuid.UUID | None = None,
    count: int = 10,
    exclude_chapter_ids: Sequence[uuid.UUID] = (),
) -> dict[str, Any] | None:
    """Ranks chapters for quick-start recommendation."""
    summary = coverage_selectors.course_summary(user_id)
    course_code = summary.course_code if summary else "cma"
    level_code = summary.level_code if summary else "intermediate"

    chapters = list(
        Chapter.objects.filter(
            subject__scheme__level__course__code=course_code,
            subject__scheme__level__code=level_code,
            subject__scheme__status="published",
        )
        .exclude(id__in=exclude_chapter_ids)
        .order_by("sort_order")[:30]
    )
    if not chapters:
        chapters = list(
            Chapter.objects.filter(
                subject__scheme__level__course__code=course_code,
                subject__scheme__level__code=level_code,
            )
            .exclude(id__in=exclude_chapter_ids)
            .order_by("sort_order")[:30]
        )
    if not chapters:
        return None

    ch_ids = [c.id for c in chapters]
    progress_map = practice_selectors.progress_by_chapter(user_id, ch_ids)
    coverage_map = coverage_selectors.coverage_pct_by_chapter(user_id, ch_ids)

    now = timezone.now()
    metrics_list = []
    for idx, c in enumerate(chapters):
        prog = progress_map.get(c.id)
        avail = qb_selectors.count_matching(user_id, {"chapter_id": c.id, "kind_groups": ["choice"]})
        attempted = prog.attempted if prog else 0
        unseen = max(0, avail - attempted)
        wrong = prog.wrong_last if prog else 0
        due = prog.due if prog else 0
        cov_pct = coverage_map.get(c.id, 0.0)
        last_at = prog.last_attempt_at if prog else None
        practised_24h = bool(last_at and (now - last_at).total_seconds() < 86400)

        metrics_list.append(
            ChapterMetrics(
                chapter_id=str(c.id),
                subject_key=c.subject.key if c.subject else "",
                chapter_key=c.key,
                available=avail,
                wrong_last=wrong,
                due=due,
                unseen=unseen,
                coverage_pct=float(cov_pct),
                practised_last_24h=practised_24h,
                syllabus_order=idx,
            )
        )

    best = rank_suggestions(metrics_list)
    if not best:
        return None

    return {
        "chapter_id": best.chapter_id,
        "subject_key": best.subject_key,
        "chapter_key": best.chapter_key,
        "reasons": best.reasons,
        "score": best.score,
        "spec": {
            "v": 1,
            "subject_key": best.subject_key,
            "chapters": [{"chapter_id": best.chapter_id, "n": count}],
            "count": count,
            "mix": "smart",
        },
    }


def list_sets(
    viewer_id: uuid.UUID | None,
    *,
    subject_key: str | None = None,
    chapter_key: str | None = None,
    kind: str | None = None,
    term_code: str | None = None,
    delivery: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Returns published MCQ sets matching filters."""
    qs = McqSet.objects.filter(status=McqSet.Status.PUBLISHED).order_by("sort_order", "title")
    if subject_key:
        qs = qs.filter(subject_key=subject_key)
    if chapter_key:
        qs = qs.filter(chapter_key=chapter_key)
    if kind:
        qs = qs.filter(set_kind=kind)
    if term_code:
        qs = qs.filter(term_code=term_code)
    if delivery:
        qs = qs.filter(delivery=delivery)

    items = list(qs[: limit + 1])
    has_next = len(items) > limit
    results = items[:limit]

    return {
        "items": [
            {
                "id": str(s.id),
                "slug": s.slug,
                "title": s.title,
                "description": s.description,
                "set_kind": s.set_kind,
                "delivery": s.delivery,
                "source_name": s.source_name,
                "source_url": s.source_url if s.delivery == McqSet.Delivery.LINK_OUT else "",
                "subject_key": s.subject_key,
                "chapter_key": s.chapter_key,
                "term_code": s.term_code,
                "question_count": s.question_count,
                "est_minutes": s.est_minutes,
                "verified": s.verified,
                "featured": s.featured,
            }
            for s in results
        ],
        "has_next": has_next,
    }


def get_set(viewer_id: uuid.UUID | None, slug: str) -> dict[str, Any]:
    """Returns full details of one MCQ set."""
    s = McqSet.objects.get(slug=slug, status=McqSet.Status.PUBLISHED)
    return {
        "id": str(s.id),
        "slug": s.slug,
        "title": s.title,
        "description": s.description,
        "set_kind": s.set_kind,
        "delivery": s.delivery,
        "collection_id": str(s.collection_id) if s.collection_id else None,
        "source_name": s.source_name,
        "source_url": s.source_url,
        "source_ref": s.source_ref,
        "subject_key": s.subject_key,
        "chapter_key": s.chapter_key,
        "term_code": s.term_code,
        "question_count": s.question_count,
        "est_minutes": s.est_minutes,
        "verified": s.verified,
        "published_at": s.published_at.isoformat() if s.published_at else None,
    }


def resolve_pattern(
    course: str,
    level: str,
    subject_key: str,
    on: datetime.date,
    scheme_id: uuid.UUID | None = None,
) -> PatternProfile | None:
    """Resolves active, verified pattern profile for a paper and date."""
    profiles = list(
        PatternProfile.objects.filter(
            course__code=course,
            level__code=level,
            subject_key=subject_key,
            status=PatternProfile.Status.ACTIVE,
            verified=True,
        )
    )
    return resolve_pattern_profile(profiles, on, scheme_id=scheme_id)


def preview_blueprint(user_id: uuid.UUID, spec: dict) -> dict[str, Any]:
    """Validates blueprint spec and calculates allocated quotas without creating a session."""
    chapters = spec.get("chapters", [])
    subject_key = spec.get("subject_key")
    count = int(spec.get("count", 20))

    if chapters:
        ch_keys = [str(c.get("chapter_id") or c.get("chapter_key")) for c in chapters]
        weights = [1.0 for _ in chapters]
        availabilities = [
            qb_selectors.count_matching(user_id, {"chapter_id": c.get("chapter_id"), "kind_groups": ["choice"]})
            if c.get("chapter_id")
            else 20
            for c in chapters
        ]
        quotas = allocate_quotas(count, ch_keys, weights, availabilities)
    elif subject_key:
        ch_objs = list(Chapter.objects.filter(subject__key=subject_key).order_by("sort_order"))
        ch_keys = [str(c.id) for c in ch_objs]
        weights = [float(c.marks_max or c.marks_min or 5) for c in ch_objs]
        availabilities = [
            qb_selectors.count_matching(user_id, {"chapter_id": c.id, "kind_groups": ["choice"]}) for c in ch_objs
        ]
        quotas = allocate_quotas(count, ch_keys, weights, availabilities)
    else:
        quotas = {}

    return {
        "total_requested": count,
        "total_allocated": sum(quotas.values()),
        "quotas": quotas,
    }


def list_presets(user_id: uuid.UUID) -> list[dict[str, Any]]:
    """Returns system presets and the student's saved presets."""
    presets = TestPreset.objects.filter(
        Q(is_system=True) | Q(user_id=user_id),
        deleted_at__isnull=True,
    ).order_by("sort_order", "-last_used_at")

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "is_system": p.is_system,
            "kind": p.kind,
            "mode": p.mode,
            "picker": p.picker,
            "spec": p.spec,
            "time_limit_seconds": p.time_limit_seconds,
            "scoring_profile": p.scoring_profile,
            "use_count": p.use_count,
            "last_used_at": p.last_used_at.isoformat() if p.last_used_at else None,
        }
        for p in presets
    ]


def external_log(
    user_id: uuid.UUID,
    *,
    cursor: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Returns self-reported external logs for the user."""
    logs = list(
        ExternalLog.objects.filter(user_id=user_id, deleted_at__isnull=True)
        .order_by("-taken_on", "-created_at")
        .select_related("set")[: limit + 1]
    )
    has_next = len(logs) > limit
    results = logs[:limit]

    return {
        "items": [
            {
                "id": str(log_item.id),
                "set_id": str(log_item.set_id),
                "set_title": log_item.set.title,
                "taken_on": log_item.taken_on.isoformat(),
                "score": str(log_item.score),
                "max_score": str(log_item.max_score),
                "score_pct": float(log_item.score_pct),
            }
            for log_item in results
        ],
        "has_next": has_next,
    }


def reference_sources() -> list[dict[str, Any]]:
    """Returns active reference sources."""
    sources = RefSource.objects.filter(status="active").order_by("prefix")
    return [
        {
            "prefix": s.prefix,
            "label": s.label,
            "url_kind": s.url_kind,
            "url_template": s.url_template,
        }
        for s in sources
    ]
