"""Write operations: publish and retire schemes, chapter maps, reports, and the idempotent seed loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from . import matching
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


@dataclass
class ChapterMapReport:
    """What `build_default_chapter_map` did. `created` counts new rows; rows that already existed are never touched."""

    created: int = 0
    skipped_existing: int = 0
    needs_review: int = 0
    by_basis: dict[str, int] = field(default_factory=dict)
    splits: int = 0  # old chapters proposed to split into several new ones
    merges: int = 0  # new chapters proposed to merge several old ones
    unmatched_old: list[Chapter] = field(
        default_factory=list
    )  # no counterpart: students' progress stays on the old scheme
    unmatched_new: list[Chapter] = field(default_factory=list)  # new in this scheme: start at zero

    def summary(self) -> str:
        parts = [f"Created {self.created} chapter maps"]
        if self.needs_review:
            parts.append(f"{self.needs_review} need your review (filter Chapter maps by 'needs review')")
        if self.splits or self.merges:
            parts.append(f"{self.splits} split and {self.merges} merge proposals")
        parts.append(
            f"{len(self.unmatched_new)} new chapters and {len(self.unmatched_old)} removed chapters have no map"
        )
        return ". ".join(parts) + "."


def _items(chapters: list[Chapter]) -> list[matching.Item]:
    return [matching.Item(c, c.key, c.name, position) for position, c in enumerate(chapters)]


def _subject_items(subjects: list[Subject]) -> list[matching.Item]:
    return [matching.Item(s, s.key, s.name, position) for position, s in enumerate(subjects)]


def propose_chapter_map(
    old_scheme: Scheme, new_scheme: Scheme
) -> tuple[list[matching.Proposal], list[Chapter], list[Chapter]]:
    """
    Proposes chapter maps from `old_scheme` to `new_scheme` without saving anything (see `matching`).
    Chapters an editor already mapped into the new scheme are left alone. Returns (proposals, unmatched old, unmatched new).
    """
    already = ChapterMap.objects.filter(
        to_chapter__subject__scheme=new_scheme, from_chapter__subject__scheme=old_scheme
    )
    mapped_old = set(already.values_list("from_chapter_id", flat=True))
    mapped_new = set(already.values_list("to_chapter_id", flat=True))

    def chapters_of(scheme: Scheme, skip: set) -> dict:
        grouped: dict = {}
        qs = Chapter.objects.filter(subject__scheme=scheme, is_active=True)
        for chapter in qs.select_related("subject").order_by("sort_order", "key"):
            if chapter.id not in skip:
                grouped.setdefault(chapter.subject_id, []).append(chapter)
        return grouped

    old_by_subject = chapters_of(old_scheme, mapped_old)
    new_by_subject = chapters_of(new_scheme, mapped_new)
    old_subjects = list(old_scheme.subjects.order_by("sort_order", "key"))
    new_subjects = list(new_scheme.subjects.order_by("sort_order", "key"))

    proposals: list[matching.Proposal] = []
    leftover_old: list[Chapter] = []
    leftover_new: list[Chapter] = []
    paired_old: set = set()
    paired_new: set = set()
    for old_item, new_item in matching.match_papers(_subject_items(old_subjects), _subject_items(new_subjects)):
        old_subject, new_subject = old_item.ref, new_item.ref
        paired_old.add(old_subject.id)
        paired_new.add(new_subject.id)
        result = matching.match_chapters(
            _items(old_by_subject.get(old_subject.id, [])), _items(new_by_subject.get(new_subject.id, []))
        )
        proposals.extend(result.proposals)
        leftover_old.extend(i.ref for i in result.unmatched_old)
        leftover_new.extend(i.ref for i in result.unmatched_new)
    for subject in old_subjects:
        if subject.id not in paired_old:
            leftover_old.extend(old_by_subject.get(subject.id, []))
    for subject in new_subjects:
        if subject.id not in paired_new:
            leftover_new.extend(new_by_subject.get(subject.id, []))

    moved = matching.match_moved(_items(leftover_old), _items(leftover_new))
    proposals.extend(moved)
    moved_old = {p.old.id for p in moved}
    moved_new = {p.new.id for p in moved}
    return (
        proposals,
        [c for c in leftover_old if c.id not in moved_old],
        [c for c in leftover_new if c.id not in moved_new],
    )


@transaction.atomic
def build_default_chapter_map(old_scheme: Scheme, new_scheme: Scheme) -> ChapterMapReport:
    """
    Fills the chapter map between two schemes of a level. Matches by key, then by normalised name and position,
    and proposes splits and merges; anything doubtful is saved with `needs_review` so an editor confirms it in the
    admin. Safe to repeat: existing rows (including ones an editor changed) are never overwritten.
    """
    if old_scheme.level_id != new_scheme.level_id:
        raise ValidationError("Schemes must belong to the same level.")
    proposals, unmatched_old, unmatched_new = propose_chapter_map(old_scheme, new_scheme)
    report = ChapterMapReport(unmatched_old=unmatched_old, unmatched_new=unmatched_new)
    split_sources: set = set()
    merge_targets: set = set()
    for p in proposals:
        _, was_created = ChapterMap.objects.get_or_create(
            from_chapter=p.old,
            to_chapter=p.new,
            defaults={
                "relation": p.relation,
                "carry_ratio": p.carry_ratio,
                "basis": p.basis,
                "confidence": Decimal(str(round(p.confidence, 2))),
                "needs_review": p.needs_review,
            },
        )
        if not was_created:
            report.skipped_existing += 1
            continue
        report.created += 1
        report.needs_review += int(p.needs_review)
        report.by_basis[p.basis] = report.by_basis.get(p.basis, 0) + 1
        if p.relation == ChapterMap.Relation.SPLIT:
            split_sources.add(p.old.id)
        if p.relation == ChapterMap.Relation.MERGED:
            merge_targets.add(p.new.id)
    report.splits, report.merges = len(split_sources), len(merge_targets)
    return report


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
        return ExamTerm.objects.get(level=level, code=code) if code else None

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
                "source_url": s.get("source_url", ""),
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
                "section": c.get("section", ""),
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
                "section": chapter.section or None,
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
                    "source_url": subject.source_url or None,
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


LEGACY_SCHEME_CODES = ("indicative", "2023-sample")


@transaction.atomic
def prune_legacy_schemes(*, dry_run: bool = False) -> list[tuple[Scheme, str]]:
    """Delete leftover placeholder schemes. Schemes with enrolled students are kept."""
    schemes = Scheme.objects.filter(code__in=LEGACY_SCHEME_CODES).select_related("level__course")
    results: list[tuple[Scheme, str]] = []
    for scheme in schemes:
        if scheme.enrollments.exists():
            results.append((scheme, "kept (enrolled students)"))
            continue
        if dry_run:
            results.append((scheme, "would delete"))
            continue
        # Subjects protect their group, so clear the tree before the scheme row.
        scheme.subjects.all().delete()
        scheme.groups.all().delete()
        scheme.delete()
        results.append((scheme, "deleted"))
    return results
