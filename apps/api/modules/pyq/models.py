"""
Models for F-09 Previous Year Questions (papers, choice groups, questions tree, links, asked cache, daily sets).
Reference: docs/product/erd/F-09-previous-year-questions.md Section 2.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class PyqPaper(models.Model):
    class Delivery(models.TextChoices):
        LINK_OUT = "link_out", "Link out to Institute PDF"
        HOSTED = "hosted", "Hosted solution"

    class RightsBasis(models.TextChoices):
        ORIGINAL = "original", "Original platform content"
        LICENSED = "licensed", "Licensed content"
        INSTITUTE_MATERIAL = "institute_material", "Institute material"

    class AnswersStatus(models.TextChoices):
        NONE = "none", "No answers published"
        PARTIAL = "partial", "Partial answers"
        COMPLETE = "complete", "Complete answers"

    class SyllabusStatus(models.TextChoices):
        CURRENT = "current", "Current syllabus"
        OLD_SCHEME = "old_scheme", "Old scheme"
        UNMAPPED = "unmapped", "Unmapped"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class WithdrawnReason(models.TextChoices):
        TAKEDOWN = "takedown", "Copyright takedown"
        LICENCE_ENDED = "licence_ended", "Licence expired"
        EDITOR = "editor", "Editor withdrawal"
        REPLACED = "replaced", "Replaced by newer version"
        ERROR = "error", "Data error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_ref = models.CharField(
        max_length=120,
        unique=True,
        help_text="Canonical reference e.g. pyq:cma:inter:taxation:2024-06",
    )
    course = models.ForeignKey("syllabus.Course", on_delete=models.CASCADE, related_name="pyq_papers")
    level = models.ForeignKey("syllabus.Level", on_delete=models.CASCADE, related_name="pyq_papers")
    subject_key = models.CharField(max_length=80, db_index=True)
    subject = models.ForeignKey(
        "syllabus.Subject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pyq_papers",
    )
    term_code = models.CharField(
        max_length=7,
        validators=[
            RegexValidator(r"^[0-9]{4}-(0[1-9]|1[0-2])$", "Term code must be in YYYY-MM format"),
        ],
        db_index=True,
    )
    exam_date = models.DateField(null=True, blank=True)
    variant = models.CharField(max_length=80, blank=True, default="")
    scheme = models.ForeignKey(
        "syllabus.Scheme",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pyq_papers",
    )
    syllabus_status = models.CharField(
        max_length=20,
        choices=SyllabusStatus.choices,
        default=SyllabusStatus.UNMAPPED,
    )
    title = models.CharField(max_length=200)
    paper_code = models.CharField(max_length=32, blank=True, default="")
    duration_minutes = models.SmallIntegerField(null=True, blank=True)
    reading_minutes = models.SmallIntegerField(default=0)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("100.00"))
    marks_note = models.TextField(blank=True, default="")
    law_note = models.CharField(max_length=300, blank=True, default="")
    delivery = models.CharField(max_length=16, choices=Delivery.choices, default=Delivery.LINK_OUT)
    rights_basis = models.CharField(max_length=24, choices=RightsBasis.choices, blank=True, default="")
    permission_ref = models.CharField(max_length=120, blank=True, default="")
    source_name = models.CharField(max_length=64, blank=True, default="")
    ingestion_item_id = models.UUIDField(null=True, blank=True)
    answers_status = models.CharField(max_length=16, choices=AnswersStatus.choices, default=AnswersStatus.NONE)
    question_count = models.SmallIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    withdrawn_reason = models.CharField(max_length=24, choices=WithdrawnReason.choices, blank=True, default="")
    replaced_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predecessors",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    schema_version = models.SmallIntegerField(default=1)
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pyq_paper"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "level", "subject_key", "term_code", "variant"],
                name="uq_pyq_paper_course_lvl_subj_term_var",
            ),
        ]
        indexes = [
            models.Index(fields=["level", "subject_key", "-term_code"], name="pyq_p_lvl_sbj_trm_idx"),
            models.Index(fields=["syllabus_status"], name="pyq_p_syl_stat_idx"),
            models.Index(fields=["status", "updated_at"], name="pyq_p_stat_upd_idx"),
        ]

    def __str__(self) -> str:
        return f"PyqPaper({self.external_ref}, {self.title})"


class ChoiceGroup(models.Model):
    class RuleKind(models.TextChoices):
        COMPULSORY = "compulsory", "Compulsory"
        ANY_N_OF_M = "any_n_of_m", "Answer any N of M"
        EITHER_OR = "either_or", "Either / Or"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey(PyqPaper, on_delete=models.CASCADE, related_name="choice_groups")
    label = models.CharField(max_length=200)
    rule_kind = models.CharField(max_length=20, choices=RuleKind.choices, default=RuleKind.COMPULSORY)
    pick_count = models.SmallIntegerField(default=1)
    of_count = models.SmallIntegerField(default=1)
    section_label = models.CharField(max_length=60, blank=True, default="")
    sort_order = models.SmallIntegerField(default=0)

    class Meta:
        db_table = "pyq_choicegroup"
        constraints = [
            models.UniqueConstraint(fields=["paper", "sort_order"], name="uq_pyq_choicegrp_paper_sort"),
        ]
        indexes = [
            models.Index(fields=["paper"], name="pyq_cg_paper_idx"),
        ]

    def __str__(self) -> str:
        return f"ChoiceGroup({self.paper.external_ref}: {self.label})"


class PaperQuestion(models.Model):
    class MappingState(models.TextChoices):
        PENDING = "pending", "Pending confirmation"
        CONFIRMED = "confirmed", "Confirmed"

    class SchemeRelation(models.TextChoices):
        CURRENT = "current", "Current syllabus"
        MAPPED = "mapped", "Mapped to current topic"
        CHANGED = "changed", "Topic content changed"
        OUT_OF_SCHEME = "out_of_scheme", "Out of syllabus"
        UNMAPPED = "unmapped", "Unmapped"

    class AnswerSource(models.TextChoices):
        NONE = "none", "None"
        ICAI_SUGGESTED = "icai_suggested", "ICAI Suggested Answer"
        ICMAI_SUGGESTED = "icmai_suggested", "ICMAI Suggested Answer"
        ICSI_GUIDELINES = "icsi_guidelines", "ICSI Guidelines"
        PLATFORM_ORIGINAL = "platform_original", "Platform Original"

    class Status(models.TextChoices):
        LIVE = "live", "Live"
        UNAVAILABLE = "unavailable", "Unavailable / Takedown"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey(PyqPaper, on_delete=models.CASCADE, related_name="questions")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    number_label = models.CharField(max_length=32)
    depth = models.SmallIntegerField(default=0)
    sort_order = models.SmallIntegerField(default=0)
    is_leaf = models.BooleanField(default=True)
    question = models.ForeignKey(
        "questionbank.Question",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="pyq_appearances",
    )
    marks = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    choice_group = models.ForeignKey(
        ChoiceGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
    )
    kind = models.CharField(max_length=32, default="long_form")
    descriptor = models.CharField(max_length=200, blank=True, default="")
    chapter = models.ForeignKey(
        "syllabus.Chapter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pyq_questions",
    )
    chapter_key = models.CharField(max_length=80, blank=True, default="")
    topic_id = models.UUIDField(null=True, blank=True)
    mapping_state = models.CharField(
        max_length=20,
        choices=MappingState.choices,
        default=MappingState.PENDING,
    )
    scheme_relation = models.CharField(
        max_length=20,
        choices=SchemeRelation.choices,
        default=SchemeRelation.UNMAPPED,
    )
    answer_source = models.CharField(
        max_length=24,
        choices=AnswerSource.choices,
        default=AnswerSource.NONE,
    )
    answer_page_hint = models.CharField(max_length=32, blank=True, default="")
    source_page_hint = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.LIVE)

    class Meta:
        db_table = "pyq_paperquestion"
        constraints = [
            models.UniqueConstraint(fields=["paper", "number_label"], name="uq_pyq_paperq_paper_num"),
        ]
        indexes = [
            models.Index(fields=["paper", "sort_order"], name="pyq_pq_paper_sort_idx"),
            models.Index(fields=["chapter", "paper"], name="pyq_pq_ch_paper_idx"),
            models.Index(fields=["question"], name="pyq_pq_q_idx"),
            models.Index(fields=["scheme_relation"], name="pyq_pq_sch_rel_idx"),
        ]

    def __str__(self) -> str:
        return f"PaperQuestion({self.paper.external_ref}: Q.{self.number_label})"


class PaperLink(models.Model):
    class LinkKind(models.TextChoices):
        PAPER = "paper", "Question Paper PDF"
        SUGGESTED_ANSWERS = "suggested_answers", "Suggested Answers PDF"
        EXAMINER_REMARKS = "examiner_remarks", "Examiner Remarks PDF"
        OTHER = "other", "Other Reference"

    class LinkStatus(models.TextChoices):
        UNCHECKED = "unchecked", "Unchecked"
        OK = "ok", "OK"
        FAILING = "failing", "Failing"
        BROKEN = "broken", "Broken"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey(PyqPaper, on_delete=models.CASCADE, related_name="links")
    link_kind = models.CharField(max_length=24, choices=LinkKind.choices)
    label = models.CharField(max_length=120, blank=True, default="")
    url = models.URLField(max_length=500)
    host = models.CharField(max_length=120, blank=True, default="")
    page_hint = models.CharField(max_length=32, blank=True, default="")
    link_status = models.CharField(max_length=16, choices=LinkStatus.choices, default=LinkStatus.UNCHECKED)
    link_checked_at = models.DateTimeField(null=True, blank=True)
    fail_count = models.SmallIntegerField(default=0)
    verified = models.BooleanField(default=False)

    class Meta:
        db_table = "pyq_paperlink"
        constraints = [
            models.UniqueConstraint(fields=["paper", "link_kind", "url"], name="uq_pyq_paperlink_kind_url"),
        ]
        indexes = [
            models.Index(fields=["paper"], name="pyq_pl_paper_idx"),
            models.Index(fields=["link_status", "link_checked_at"], name="pyq_pl_stat_chk_idx"),
        ]

    def __str__(self) -> str:
        return f"PaperLink({self.paper.external_ref}: {self.link_kind} -> {self.url})"


class AskedCache(models.Model):
    """
    Cached frequency statistics from F-11 for high-speed chapter list sort and chips.
    No statistics are derived in F-09; values are mirrored from F-11.
    """

    question = models.OneToOneField(
        "questionbank.Question",
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="pyq_asked_cache",
    )
    asked_n = models.SmallIntegerField(default=0)
    window_n = models.SmallIntegerField(default=0)
    last_term_code = models.CharField(max_length=7, blank=True, default="")
    source_stamp = models.CharField(max_length=64, default="")
    refreshed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "pyq_askedcache"
        indexes = [
            models.Index(fields=["refreshed_at"], name="pyq_ac_refr_idx"),
        ]

    def __str__(self) -> str:
        return f"AskedCache(Q:{self.question_id}, asked={self.asked_n})"


class DailySet(models.Model):
    class PoolKind(models.TextChoices):
        PYQ_HOSTED = "pyq_hosted", "PYQ Hosted Questions"
        MIXED_FALLBACK = "mixed_fallback", "Mixed with Platform Originals"

    class Status(models.TextChoices):
        GENERATING = "generating", "Generating"
        PUBLISHED = "published", "Published"
        WITHDRAWN = "withdrawn", "Withdrawn"
        SKIPPED = "skipped", "Skipped"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    level = models.ForeignKey("syllabus.Level", on_delete=models.CASCADE, related_name="pyq_daily_sets")
    local_date = models.DateField(db_index=True)
    seed = models.CharField(max_length=64, default="")
    pool_kind = models.CharField(max_length=20, choices=PoolKind.choices, default=PoolKind.PYQ_HOSTED)
    pool_size = models.IntegerField(default=0)
    item_count = models.SmallIntegerField(default=5)
    time_limit_seconds = models.IntegerField(default=480)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.GENERATING)
    skip_reason = models.CharField(max_length=32, blank=True, default="")
    generated_by = models.CharField(max_length=64, default="job")
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pyq_dailyset"
        constraints = [
            models.UniqueConstraint(fields=["level", "local_date"], name="uq_pyq_dailyset_lvl_date"),
        ]
        indexes = [
            models.Index(fields=["-local_date", "level"], name="pyq_ds_date_lvl_idx"),
        ]

    def __str__(self) -> str:
        return f"DailySet({self.level_id}: {self.local_date}, status={self.status})"


class DailySetItem(models.Model):
    set = models.ForeignKey(DailySet, on_delete=models.CASCADE, related_name="items")
    position = models.SmallIntegerField()
    question = models.ForeignKey("questionbank.Question", on_delete=models.RESTRICT)
    question_version_id = models.UUIDField()
    paper_question = models.ForeignKey(
        PaperQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_items",
    )
    marks = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))
    difficulty_band = models.CharField(max_length=16, default="medium")

    class Meta:
        db_table = "pyq_dailysetitem"
        constraints = [
            models.UniqueConstraint(fields=["set", "position"], name="uq_pyq_dailysetitem_set_pos"),
        ]
        indexes = [
            models.Index(fields=["question"], name="pyq_dsi_q_idx"),
        ]

    def __str__(self) -> str:
        return f"DailySetItem({self.set_id} pos={self.position} Q={self.question_id})"
