"""Read-only queries for the syllabus. Students only ever see `published` schemes, enrolled students also see `retired`."""

from django.db.models import Prefetch, QuerySet

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


def list_chapters(subject: Subject) -> QuerySet[Chapter]:
    return subject.chapters.filter(is_active=True).order_by("sort_order", "key")


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


def list_terms(course_code: str | None = None, open_only: bool = True) -> QuerySet[ExamTerm]:
    qs = ExamTerm.objects.select_related("course").order_by("course__code", "code")
    if course_code:
        qs = qs.filter(course__code=course_code)
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
