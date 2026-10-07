"""
Tables for the Pomodoro focus timer (F-01.1). Finished rounds are `tracking_studysession` rows written through the
tracking service; this app only owns the live timer and the student's timer settings. The daily goal and streak are the
tracker's (one shared goal), so there is no goal column or summary table here. `user_id` holds the Supabase user id by
value (no cross-schema foreign key).
"""

from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from modules.tracking.domain.durations import ACTIVITY_TYPES

PRESET_CHOICES = [("classic", "Classic"), ("deep", "Deep"), ("light", "Light"), ("custom", "Custom")]
ACTIVITY_CHOICES = [(a, a) for a in ACTIVITY_TYPES]
PHASE_CHOICES = [("focus", "Focus"), ("short_break", "Short break"), ("long_break", "Long break")]
POPOUT_SIZE_CHOICES = [("pill", "Pill"), ("card", "Card")]


class FocusSettings(TimeStampedModel):
    user_id = models.UUIDField(primary_key=True)
    last_preset = models.CharField(max_length=7, choices=PRESET_CHOICES, default="classic")
    focus_minutes = models.SmallIntegerField(default=25)
    short_break_minutes = models.SmallIntegerField(default=5)
    long_break_minutes = models.SmallIntegerField(default=15)
    rounds_before_long = models.SmallIntegerField(default=4)
    auto_start_breaks = models.BooleanField(default=True)
    auto_start_focus = models.BooleanField(default=False)
    # Keep a focus round running past its planned length until the student stops it (then the break starts).
    overtime_enabled = models.BooleanField(default=True)
    sound_enabled = models.BooleanField(default=True)
    volume = models.SmallIntegerField(default=70)
    notifications_enabled = models.BooleanField(default=False)
    # Hold the screen awake while a round runs (X-01 keep awake). Breaks only when the second switch is on too.
    keep_awake = models.BooleanField(default=True)
    keep_awake_in_breaks = models.BooleanField(default=False)
    # The floating timer (X-01 P4). `popout_prompt_seen` is set when the start-of-round prompt is shown, not when answered.
    popout_on_start = models.BooleanField(default=False)
    popout_size = models.CharField(max_length=4, choices=POPOUT_SIZE_CHOICES, default="pill")
    popout_prompt_seen = models.BooleanField(default=False)
    intro_seen = models.BooleanField(default=False)
    # The remembered cycle: when a phase ends and nothing starts on its own the timer goes idle, but the round count and
    # the phase that is due next carry on ("Start round 3 of 4", "Start break").
    cycle_id = models.UUIDField(null=True, blank=True)
    cycle_round = models.SmallIntegerField(default=0)  # focus rounds finished in this cycle
    cycle_next_phase = models.CharField(max_length=11, choices=PHASE_CHOICES, default="focus")
    cycle_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "focus_focussettings"
        constraints = [
            models.CheckConstraint(
                condition=Q(last_preset__in=["classic", "deep", "light", "custom"]), name="focus_settings_preset_valid"
            ),
            models.CheckConstraint(
                condition=Q(focus_minutes__gte=5, focus_minutes__lte=120), name="focus_settings_focus_range"
            ),
            models.CheckConstraint(
                condition=Q(short_break_minutes__gte=1, short_break_minutes__lte=30), name="focus_settings_short_range"
            ),
            models.CheckConstraint(
                condition=Q(long_break_minutes__gte=5, long_break_minutes__lte=60), name="focus_settings_long_range"
            ),
            models.CheckConstraint(
                condition=Q(rounds_before_long__gte=2, rounds_before_long__lte=8), name="focus_settings_rounds_range"
            ),
            models.CheckConstraint(condition=Q(volume__gte=0, volume__lte=100), name="focus_settings_volume_range"),
            models.CheckConstraint(
                condition=Q(popout_size__in=["pill", "card"]), name="focus_settings_popout_size_valid"
            ),
            models.CheckConstraint(
                condition=Q(cycle_round__gte=0, cycle_round__lte=8), name="focus_settings_cycle_round"
            ),
            models.CheckConstraint(
                condition=Q(cycle_next_phase__in=["focus", "short_break", "long_break"]),
                name="focus_settings_cycle_phase",
            ),
        ]


class ActiveTimer(TimeStampedModel):
    """The live phase. One row per student (the primary key), present only while a focus or break phase is running."""

    user_id = models.UUIDField(primary_key=True)
    phase = models.CharField(max_length=11, choices=PHASE_CHOICES)
    round_number = models.SmallIntegerField()
    cycle_id = models.UUIDField()
    planned_seconds = models.IntegerField()
    extension_count = models.SmallIntegerField(default=0)
    started_at = models.DateTimeField()
    paused_at = models.DateTimeField(null=True, blank=True)
    paused_total_seconds = models.IntegerField(default=0)
    pause_count = models.SmallIntegerField(default=0)
    last_seen_at = models.DateTimeField()
    # A focus round ran out while the student was away; they choose to count it or not (`claim`).
    away_pending = models.BooleanField(default=False)
    preset = models.CharField(max_length=7, choices=PRESET_CHOICES, default="classic")
    focus_minutes = models.SmallIntegerField()
    short_break_minutes = models.SmallIntegerField()
    long_break_minutes = models.SmallIntegerField()
    rounds_before_long = models.SmallIntegerField()
    auto_start_breaks = models.BooleanField(default=True)
    auto_start_focus = models.BooleanField(default=False)
    # Snapshot of the setting when the round started, like the other `auto_*` flags. Rows from before default to off.
    overtime_enabled = models.BooleanField(default=False)
    subject = models.ForeignKey("syllabus.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    chapter = models.ForeignKey("syllabus.Chapter", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    activity_type = models.CharField(max_length=10, choices=ACTIVITY_CHOICES, default="other")
    client_id = models.UUIDField()
    version = models.IntegerField(default=1)

    class Meta:
        db_table = "focus_activetimer"
        constraints = [
            models.CheckConstraint(
                condition=Q(phase__in=["focus", "short_break", "long_break"]), name="focus_timer_phase_valid"
            ),
            models.CheckConstraint(
                condition=Q(planned_seconds__gte=60, planned_seconds__lte=14400), name="focus_timer_planned_range"
            ),
            models.CheckConstraint(
                condition=Q(extension_count__gte=0, extension_count__lte=3), name="focus_timer_extension_range"
            ),
            models.CheckConstraint(condition=Q(paused_total_seconds__gte=0), name="focus_timer_pause_total"),
            models.CheckConstraint(condition=Q(round_number__gte=1, round_number__lte=8), name="focus_timer_round"),
            models.CheckConstraint(
                condition=Q(away_pending=False) | Q(phase="focus"), name="focus_timer_away_only_focus"
            ),
        ]
