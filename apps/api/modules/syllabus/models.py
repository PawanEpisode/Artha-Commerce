"""
Syllabus taxonomy (X-05): public reference data shared by every student. Admin and seed loader write, everyone reads.

Hierarchy: Course > Level > Scheme (version) > Group (optional) > Subject > Chapter > Topic.
Every node below a level belongs to a scheme; a new scheme is a new set of rows, so student progress never breaks.
See docs/product/erd/F-02-syllabus-structure-and-coverage.md.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import UUIDModel


class Course(UUIDModel):
    code = models.SlugField(max_length=16, unique=True)  # ca, cs, cma
    name = models.CharField(max_length=120)
    institute_name = models.CharField(max_length=120)
    institute_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "syllabus_course"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class Level(UUIDModel):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="levels")
    code = models.SlugField(max_length=32)
    name = models.CharField(max_length=80)
    sort_order = models.SmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "syllabus_level"
        ordering = ["sort_order", "code"]
        constraints = [models.UniqueConstraint(fields=["course", "code"], name="syllabus_level_unique_code")]

    def __str__(self) -> str:
        return f"{self.course.code}/{self.code}"


class ExamTerm(UUIDModel):
    """An exam attempt of one level (CMA Foundation, CMA Intermediate and CMA Final each have their own attempts and dates)."""

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="terms", editable=False)  # from `level`
    level = models.ForeignKey(Level, on_delete=models.PROTECT, related_name="terms")
    code = models.CharField(max_length=16)  # 2027-05
    name = models.CharField(max_length=60)  # May 2027
    exam_start = models.DateField(null=True, blank=True)
    exam_end = models.DateField(null=True, blank=True)
    is_open = models.BooleanField(default=True)  # shown in onboarding

    class Meta:
        db_table = "syllabus_examterm"
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["level", "code"], name="syllabus_examterm_unique_level_code")]

    def save(self, *args, **kwargs):
        self.course_id = self.level.course_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.course.code.upper()} {self.level.name} {self.name}"


class Scheme(UUIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    level = models.ForeignKey(Level, on_delete=models.PROTECT, related_name="schemes")
    code = models.CharField(max_length=16)  # 2023, 2025
    name = models.CharField(max_length=80)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    from_term = models.ForeignKey(ExamTerm, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    to_term = models.ForeignKey(ExamTerm, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    source_url = models.URLField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "syllabus_scheme"
        ordering = ["level", "-code"]
        permissions = [("publish_scheme", "Can publish and retire schemes")]
        constraints = [
            models.UniqueConstraint(fields=["level", "code"], name="syllabus_scheme_unique_code"),
            models.CheckConstraint(
                condition=Q(status__in=["draft", "published", "retired"]), name="syllabus_scheme_status_valid"
            ),
        ]

    def clean(self):
        for field in ("from_term", "to_term"):
            term = getattr(self, field)
            if term and self.level_id and term.level_id != self.level_id:
                raise ValidationError({field: "Pick an exam term of this scheme's level."})

    def __str__(self) -> str:
        return f"{self.level} {self.code}"


class SyllabusGroup(UUIDModel):
    """A group or module of papers (Group I, Module 1). Levels without groups simply have none."""

    scheme = models.ForeignKey(Scheme, on_delete=models.CASCADE, related_name="groups")
    key = models.SlugField(max_length=64)
    name = models.CharField(max_length=120)
    sort_order = models.SmallIntegerField(default=0)

    class Meta:
        db_table = "syllabus_group"
        ordering = ["sort_order", "key"]
        constraints = [models.UniqueConstraint(fields=["scheme", "key"], name="syllabus_group_unique_key")]

    def __str__(self) -> str:
        return f"{self.scheme} {self.key}"


class Subject(UUIDModel):
    """A paper. `key` is stable across schemes so URLs, goals and reports survive a scheme change."""

    class Kind(models.TextChoices):
        THEORY = "theory", "Theory"
        PRACTICAL = "practical", "Practical"
        MIXED = "mixed", "Mixed"
        ELECTIVE = "elective", "Elective"

    scheme = models.ForeignKey(Scheme, on_delete=models.CASCADE, related_name="subjects")
    group = models.ForeignKey(SyllabusGroup, null=True, blank=True, on_delete=models.PROTECT, related_name="subjects")
    key = models.SlugField(max_length=80)
    paper_number = models.SmallIntegerField(null=True, blank=True)
    name = models.CharField(max_length=200)
    total_marks = models.SmallIntegerField(null=True, blank=True)
    exam_duration_minutes = models.SmallIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.THEORY)
    is_optional = models.BooleanField(default=False)
    source_url = models.URLField(max_length=500, blank=True)  # the institute document this paper was built from
    sort_order = models.SmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "syllabus_subject"
        ordering = ["sort_order", "key"]
        constraints = [
            models.UniqueConstraint(fields=["scheme", "key"], name="syllabus_subject_unique_key"),
            models.CheckConstraint(
                condition=Q(kind__in=["theory", "practical", "mixed", "elective"]), name="syllabus_subject_kind_valid"
            ),
        ]
        indexes = [models.Index(fields=["scheme", "group", "sort_order"], name="syllabus_subject_tree_idx")]

    def __str__(self) -> str:
        return f"{self.scheme} {self.key}"


class Chapter(UUIDModel):
    class WeightSource(models.TextChoices):
        OFFICIAL = "official", "Official"
        ANALYSIS = "analysis", "Analysis based"
        UNKNOWN = "unknown", "Unknown"

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="chapters")
    key = models.SlugField(max_length=100)
    name = models.CharField(max_length=240)
    # Section / Part of the paper this chapter sits in, e.g. "Section A: Direct Taxation (50%)". Flat label, no extra table.
    section = models.CharField(max_length=200, blank=True)
    marks_min = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    marks_max = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_source = models.CharField(max_length=10, choices=WeightSource.choices, default=WeightSource.UNKNOWN)
    target_practice_sets = models.SmallIntegerField(default=1)
    target_revisions = models.SmallIntegerField(default=2)
    target_mocks = models.SmallIntegerField(default=1)
    est_study_minutes = models.SmallIntegerField(null=True, blank=True)
    sort_order = models.SmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "syllabus_chapter"
        ordering = ["sort_order", "key"]
        constraints = [
            models.UniqueConstraint(fields=["subject", "key"], name="syllabus_chapter_unique_key"),
            models.CheckConstraint(
                condition=Q(marks_min__isnull=True)
                | Q(marks_max__isnull=True)
                | Q(marks_max__gte=models.F("marks_min")),
                name="syllabus_chapter_marks_range",
            ),
            models.CheckConstraint(
                condition=Q(target_practice_sets__gte=0, target_practice_sets__lte=20)
                & Q(target_revisions__gte=0, target_revisions__lte=20)
                & Q(target_mocks__gte=0, target_mocks__lte=20),
                name="syllabus_chapter_targets_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.subject} {self.key}"

    @property
    def marks_weight(self) -> float:
        return marks_weight(self.marks_min, self.marks_max)


def marks_weight(marks_min: Decimal | None, marks_max: Decimal | None) -> float:
    """coalesce((min + max) / 2, max, min, 1): the weight of a chapter in marks-weighted roll-ups."""
    if marks_min is not None and marks_max is not None:
        return float((marks_min + marks_max) / 2)
    if marks_max is not None:
        return float(marks_max)
    if marks_min is not None:
        return float(marks_min)
    return 1.0


class Topic(UUIDModel):
    class Kind(models.TextChoices):
        CONCEPT = "concept", "Concept"
        SECTION = "section", "Section"
        RULE = "rule", "Rule"
        STANDARD = "standard", "Standard"
        FORMULA = "formula", "Formula"
        CASE_LAW = "case_law", "Case law"
        ILLUSTRATION = "illustration", "Illustration"

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="topics")
    key = models.SlugField(max_length=120)
    name = models.CharField(max_length=240)
    kind = models.CharField(max_length=14, choices=Kind.choices, default=Kind.CONCEPT)
    sort_order = models.SmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "syllabus_topic"
        ordering = ["sort_order", "key"]
        constraints = [
            models.UniqueConstraint(fields=["chapter", "key"], name="syllabus_topic_unique_key"),
            models.CheckConstraint(
                condition=Q(kind__in=["concept", "section", "rule", "standard", "formula", "case_law", "illustration"]),
                name="syllabus_topic_kind_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.chapter} {self.key}"


class ChapterMap(UUIDModel):
    """Carries progress between two schemes of the same level."""

    class Relation(models.TextChoices):
        SAME = "same", "Same"
        SPLIT = "split", "Split"
        MERGED = "merged", "Merged"
        PARTIAL = "partial", "Partial"

    from_chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="maps_out")
    to_chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="maps_in")
    relation = models.CharField(max_length=10, choices=Relation.choices, default=Relation.SAME)
    carry_ratio = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("1.00"))

    class Meta:
        db_table = "syllabus_chaptermap"
        constraints = [
            models.UniqueConstraint(fields=["from_chapter", "to_chapter"], name="syllabus_chaptermap_unique_pair"),
            models.CheckConstraint(
                condition=Q(relation__in=["same", "split", "merged", "partial"]), name="syllabus_chaptermap_relation"
            ),
            models.CheckConstraint(
                condition=Q(carry_ratio__gte=0, carry_ratio__lte=1), name="syllabus_chaptermap_ratio_range"
            ),
        ]


class SyllabusReport(UUIDModel):
    """'Report a wrong syllabus item'. Anonymous reports are allowed (user_id null)."""

    class NodeType(models.TextChoices):
        COURSE = "course", "Course"
        LEVEL = "level", "Level"
        SCHEME = "scheme", "Scheme"
        SUBJECT = "subject", "Subject"
        CHAPTER = "chapter", "Chapter"
        TOPIC = "topic", "Topic"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        FIXED = "fixed", "Fixed"

    node_type = models.CharField(max_length=10, choices=NodeType.choices)
    node_id = models.UUIDField()
    user_id = models.UUIDField(null=True, blank=True)
    message = models.CharField(max_length=1000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)

    class Meta:
        db_table = "syllabus_report"
        indexes = [models.Index(fields=["status", "created_at"], name="syllabus_report_queue_idx")]
