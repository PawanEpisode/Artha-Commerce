"""
Practice Engine Models (F-06 ERD 2.19 - 2.25, E-F06-1).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models
from django.utils import timezone


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Session(TimeStampedModel):
    class Mode(models.TextChoices):
        UNTIMED = "untimed", "Untimed practice"
        TIMED = "timed", "Timed practice"
        CHAPTER_QUIZ = "chapter_quiz", "Chapter quiz"
        REVISION = "revision", "Spaced revision"
        CUSTOM_TEST = "custom_test", "Custom test"
        EXAM = "exam", "Exam simulation"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        IN_PROGRESS = "in_progress", "In progress"
        PAUSED = "paused", "Paused"
        SUBMITTED = "submitted", "Submitted"
        AUTO_SUBMITTED = "auto_submitted", "Auto-submitted (timeout)"
        ABANDONED = "abandoned", "Abandoned"

    class FeedbackPolicy(models.TextChoices):
        INSTANT = "instant", "Instant feedback per question"
        AFTER_SECTION = "after_section", "Feedback after section"
        AT_END = "at_end", "Feedback at end of session"
        NEVER_UNTIL_SUBMIT = "never_until_submit", "No feedback until submitted"

    class ScoringProfile(models.TextChoices):
        PRACTICE = "practice", "Practice (no penalty unless chosen)"
        OFFICIAL = "official", "Official exam pattern rules"

    class ScoreStatus(models.TextChoices):
        NONE = "none", "None"
        FINAL = "final", "Final"
        PROVISIONAL = "provisional", "Provisional (awaiting manual/long-form grading)"

    user_id = models.UUIDField(db_index=True)
    client_id = models.UUIDField()
    mode = models.CharField(max_length=32, choices=Mode.choices, default=Mode.UNTIMED)
    origin_module = models.CharField(max_length=32, default="questionbank")
    origin_ref = models.CharField(max_length=200, null=True, blank=True)  # noqa: DJ001
    title = models.CharField(max_length=200, blank=True, default="")
    picker = models.CharField(max_length=64)
    spec = models.JSONField(default=dict)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CREATED)
    feedback_policy = models.CharField(max_length=32, choices=FeedbackPolicy.choices, default=FeedbackPolicy.AT_END)
    scoring_profile = models.CharField(max_length=32, choices=ScoringProfile.choices, default=ScoringProfile.PRACTICE)
    scoring_snapshot = models.JSONField(default=dict)
    shuffle_seed = models.IntegerField(default=0)
    question_count = models.SmallIntegerField(default=0)
    removed_count = models.SmallIntegerField(default=0)
    total_marks = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    time_limit_seconds = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    paused_total_seconds = models.IntegerField(default=0)
    active_seconds = models.IntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    last_active_at = models.DateTimeField(default=timezone.now)

    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    score_status = models.CharField(max_length=32, choices=ScoreStatus.choices, default=ScoreStatus.NONE)
    answered_count = models.SmallIntegerField(default=0)
    correct_count = models.SmallIntegerField(default=0)
    incorrect_count = models.SmallIntegerField(default=0)
    partial_count = models.SmallIntegerField(default=0)
    skipped_count = models.SmallIntegerField(default=0)
    pending_count = models.SmallIntegerField(default=0)

    tz = models.CharField(max_length=64, default="Asia/Kolkata")
    local_date = models.DateField()
    retake_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="retakes")
    share_link_id = models.UUIDField(null=True, blank=True)
    rev = models.IntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "practice_session"
        indexes = [
            models.Index(fields=["user_id", "status", "-last_active_at"], name="qb_sess_usr_stat_idx"),
            models.Index(fields=["user_id", "-submitted_at"], name="qb_sess_usr_sub_idx"),
            models.Index(fields=["status", "last_active_at"], name="qb_sess_stat_act_idx"),
            models.Index(fields=["origin_module", "origin_ref"], name="qb_sess_orig_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user_id", "client_id"], name="uq_practice_session_client"),
        ]

    def __str__(self) -> str:
        return f"PracticeSession({self.id}, user={self.user_id}, status={self.status})"


class AttemptAnswer(models.Model):
    class Status(models.TextChoices):
        UNSEEN = "unseen", "Unseen"
        SEEN = "seen", "Seen"
        ANSWERED = "answered", "Answered"
        SKIPPED = "skipped", "Skipped"
        PENDING_EVALUATION = "pending_evaluation", "Pending evaluation"
        GRADED = "graded", "Graded"
        REMOVED = "removed", "Removed (takedown)"

    class Result(models.TextChoices):
        CORRECT = "correct", "Correct"
        INCORRECT = "incorrect", "Incorrect"
        PARTIAL = "partial", "Partial credit"
        SKIPPED = "skipped", "Skipped"
        PENDING = "pending", "Pending"
        UNGRADED = "ungraded", "Ungraded"
        REMOVED = "removed", "Removed"

    class GradingSource(models.TextChoices):
        AUTO = "auto", "Automatic"
        SELF = "self", "Self-graded"
        AI = "ai", "AI evaluation"
        MANUAL = "manual", "Manual review"
        REGRADE = "regrade", "Regrade batch"

    class MistakeReason(models.TextChoices):
        CONCEPT = "concept", "Concept confusion"
        SILLY = "silly", "Silly mistake / misread"
        CALCULATION = "calculation", "Calculation error"
        TIME = "time", "Ran out of time"
        NOT_READ = "not_read", "Question not read carefully"
        FORGOT = "forgot", "Formula or provision forgotten"
        GUESS = "guess", "Blind guess"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(db_index=True)  # Equal to session.created_at (partition key)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="answers")
    user_id = models.UUIDField(db_index=True)
    position = models.SmallIntegerField()
    question_id = models.UUIDField(db_index=True)
    question_version_id = models.UUIDField()
    group_question_id = models.UUIDField(null=True, blank=True)
    kind = models.CharField(max_length=32)
    chapter_id = models.UUIDField(null=True, blank=True, db_index=True)
    subject_id = models.UUIDField(null=True, blank=True)
    section_label = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.UNSEEN)
    selected_option_ids = models.JSONField(default=list, blank=True)
    numeric_value = models.DecimalField(max_digits=24, decimal_places=6, null=True, blank=True)
    numeric_unit = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001
    submission_id = models.UUIDField(null=True, blank=True)
    result = models.CharField(max_length=32, choices=Result.choices, null=True, blank=True)  # noqa: DJ001
    marks_max = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"))
    negative_max = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    marks_awarded = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    negative_applied = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    grading_source = models.CharField(max_length=32, choices=GradingSource.choices, null=True, blank=True)  # noqa: DJ001
    graded_at = models.DateTimeField(null=True, blank=True)
    time_spent_ms = models.IntegerField(default=0)
    first_seen_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    answer_changes = models.SmallIntegerField(default=0)
    marked_for_review = models.BooleanField(default=False)
    doubt = models.BooleanField(default=False)
    confidence = models.SmallIntegerField(null=True, blank=True)  # 1: sure, 2: unsure, 3: guess
    mistake_reason = models.CharField(max_length=32, choices=MistakeReason.choices, null=True, blank=True)  # noqa: DJ001
    client_ts = models.DateTimeField(null=True, blank=True)
    rev = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "practice_attemptanswer"
        indexes = [
            models.Index(fields=["user_id", "question_id", "-created_at"], name="qb_att_usr_q_idx"),
            models.Index(fields=["user_id", "-created_at"], name="qb_att_usr_res_idx"),
            models.Index(fields=["session", "position"], name="qb_att_sess_pos_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["session", "position", "created_at"], name="uq_practice_attempt_pos"),
        ]

    def __str__(self) -> str:
        return f"AttemptAnswer({self.id}, session={self.session_id}, pos={self.position})"


class Submission(TimeStampedModel):
    class InputMode(models.TextChoices):
        TYPED = "typed", "Typed text"
        PHOTOS = "photos", "Photo upload"
        BOTH = "both", "Typed and photos"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        EVALUATING = "evaluating", "Evaluating"
        SELF_GRADED = "self_graded", "Self-graded"
        EVALUATED = "evaluated", "Evaluated"
        FAILED = "failed", "Evaluation failed"
        WITHDRAWN = "withdrawn", "Withdrawn"

    user_id = models.UUIDField(db_index=True)
    client_id = models.UUIDField()
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="submissions")
    answer_position = models.SmallIntegerField()
    question_id = models.UUIDField()
    question_version_id = models.UUIDField()
    input_mode = models.CharField(max_length=16, choices=InputMode.choices, default=InputMode.TYPED)
    text_md = models.TextField(blank=True, default="")
    word_count = models.IntegerField(default=0)
    page_count = models.SmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    self_steps = models.JSONField(default=list, blank=True)
    marks_awarded = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    marks_max = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    marks_source = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001
    evaluation_ref = models.UUIDField(null=True, blank=True)
    evaluation_state = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001
    retention_until = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "practice_submission"
        indexes = [
            models.Index(fields=["user_id", "-submitted_at"], name="qb_subm_usr_sub_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user_id", "client_id"], name="uq_practice_subm_client"),
        ]

    def __str__(self) -> str:
        return f"Submission({self.id}, user={self.user_id}, status={self.status})"


class SubmissionPage(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="pages")
    position = models.SmallIntegerField()
    attachment = models.ForeignKey("media.Attachment", on_delete=models.CASCADE, related_name="+")
    rotation = models.SmallIntegerField(default=0)
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "practice_submissionpage"
        constraints = [
            models.UniqueConstraint(fields=["submission", "position"], name="uq_practice_submpage_pos"),
            models.UniqueConstraint(fields=["attachment"], name="uq_practice_submpage_att"),
        ]

    def __str__(self) -> str:
        return f"SubmissionPage({self.submission_id}, pos={self.position})"


class ScoringRule(UUIDModel):
    class CorrectMode(models.TextChoices):
        QUESTION_MARKS = "question_marks", "Question marks"
        FIXED = "fixed", "Fixed marks"

    class NegativeMode(models.TextChoices):
        NONE = "none", "No negative marking"
        FRACTION_OF_MARKS = "fraction_of_marks", "Fraction of question marks"
        FIXED = "fixed", "Fixed penalty"

    class MultiMode(models.TextChoices):
        ALL_OR_NOTHING = "all_or_nothing", "All or nothing"
        PARTIAL_WITH_PENALTY = "partial_with_penalty", "Partial with penalty"
        PROPORTIONAL = "proportional", "Proportional to correct choices"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    course = models.ForeignKey("syllabus.Course", on_delete=models.RESTRICT, related_name="+")
    level = models.ForeignKey("syllabus.Level", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    subject_key = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001
    question_kind = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001
    correct_mode = models.CharField(max_length=32, choices=CorrectMode.choices, default=CorrectMode.QUESTION_MARKS)
    fixed_correct_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    negative_mode = models.CharField(max_length=32, choices=NegativeMode.choices, default=NegativeMode.NONE)
    negative_value = models.DecimalField(max_digits=5, decimal_places=3, default=Decimal("0.000"))
    skip_marks = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.00"))
    multi_mode = models.CharField(max_length=32, choices=MultiMode.choices, default=MultiMode.ALL_OR_NOTHING)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    verified = models.BooleanField(default=False)
    source_note = models.TextField(blank=True, default="")
    source_url = models.URLField(blank=True, default="")
    verified_by = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "practice_scoringrule"

    def __str__(self) -> str:
        return f"ScoringRule({self.id}, course={self.course_id}, status={self.status}, verified={self.verified})"


class QuestionState(models.Model):
    user_id = models.UUIDField(db_index=True)
    question_id = models.UUIDField(db_index=True)
    chapter_id = models.UUIDField(null=True, blank=True, db_index=True)  # Extension E-F06-1
    bookmarked = models.BooleanField(default=False)
    bookmarked_at = models.DateTimeField(null=True, blank=True)
    doubt = models.BooleanField(default=False)
    note = models.TextField(blank=True, default="")
    attempts = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)
    last_result = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001
    last_answer_session_id = models.UUIDField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_time_ms = models.IntegerField(null=True, blank=True)
    avg_time_ms = models.IntegerField(null=True, blank=True)
    correct_streak = models.SmallIntegerField(default=0)
    last_mistake_reason = models.CharField(max_length=32, null=True, blank=True)  # noqa: DJ001
    box = models.SmallIntegerField(default=0)
    next_review_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "practice_questionstate"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "question_id"], name="uq_practice_qstate_usr_q"),
        ]
        indexes = [
            models.Index(fields=["user_id", "chapter_id"], name="qb_qstate_usr_ch_idx"),
            models.Index(fields=["user_id", "next_review_at"], name="qb_qstate_usr_rev_idx"),
            models.Index(fields=["user_id", "-last_attempt_at"], name="qb_qstate_usr_att_idx"),
            models.Index(fields=["user_id", "-bookmarked_at"], name="qb_qstate_usr_bkm_idx"),
        ]

    def __str__(self) -> str:
        return f"QuestionState(user={self.user_id}, q={self.question_id}, attempts={self.attempts})"

    @property
    def notes(self) -> str:
        return self.note

    @notes.setter
    def notes(self, value: str) -> None:
        self.note = value


class DailyRollup(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_id = models.UUIDField(db_index=True)
    local_date = models.DateField()
    chapter_id = models.UUIDField(null=True, blank=True)
    subject_id = models.UUIDField(null=True, blank=True)
    kind = models.CharField(max_length=32, default="all")
    answered = models.IntegerField(default=0)
    correct = models.IntegerField(default=0)
    incorrect = models.IntegerField(default=0)
    partial = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    time_ms = models.BigIntegerField(default=0)
    marks = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    marks_max = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    self_graded_marks = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "practice_dailyrollup"
        indexes = [
            models.Index(fields=["user_id", "local_date"], name="qb_droll_usr_date_idx"),
            models.Index(fields=["user_id", "chapter_id", "local_date"], name="qb_droll_usr_ch_date_idx"),
        ]

    def __str__(self) -> str:
        return f"DailyRollup(user={self.user_id}, date={self.local_date}, answered={self.answered})"


class RegradeJob(UUIDModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    question_id = models.UUIDField()
    from_version_id = models.UUIDField()
    to_version_id = models.UUIDField()
    requested_by = models.UUIDField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    affected_answers = models.IntegerField(default=0)
    changed_answers = models.IntegerField(default=0)
    score_delta_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    notify_students = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "practice_regradejob"

    def __str__(self) -> str:
        return f"RegradeJob({self.id}, q={self.question_id}, status={self.status})"


class Settings(models.Model):
    user_id = models.UUIDField(primary_key=True)
    default_mode = models.CharField(max_length=32, choices=Session.Mode.choices, default=Session.Mode.UNTIMED)
    default_count = models.SmallIntegerField(default=10)
    shuffle_options = models.BooleanField(default=True)
    auto_advance = models.BooleanField(default=False)
    show_timer = models.BooleanField(default=True)
    keyboard_shortcuts = models.BooleanField(default=True)
    text_size = models.SmallIntegerField(default=0)
    official_scoring_default = models.BooleanField(default=False)
    tz = models.CharField(max_length=64, default="Asia/Kolkata")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "practice_settings"

    def __str__(self) -> str:
        return f"PracticeSettings(user={self.user_id}, mode={self.default_mode})"
