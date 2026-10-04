"""Write operations: publish and retire schemes, chapter maps, reports, and the idempotent seed loader."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    Chapter,
    ChapterMap,
    Course,
    ExamTerm,
    Level,
    Scheme,
    Subject,
    SyllabusGroup,
    SyllabusReport,
    Topic,
)


class SchemeStateError(ValidationError):
    """The requested publish or retire is not allowed in the scheme's current state."""


# --- publish and retire ----------------------------------------------------------------------


def _window(scheme: Scheme) -> tuple[str, str]:
    """Applicability window as comparable strings ('' = open start, '~' = open end). Term codes sort as YYYY-MM."""
    start = scheme.from_term.code if scheme.from_term_id else ""
    end = scheme.to_term.code if scheme.to_term_id else "~"
    return start, end


def _overlaps(a: Scheme, b: Scheme) -> bool:
    a_start, a_end = _window(a)
    b_start, b_end = _window(b)
    return a_start <= b_end and b_start <= a_end


@transaction.atomic
def publish_scheme(scheme: Scheme) -> Scheme:
    """Make a draft scheme visible. At most one published scheme per level may cover a given term (FR-4, FR-8)."""
    if scheme.status == Scheme.Status.PUBLISHED:
        return scheme
    if scheme.status == Scheme.Status.RETIRED:
        raise SchemeStateError("A retired scheme cannot be published again. Create a new scheme instead.")
    if not scheme.subjects.filter(is_active=True).exists():
        raise SchemeStateError("A scheme needs at least one subject before it can be published.")
    others = scheme.level.schemes.filter(status=Scheme.Status.PUBLISHED).select_related("from_term", "to_term")
    for other in others:
        if _overlaps(scheme, other):
            raise SchemeStateError(
                f"Scheme {other.code} is already published for an overlapping set of terms. Retire it or narrow the term window first."
            )
    scheme.status = Scheme.Status.PUBLISHED
    scheme.published_at = timezone.now()
    scheme.save(update_fields=["status", "published_at", "updated_at"])
    return scheme


@transaction.atomic
def retire_scheme(scheme: Scheme) -> Scheme:
    """Retiring hides a scheme from new students; nothing is deleted, enrolled students keep reading it."""
    if scheme.status != Scheme.Status.PUBLISHED:
        raise SchemeStateError("Only a published scheme can be retired.")
    scheme.status = Scheme.Status.RETIRED
    scheme.save(update_fields=["status", "updated_at"])
    return scheme


# --- chapter mapping between schemes ---------------------------------------------------------


@transaction.atomic
def build_default_chapter_map(old_scheme: Scheme, new_scheme: Scheme) -> int:
    """Creates `same` rows for chapters with the same subject key and chapter key. Editors adjust the rest."""
    if old_scheme.level_id != new_scheme.level_id:
        raise ValidationError("Schemes must belong to the same level.")
    new_chapters = {
        (c.subject.key, c.key): c
        for c in Chapter.objects.filter(subject__scheme=new_scheme, is_active=True).select_related("subject")
    }
    created = 0
    for old in Chapter.objects.filter(subject__scheme=old_scheme, is_active=True).select_related("subject"):
        target = new_chapters.get((old.subject.key, old.key))
        if not target:
            continue
        _, was_created = ChapterMap.objects.get_or_create(
            from_chapter=old,
            to_chapter=target,
            defaults={"relation": ChapterMap.Relation.SAME, "carry_ratio": Decimal("1.00")},
        )
        created += int(was_created)
    return created


# --- reports ---------------------------------------------------------------------------------

_NODE_MODELS = {
    "course": Course,
    "level": Level,
    "scheme": Scheme,
    "subject": Subject,
    "chapter": Chapter,
    "topic": Topic,
}


def create_report(*, node_type: str, node_id, message: str, user_id: str | None) -> SyllabusReport:
    model = _NODE_MODELS.get(node_type)
    if model is None or not model.objects.filter(pk=node_id).exists():
        raise ValidationError("The reported item does not exist.")
    return SyllabusReport.objects.create(node_type=node_type, node_id=node_id, message=message, user_id=user_id)


# --- seed loader (idempotent, keyed on stable keys) ------------------------------------------


@transaction.atomic
def load_scheme_from_dict(data: dict[str, Any], *, publish: bool = False) -> Scheme:
    """
    Loads one scheme file. Running it twice creates no duplicates (FR-9): every node is matched on its stable key.
    Nodes missing from the file are set inactive, never deleted. New schemes start as `draft` unless `publish` is set.
    """
    course = Course.objects.get(code=data["course"])
    level = Level.objects.get(course=course, code=data["level"])
    spec = data["scheme"]

    def term(code: str | None) -> ExamTerm | None:
        return ExamTerm.objects.get(course=course, code=code) if code else None

    scheme, created = Scheme.objects.get_or_create(
        level=level,
        code=spec["code"],
        defaults={"name": spec["name"], "status": Scheme.Status.DRAFT},
    )
    scheme.name = spec["name"]
    scheme.source_url = spec.get("source_url", "")
    scheme.notes = spec.get("notes", "")
    scheme.from_term = term(spec.get("from_term"))
    scheme.to_term = term(spec.get("to_term"))
    scheme.save()

    group_objs: dict[str, SyllabusGroup] = {}
    for order, g in enumerate(data.get("groups", [])):
        group, _ = SyllabusGroup.objects.update_or_create(
            scheme=scheme, key=g["key"], defaults={"name": g["name"], "sort_order": order}
        )
        group_objs[g["key"]] = group

    seen_subjects: set[str] = set()
    for s_order, s in enumerate(data.get("subjects", [])):
        subject, _ = Subject.objects.update_or_create(
            scheme=scheme,
            key=s["key"],
            defaults={
                "group": group_objs.get(s.get("group", "")),
                "paper_number": s.get("paper_number"),
                "name": s["name"],
                "total_marks": s.get("total_marks"),
                "exam_duration_minutes": s.get("exam_duration_minutes"),
                "kind": s.get("kind", Subject.Kind.THEORY),
                "is_optional": s.get("is_optional", False),
                "sort_order": s_order,
                "is_active": True,
            },
        )
        seen_subjects.add(subject.key)
        _load_chapters(subject, s.get("chapters", []))
    scheme.subjects.exclude(key__in=seen_subjects).update(is_active=False)

    if publish and scheme.status == Scheme.Status.DRAFT:
        publish_scheme(scheme)
    return scheme


def _load_chapters(subject: Subject, chapters: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for c_order, c in enumerate(chapters):
        chapter, _ = Chapter.objects.update_or_create(
            subject=subject,
            key=c["key"],
            defaults={
                "name": c["name"],
                "marks_min": c.get("marks_min"),
                "marks_max": c.get("marks_max"),
                "weight_source": c.get("weight_source", Chapter.WeightSource.UNKNOWN),
                "target_practice_sets": c.get("target_practice_sets", 1),
                "target_revisions": c.get("target_revisions", 2),
                "target_mocks": c.get("target_mocks", 1),
                "est_study_minutes": c.get("est_study_minutes"),
                "sort_order": c_order,
                "is_active": True,
            },
        )
        seen.add(chapter.key)
        seen_topics: set[str] = set()
        for t_order, t in enumerate(c.get("topics", [])):
            topic, _ = Topic.objects.update_or_create(
                chapter=chapter,
                key=t["key"],
                defaults={
                    "name": t["name"],
                    "kind": t.get("kind", Topic.Kind.CONCEPT),
                    "sort_order": t_order,
                    "is_active": True,
                },
            )
            seen_topics.add(topic.key)
        chapter.topics.exclude(key__in=seen_topics).update(is_active=False)
    subject.chapters.exclude(key__in=seen).update(is_active=False)


# --- bulk helpers for the admin ---------------------------------------------------------------


def _unique_key(base: str, taken: set[str], limit: int) -> str:
    key = base[:limit] or "item"
    candidate, n = key, 2
    while candidate in taken:
        suffix = f"-{n}"
        candidate = f"{key[: limit - len(suffix)]}{suffix}"
        n += 1
    return candidate


def add_topics_from_text(chapter: Chapter, text: str) -> int:
    """One topic per line. Optional `name | kind` (kind such as rule, section, formula). Existing names are skipped."""
    from django.utils.text import slugify

    existing = {t.name.strip().lower() for t in chapter.topics.all()}
    taken = set(chapter.topics.values_list("key", flat=True))
    order = (chapter.topics.order_by("-sort_order").values_list("sort_order", flat=True).first() or 0) + 1
    valid_kinds = {k for k, _ in Topic.Kind.choices}
    created = 0
    for raw in text.splitlines():
        name, _, kind = (part.strip() for part in raw.partition("|"))
        if not name or name.lower() in existing:
            continue
        key = _unique_key(slugify(name), taken, 120)
        taken.add(key)
        existing.add(name.lower())
        Topic.objects.create(
            chapter=chapter,
            key=key,
            name=name[:240],
            kind=kind if kind in valid_kinds else Topic.Kind.CONCEPT,
            sort_order=order,
        )
        order += 1
        created += 1
    return created


def add_chapters_from_text(subject: Subject, text: str) -> int:
    """One chapter per line. Optional `name | min-max` marks (for example `GST Basics | 5-8`, or `| 6` for one value)."""
    from decimal import InvalidOperation

    from django.utils.text import slugify

    existing = {c.name.strip().lower() for c in subject.chapters.all()}
    taken = set(subject.chapters.values_list("key", flat=True))
    order = (subject.chapters.order_by("-sort_order").values_list("sort_order", flat=True).first() or 0) + 1
    created = 0
    for raw in text.splitlines():
        name, _, marks = (part.strip() for part in raw.partition("|"))
        if not name or name.lower() in existing:
            continue
        low = high = None
        if marks:
            lo_text, dash, hi_text = marks.partition("-")
            try:
                low = Decimal(lo_text.strip()) if dash else None
                high = Decimal(hi_text.strip()) if dash else Decimal(lo_text.strip())
            except InvalidOperation:
                low = high = None
        if low is not None and high is not None and high < low:
            low, high = high, low
        key = _unique_key(slugify(name), taken, 100)
        taken.add(key)
        existing.add(name.lower())
        Chapter.objects.create(
            subject=subject,
            key=key,
            name=name[:240],
            marks_min=low,
            marks_max=high,
            weight_source=Chapter.WeightSource.OFFICIAL if high is not None else Chapter.WeightSource.UNKNOWN,
            sort_order=order,
        )
        order += 1
        created += 1
    return created


def scheme_to_dict(scheme: Scheme) -> dict[str, Any]:
    """The inverse of `load_scheme_from_dict`: the same JSON format as the seed files, for round-trip editing."""

    def num(value):
        return float(value) if value is not None else None

    subjects = []
    for subject in scheme.subjects.filter(is_active=True).select_related("group").order_by("sort_order", "key"):
        chapters = []
        for chapter in subject.chapters.filter(is_active=True).order_by("sort_order", "key"):
            entry: dict[str, Any] = {
                "key": chapter.key,
                "name": chapter.name,
                "marks_min": num(chapter.marks_min),
                "marks_max": num(chapter.marks_max),
                "weight_source": chapter.weight_source,
                "target_practice_sets": chapter.target_practice_sets,
                "target_revisions": chapter.target_revisions,
                "target_mocks": chapter.target_mocks,
                "est_study_minutes": chapter.est_study_minutes,
                "topics": [
                    {"key": t.key, "name": t.name, "kind": t.kind}
                    for t in chapter.topics.filter(is_active=True).order_by("sort_order", "key")
                ],
            }
            chapters.append({k: v for k, v in entry.items() if v is not None})
        subjects.append(
            {
                k: v
                for k, v in {
                    "key": subject.key,
                    "paper_number": subject.paper_number,
                    "name": subject.name,
                    "group": subject.group.key if subject.group_id else None,
                    "total_marks": subject.total_marks,
                    "exam_duration_minutes": subject.exam_duration_minutes,
                    "kind": subject.kind,
                    "is_optional": subject.is_optional,
                    "chapters": chapters,
                }.items()
                if v is not None
            }
        )
    return {
        "course": scheme.level.course.code,
        "level": scheme.level.code,
        "scheme": {
            k: v
            for k, v in {
                "code": scheme.code,
                "name": scheme.name,
                "source_url": scheme.source_url,
                "notes": scheme.notes,
                "from_term": scheme.from_term.code if scheme.from_term_id else None,
                "to_term": scheme.to_term.code if scheme.to_term_id else None,
            }.items()
            if v not in (None, "")
        },
        "groups": [{"key": g.key, "name": g.name} for g in scheme.groups.order_by("sort_order", "key")],
        "subjects": subjects,
    }
