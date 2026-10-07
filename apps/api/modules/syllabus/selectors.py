"""Read-only queries for the syllabus. Students only ever see `published` schemes, enrolled students also see `retired`."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from django.db.models import Prefetch, Q, QuerySet

from .models import Chapter, Course, ExamTerm, Level, Scheme, Subject, SyllabusGroup, Topic


def list_courses() -> QuerySet[Course]:
    levels = Prefetch("levels", queryset=Level.objects.filter(is_active=True).order_by("sort_order", "code"))
    return Course.objects.filter(is_active=True).prefetch_related(levels).order_by("code")


def get_course(code: str) -> Course | None:
    return Course.objects.filter(code=code, is_active=True).first()


def get_level(course_code: str, level_code: str) -> Level | None:
    return (
        Level.objects.select_related("course")
        .filter(course__code=course_code, course__is_active=True, code=level_code, is_active=True)
        .first()
    )


def list_published_schemes(level: Level) -> QuerySet[Scheme]:
    return level.schemes.filter(status=Scheme.Status.PUBLISHED).order_by("-published_at", "-code")


def get_current_scheme(level: Level) -> Scheme | None:
    """The scheme a new student should be offered: the most recently published one."""
    return list_published_schemes(level).first()


def get_scheme(scheme_id) -> Scheme | None:
    return Scheme.objects.select_related("level__course").filter(pk=scheme_id).first()


def get_scheme_any_visible(scheme_id) -> Scheme | None:
    """For enrolment: published or retired (never draft)."""
    return (
        Scheme.objects.select_related("level__course")
        .filter(pk=scheme_id, status__in=[Scheme.Status.PUBLISHED, Scheme.Status.RETIRED])
        .first()
    )


def list_groups(scheme: Scheme) -> QuerySet[SyllabusGroup]:
    return scheme.groups.order_by("sort_order", "key")


def list_subjects(scheme: Scheme) -> QuerySet[Subject]:
    return (
        scheme.subjects.filter(is_active=True)
        .select_related("group")
        .prefetch_related(Prefetch("chapters", queryset=Chapter.objects.filter(is_active=True)))
        .order_by("sort_order", "key")
    )


@dataclass
class ElectiveSlot:
    """A paper the student sits one option of (CMA Final 20A/20B/20C, CS Professional 4.x and 7.x)."""

    key: str  # "<group key>:<paper number>", stable across schemes of the same level
    paper_number: int | None
    group_key: str | None
    options: list[Subject] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"Elective Paper {self.paper_number}" if self.paper_number else "Elective paper"


def elective_slots(scheme: Scheme) -> list[ElectiveSlot]:
    """
    Groups the optional subjects of a scheme into slots: subjects flagged `is_optional` or `kind=elective` that share
    a group and paper number. A single optional subject is not a choice, so slots need at least two options.
    """
    slots: dict[str, ElectiveSlot] = {}
    for subject in list_subjects(scheme):
        if not (subject.is_optional or subject.kind == Subject.Kind.ELECTIVE) or subject.paper_number is None:
            continue
        group_key = subject.group.key if subject.group_id else None
        key = f"{group_key or ''}:{subject.paper_number}"
        slot = slots.setdefault(key, ElectiveSlot(key=key, paper_number=subject.paper_number, group_key=group_key))
        slot.options.append(subject)
    return [s for s in slots.values() if len(s.options) >= 2]


def list_chapters(subject: Subject) -> QuerySet[Chapter]:
    return subject.chapters.filter(is_active=True).order_by("sort_order", "key")


def neighbour_chapters(chapter: Chapter) -> tuple[Chapter | None, Chapter | None]:
    """The previous and next active chapter of the same paper, in syllabus order (for prev/next navigation)."""
    siblings = list(list_chapters(chapter.subject))
    for i, c in enumerate(siblings):
        if c.id == chapter.id:
            return (siblings[i - 1] if i > 0 else None, siblings[i + 1] if i + 1 < len(siblings) else None)
    return None, None


def list_topics(chapter: Chapter) -> QuerySet[Topic]:
    return chapter.topics.filter(is_active=True).order_by("sort_order", "key")


def get_subject_by_keys(course_code: str, level_code: str, subject_key: str) -> Subject | None:
    level = get_level(course_code, level_code)
    scheme = get_current_scheme(level) if level else None
    if not scheme:
        return None
    return (
        Subject.objects.select_related("scheme__level__course", "group")
        .filter(scheme=scheme, key=subject_key, is_active=True)
        .first()
    )


def get_chapter_by_keys(course_code: str, level_code: str, subject_key: str, chapter_key: str) -> Chapter | None:
    subject = get_subject_by_keys(course_code, level_code, subject_key)
    if not subject:
        return None
    return (
        subject.chapters.filter(key=chapter_key, is_active=True)
        .select_related("subject__scheme__level__course")
        .first()
    )


def get_published_subject(subject_id) -> Subject | None:
    return (
        Subject.objects.select_related("scheme__level__course", "group")
        .filter(pk=subject_id, is_active=True, scheme__status=Scheme.Status.PUBLISHED)
        .first()
    )


def get_subject(subject_id) -> Subject | None:
    """Any visible subject (published or retired scheme). Used by tracking for students still on an older scheme."""
    return (
        Subject.objects.select_related("scheme__level__course", "group")
        .filter(pk=subject_id, is_active=True, scheme__status__in=[Scheme.Status.PUBLISHED, Scheme.Status.RETIRED])
        .first()
    )


def get_published_chapter(chapter_id) -> Chapter | None:
    return (
        Chapter.objects.select_related("subject__scheme__level__course", "subject__group")
        .filter(pk=chapter_id, is_active=True, subject__scheme__status=Scheme.Status.PUBLISHED)
        .first()
    )


def get_chapter(chapter_id) -> Chapter | None:
    """Any visible chapter (published or retired scheme). Used by coverage for enrolled students."""
    return (
        Chapter.objects.select_related("subject__scheme__level__course", "subject__group")
        .filter(pk=chapter_id, subject__scheme__status__in=[Scheme.Status.PUBLISHED, Scheme.Status.RETIRED])
        .first()
    )


def get_topic(topic_id) -> Topic | None:
    return (
        Topic.objects.select_related("chapter__subject__scheme")
        .filter(pk=topic_id, is_active=True, chapter__subject__scheme__status__in=["published", "retired"])
        .first()
    )


def list_terms(
    course_code: str | None = None, level_code: str | None = None, open_only: bool = True
) -> QuerySet[ExamTerm]:
    qs = ExamTerm.objects.select_related("course", "level").order_by("course__code", "level__sort_order", "code")
    if course_code:
        qs = qs.filter(course__code=course_code)
    if level_code:
        qs = qs.filter(level__code=level_code)
    if open_only:
        qs = qs.filter(is_open=True)
    return qs


def sitemap_paths() -> list[str]:
    """Public syllabus paths of every level's current scheme (subjects and chapters)."""
    paths: list[str] = []
    for level in Level.objects.select_related("course").filter(is_active=True, course__is_active=True):
        scheme = get_current_scheme(level)
        if not scheme:
            continue
        base = f"/courses/{level.course.code}/{level.code}"
        for subject in scheme.subjects.filter(is_active=True).prefetch_related("chapters"):
            paths.append(f"{base}/{subject.key}")
            paths.extend(f"{base}/{subject.key}/{c.key}" for c in subject.chapters.all() if c.is_active)
    return paths


# --- Stable references for other modules (F-03 ERD 3.2, additive) -------------------------------------------------------
# Modules that keep their own rows against a chapter (notes now, the question bank later) store the foreign key AND the
# stable keys. They resolve ids and keys through these functions and never import syllabus models.


@dataclass(frozen=True)
class ChapterRef:
    id: UUID
    key: str
    name: str
    subject_id: UUID
    subject_key: str
    level_id: UUID
    scheme_id: UUID
    scheme_status: str
    subject_name: str = ""  # display only; appended after the contract fields so positional callers keep working


@dataclass(frozen=True)
class TopicRef:
    id: UUID
    key: str
    name: str
    chapter_id: UUID
    chapter_key: str


def _chapter_ref(chapter: Chapter) -> ChapterRef:
    subject = chapter.subject
    return ChapterRef(
        id=chapter.id,
        key=chapter.key,
        name=chapter.name,
        subject_id=subject.id,
        subject_key=subject.key,
        level_id=subject.scheme.level_id,
        scheme_id=subject.scheme_id,
        scheme_status=subject.scheme.status,
        subject_name=subject.name,
    )


def _visible_chapters() -> QuerySet[Chapter]:
    """Chapters of published or retired schemes (never drafts), with what a ChapterRef needs in one query."""
    return Chapter.objects.select_related("subject__scheme").filter(
        subject__scheme__status__in=[Scheme.Status.PUBLISHED, Scheme.Status.RETIRED]
    )


def chapter_refs(chapter_ids: Sequence[UUID]) -> dict[UUID, ChapterRef]:
    """References for the visible chapters among `chapter_ids`; unknown, draft-only or invalid ids are simply absent."""
    if not chapter_ids:
        return {}
    return {c.id: _chapter_ref(c) for c in _visible_chapters().filter(pk__in=list(chapter_ids))}


def topic_refs(topic_ids: Sequence[UUID]) -> dict[UUID, TopicRef]:
    if not topic_ids:
        return {}
    topics = Topic.objects.select_related("chapter__subject__scheme").filter(
        pk__in=list(topic_ids), chapter__subject__scheme__status__in=[Scheme.Status.PUBLISHED, Scheme.Status.RETIRED]
    )
    return {
        t.id: TopicRef(id=t.id, key=t.key, name=t.name, chapter_id=t.chapter_id, chapter_key=t.chapter.key)
        for t in topics
    }


def _current_scheme_id(level_id: UUID) -> UUID | None:
    return (
        Scheme.objects.filter(level_id=level_id, status=Scheme.Status.PUBLISHED)
        .order_by("-published_at", "-code")
        .values_list("id", flat=True)
        .first()
    )


def resolve_key_pairs(level_id: UUID, pairs: Iterable[tuple[str, str]]) -> dict[tuple[str, str], ChapterRef]:
    """
    `(subject_key, chapter_key)` pairs to chapters of the level's current published scheme, in one query. This is how a
    student's notes follow a scheme switch: the keys are stable, the rows they point at are not. Missing pairs are absent.
    """
    wanted = set(pairs)
    scheme_id = _current_scheme_id(level_id) if wanted else None
    if scheme_id is None:
        return {}
    match = Q()
    for subject_key, chapter_key in wanted:
        match |= Q(subject__key=subject_key, key=chapter_key)
    chapters = (
        _visible_chapters().filter(subject__scheme_id=scheme_id, is_active=True, subject__is_active=True).filter(match)
    )
    return {(c.subject.key, c.key): _chapter_ref(c) for c in chapters}


def resolve_keys(level_id: UUID, subject_key: str, chapter_key: str) -> ChapterRef | None:
    """The chapter with these keys in the level's current published scheme, or None (moved or removed)."""
    return resolve_key_pairs(level_id, [(subject_key, chapter_key)]).get((subject_key, chapter_key))


def chapters_for_scheme(scheme_id: UUID, subject_key: str | None = None) -> list[ChapterRef]:
    """Active chapters of a scheme in syllabus order (subject, then chapter), optionally of one subject."""
    chapters = _visible_chapters().filter(subject__scheme_id=scheme_id, is_active=True, subject__is_active=True)
    if subject_key:
        chapters = chapters.filter(subject__key=subject_key)
    return [_chapter_ref(c) for c in chapters.order_by("subject__sort_order", "subject__key", "sort_order", "key")]


def current_scheme_id(level_id: UUID) -> UUID | None:
    """The scheme a level currently shows students (most recently published)."""
    return _current_scheme_id(level_id)
