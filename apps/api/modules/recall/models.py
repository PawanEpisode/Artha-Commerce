"""
Tables for the recall system (F-15, release R1). See docs/product/erd/F-15-recall-system.md section 2.

R1 creates content (items, versions, decks, snapshots), the student's state (settings, subscriptions, cards, sessions,
schedule events, parameter sets), the review log, rollups, the quota tables, the report table and the audit log. Sharing and
AI tables arrive with R2 and R3 as additive migrations.

Conventions
- `user_id` holds the Supabase user id by value (no cross-schema foreign key) and scopes every query.
- Every enum is `text` with a check constraint. List-valued columns (tags, reference keys, flags, steps, weights) are JSON
  lists, not PostgreSQL arrays, so the quick tests run on SQLite (the repo has no array columns); containment indexes for the
  two that are searched are created on PostgreSQL only (migration 0001). Services validate the lists.
- `RecallReviewLog` is created by raw SQL (a hash partitioned table with an immutability trigger on PostgreSQL, a plain table on
  SQLite), so its model is unmanaged. Derived columns on it may only be rewritten by the replay service.
- Foreign keys to the syllabus are `restrict`, as in Notes; stable key copies keep rows valid across a scheme switch.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel, UUIDModel

from .domain.limits import SCHEDULER_VERSION


def default_learning_steps() -> list[int]:
    return [1, 10]


def default_relearning_steps() -> list[int]:
    return [10]


def in_(field: str, values, name: str) -> models.CheckConstraint:
    """A check constraint that a text enum column holds one of `values`."""
    return models.CheckConstraint(condition=Q(**{f"{field}__in": list(values)}), name=name)


# --------------------------------------------------------------------------------------------- content


ITEM_KINDS = ("pointer", "formula", "section", "definition", "mnemonic", "case_law", "cloze")
ITEM_OWNERSHIPS = ("platform", "user")
ITEM_ORIGINS = (
    "manual", "selection", "solution", "mistake", "ai_suggestion", "import_csv", "import_share", "editor", "fork",
    "amendment_card", "material_item", "super50_entry",
)  # fmt: skip
ITEM_STATUSES = ("active", "archived", "withdrawn", "deleted")
ITEM_IMPORTANCES = ("bullet", "important", "mandatory")
ITEM_RIGHTS = ("original", "licensed", "institute_material", "third_party_claimed", "unknown")
ITEM_ORIGIN_MODULES = ("notes", "questionbank", "amendments", "study_material", "super50")
ITEM_CHECK_REASONS = ("amendment", "report", "rights")


class RecallItem(UUIDModel):
    KINDS = ITEM_KINDS
    OWNERSHIPS = ITEM_OWNERSHIPS
    ORIGINS = ITEM_ORIGINS
    STATUSES = ITEM_STATUSES
    IMPORTANCES = ITEM_IMPORTANCES
    RIGHTS = ITEM_RIGHTS
    ORIGIN_MODULES = ITEM_ORIGIN_MODULES
    CHECK_REASONS = ITEM_CHECK_REASONS
    """Content identity, shared by platform and user. A student's scheduled unit of it is a `RecallCard`."""

    kind = models.CharField(max_length=16)
    ownership = models.CharField(max_length=8)
    owner_user_id = models.UUIDField(null=True, blank=True)
    origin = models.CharField(max_length=24, default="manual")
    status = models.CharField(max_length=10, default="active")
    importance = models.CharField(max_length=10, default="bullet")
    course = models.ForeignKey("syllabus.Course", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    level = models.ForeignKey("syllabus.Level", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    scheme = models.ForeignKey("syllabus.Scheme", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey("syllabus.Subject", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    chapter = models.ForeignKey("syllabus.Chapter", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    topic = models.ForeignKey("syllabus.Topic", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject_key = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001 - NULL is Unsorted
    chapter_key = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001 - NULL is Unsorted
    reference_keys = models.JSONField(default=list, blank=True)  # normalised provision keys, e.g. "cgst:17(5)"
    tags = models.JSONField(default=list, blank=True)  # at most 12, each at most 40 characters
    rights_status = models.CharField(max_length=24, default="unknown")
    source_label = models.CharField(max_length=200, blank=True, default="")
    source_url = models.URLField(max_length=500, null=True, blank=True)  # noqa: DJ001 - NULL means no link; https only
    origin_module = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001 - NULL means not source-created
    origin_ref = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001 - id in the origin module
    origin_kind = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001 - Notes port kind (D2)
    origin_locator = models.JSONField(null=True, blank=True)  # {"v": 1, ...}, schema-less per origin, never card text
    origin_dangling = models.BooleanField(default=False)
    shareable = models.BooleanField(default=False)
    shareable_attested_at = models.DateTimeField(null=True, blank=True)
    forked_from_item = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    live_version = models.ForeignKey(
        "RecallItemVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    current_version = models.ForeignKey(
        "RecallItemVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    needs_editor_check = models.BooleanField(default=False)
    check_reason = models.CharField(max_length=12, null=True, blank=True)  # noqa: DJ001
    check_ref = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001
    fingerprint = models.CharField(max_length=64)  # SHA-256 of the normalised text; duplicate warning
    search_text = models.TextField(blank=True, default="")  # plain text of the live version, at most 10,000 characters
    external_ref = models.CharField(max_length=160, null=True, blank=True)  # noqa: DJ001 - editor import idempotency key
    client_id = models.UUIDField(null=True, blank=True)  # offline create idempotency
    created_by = models.UUIDField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recall_item"
        constraints = [
            in_("kind", ITEM_KINDS, "recall_item_kind_valid"),
            in_("ownership", ITEM_OWNERSHIPS, "recall_item_ownership_valid"),
            in_("origin", ITEM_ORIGINS, "recall_item_origin_valid"),
            in_("status", ITEM_STATUSES, "recall_item_status_valid"),
            in_("importance", ITEM_IMPORTANCES, "recall_item_importance_valid"),
            in_("rights_status", ITEM_RIGHTS, "recall_item_rights_valid"),
            models.CheckConstraint(
                condition=Q(ownership="platform", owner_user_id__isnull=True)
                | Q(ownership="user", owner_user_id__isnull=False),
                name="recall_item_owner_matches_ownership",
            ),
            models.CheckConstraint(
                condition=Q(chapter__isnull=True) | Q(subject_key__isnull=False, chapter_key__isnull=False),
                name="recall_item_chapter_has_keys",
            ),
            models.CheckConstraint(
                condition=Q(fingerprint__regex=r"^[0-9a-f]{64}$"), name="recall_item_fingerprint_hex"
            ),
            models.UniqueConstraint(
                fields=["external_ref"], condition=Q(external_ref__isnull=False), name="recall_item_external_ref_uniq"
            ),
            models.UniqueConstraint(
                fields=["owner_user_id", "client_id"],
                condition=Q(client_id__isnull=False, owner_user_id__isnull=False),
                name="recall_item_client_id_uniq",
            ),
            # Idempotency of source-created cards (D2): one item per student, source object and port kind
            models.UniqueConstraint(
                fields=["owner_user_id", "origin_module", "origin_ref", "origin_kind"],
                condition=Q(origin_ref__isnull=False, origin_kind__isnull=False, status__in=["active", "archived"]),
                name="recall_item_source_kind_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["owner_user_id", "status", "-updated_at"],
                condition=Q(ownership="user"),
                name="recall_item_mine_idx",
            ),
            models.Index(
                fields=["chapter", "importance", "id"],
                condition=Q(ownership="platform", status="active"),
                name="recall_item_library_idx",
            ),
            models.Index(
                fields=["owner_user_id", "fingerprint"], condition=Q(ownership="user"), name="recall_item_dupes_idx"
            ),
            models.Index(
                fields=["forked_from_item"], condition=Q(forked_from_item__isnull=False), name="recall_item_fork_idx"
            ),
            models.Index(
                fields=["needs_editor_check"], condition=Q(needs_editor_check=True), name="recall_item_check_idx"
            ),
        ]


ITEMVERSION_STATES = ("draft", "live", "superseded", "withdrawn")
ITEMVERSION_CHANGE_KINDS = ("create", "typo", "clarify", "substantive", "amendment")


class RecallItemVersion(UUIDModel):
    STATES = ITEMVERSION_STATES
    CHANGE_KINDS = ITEMVERSION_CHANGE_KINDS
    """Immutable once it leaves draft. User items skip draft (created live)."""

    item = models.ForeignKey(RecallItem, on_delete=models.PROTECT, related_name="versions")
    version_no = models.IntegerField()
    state = models.CharField(max_length=12, default="draft")
    change_kind = models.CharField(max_length=12, default="create")
    change_note = models.TextField(blank=True, default="")
    fields = models.JSONField()  # {"v": 1, ...kind fields}; validated by the kind, never trusted from the client
    fields_schema = models.SmallIntegerField(default=1)
    cloze_count = models.SmallIntegerField(default=0)
    content_hash = models.CharField(max_length=64)
    plain_text = models.TextField(blank=True, default="")
    authored_by = models.UUIDField(null=True, blank=True)
    live_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recall_itemversion"
        constraints = [
            in_("state", ITEMVERSION_STATES, "recall_itemversion_state_valid"),
            in_("change_kind", ITEMVERSION_CHANGE_KINDS, "recall_itemversion_change_valid"),
            models.CheckConstraint(
                condition=Q(cloze_count__gte=0, cloze_count__lte=20), name="recall_itemversion_cloze_range"
            ),
            models.UniqueConstraint(fields=["item", "version_no"], name="recall_itemversion_no_uniq"),
            models.UniqueConstraint(fields=["item"], condition=Q(state="live"), name="recall_itemversion_one_live"),
        ]


DECK_KINDS = ("platform", "user")
DECK_STATUSES = ("active", "archived", "withdrawn")


class RecallDeck(UUIDModel):
    KINDS = DECK_KINDS
    STATUSES = DECK_STATUSES

    kind = models.CharField(max_length=8)
    owner_user_id = models.UUIDField(null=True, blank=True)
    slug = models.SlugField(max_length=100, null=True, blank=True)  # noqa: DJ001 - platform only
    title = models.CharField(max_length=80)
    description = models.CharField(max_length=500, blank=True, default="")
    course = models.ForeignKey("syllabus.Course", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    level = models.ForeignKey("syllabus.Level", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey("syllabus.Subject", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    chapter = models.ForeignKey("syllabus.Chapter", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=10, default="active")
    live_version = models.ForeignKey(
        "RecallDeckVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    draft_version = models.ForeignKey(
        "RecallDeckVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    card_count = models.IntegerField(
        default=0
    )  # members of a user deck; the per-deck quota is a conditional UPDATE on it
    client_id = models.UUIDField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recall_deck"
        constraints = [
            in_("kind", DECK_KINDS, "recall_deck_kind_valid"),
            in_("status", DECK_STATUSES, "recall_deck_status_valid"),
            models.CheckConstraint(
                condition=Q(kind="platform", owner_user_id__isnull=True) | Q(kind="user", owner_user_id__isnull=False),
                name="recall_deck_owner_matches_kind",
            ),
            models.CheckConstraint(condition=Q(card_count__gte=0), name="recall_deck_card_count_nonnegative"),
            models.UniqueConstraint(fields=["slug"], condition=Q(slug__isnull=False), name="recall_deck_slug_uniq"),
            models.UniqueConstraint(
                fields=["owner_user_id", "client_id"],
                condition=Q(client_id__isnull=False, owner_user_id__isnull=False),
                name="recall_deck_client_id_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["kind", "status", "chapter"], name="recall_deck_library_idx"),
            models.Index(
                fields=["owner_user_id", "status", "-updated_at"], condition=Q(kind="user"), name="recall_deck_mine_idx"
            ),
        ]


DECKVERSION_STATES = ("draft", "in_review", "live", "superseded", "withdrawn")


class RecallDeckVersion(UUIDModel):
    STATES = DECKVERSION_STATES

    deck = models.ForeignKey(RecallDeck, on_delete=models.PROTECT, related_name="versions")
    version_no = models.IntegerField()
    state = models.CharField(max_length=12, default="draft")
    changelog_md = models.TextField(blank=True, default="")
    item_count = models.SmallIntegerField(default=0)
    tier_counts = models.JSONField(default=dict, blank=True)  # {"v": 1, "mandatory": 14, ...}
    diff_summary = models.JSONField(default=dict, blank=True)  # versus the previous live version
    published_by = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recall_deckversion"
        constraints = [
            in_("state", DECKVERSION_STATES, "recall_deckversion_state_valid"),
            models.UniqueConstraint(fields=["deck", "version_no"], name="recall_deckversion_no_uniq"),
            models.UniqueConstraint(fields=["deck"], condition=Q(state="live"), name="recall_deckversion_one_live"),
        ]


DECKVERSIONITEM_CHANGES = ("added", "unchanged", "typo", "clarify", "substantive", "amendment")


class RecallDeckVersionItem(models.Model):
    CHANGES = DECKVERSIONITEM_CHANGES
    """One row of a deck snapshot: the exact item version a deck version contains."""

    pk = models.CompositePrimaryKey("deck_version_id", "item_id")
    deck_version = models.ForeignKey(RecallDeckVersion, on_delete=models.CASCADE, related_name="rows")
    item = models.ForeignKey(RecallItem, on_delete=models.PROTECT, related_name="+")
    item_version = models.ForeignKey(RecallItemVersion, on_delete=models.PROTECT, related_name="+")
    position = models.SmallIntegerField(default=0)
    change_vs_prev = models.CharField(max_length=12, default="unchanged")

    class Meta:
        db_table = "recall_deckversionitem"
        constraints = [in_("change_vs_prev", DECKVERSIONITEM_CHANGES, "recall_deckversionitem_change_valid")]
        indexes = [models.Index(fields=["item"], name="recall_dvi_item_idx")]

    def __str__(self) -> str:
        return f"RecallDeckVersionItem {self.pk}"


class RecallDeckItem(models.Model):
    """Live membership of a student's own deck. Platform deck membership is the snapshot."""

    pk = models.CompositePrimaryKey("deck_id", "item_id")
    deck = models.ForeignKey(RecallDeck, on_delete=models.CASCADE, related_name="members")
    item = models.ForeignKey(RecallItem, on_delete=models.CASCADE, related_name="+")
    position = models.SmallIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recall_deckitem"
        indexes = [models.Index(fields=["item"], name="recall_deckitem_item_idx")]

    def __str__(self) -> str:
        return f"RecallDeckItem {self.pk}"


# ------------------------------------------------------------------------------------ student state


PARAMS_SCOPES = ("default", "user", "pooled")
PARAMS_STATUSES = ("active", "candidate", "retired", "rejected")


class RecallParams(UUIDModel):
    SCOPES = PARAMS_SCOPES
    STATUSES = PARAMS_STATUSES
    """The 21 weights of a scheduler version. One seeded `default` row; per-student sets arrive later."""

    scope = models.CharField(max_length=8)
    user_id = models.UUIDField(null=True, blank=True)
    scheduler_version = models.CharField(max_length=16, default=SCHEDULER_VERSION)
    weights = (
        models.JSONField()
    )  # exactly 21 numbers for fsrs-6.0 (validated by the domain; PostgreSQL also checks the length)
    status = models.CharField(max_length=10, default="active")
    n_reviews = models.IntegerField(null=True, blank=True)
    n_cards = models.IntegerField(null=True, blank=True)
    fitted_from = models.DateTimeField(null=True, blank=True)
    fitted_to = models.DateTimeField(null=True, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    optimiser = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recall_params"
        constraints = [
            in_("scope", PARAMS_SCOPES, "recall_params_scope_valid"),
            in_("status", PARAMS_STATUSES, "recall_params_status_valid"),
            models.UniqueConstraint(
                fields=["scheduler_version"],
                condition=Q(scope="default", status="active"),
                name="recall_params_one_default",
            ),
            models.UniqueConstraint(
                fields=["user_id"], condition=Q(scope="user", status="active"), name="recall_params_one_per_user"
            ),
        ]


class RecallSettings(TimeStampedModel):
    """One row per student, created on first read."""

    user_id = models.UUIDField(primary_key=True)
    desired_retention = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.90"))
    new_per_day = models.SmallIntegerField(default=10)
    reviews_per_day = models.SmallIntegerField(default=100)
    learning_steps_min = models.JSONField(default=default_learning_steps)  # at most 4, each 1..1440
    relearning_steps_min = models.JSONField(default=default_relearning_steps)  # at most 3
    max_interval_days = models.IntegerField(default=365)
    leech_threshold = models.SmallIntegerField(default=8)
    day_start_hour = models.SmallIntegerField(default=4)
    tz = models.CharField(max_length=64, default="Asia/Kolkata")
    bury_siblings = models.BooleanField(default=True)
    interleave = models.BooleanField(default=True)
    catchup_mode = models.CharField(max_length=8, default="auto")
    pause_new_in_catchup = models.BooleanField(default=True)
    exam_horizon = models.BooleanField(default=True)
    recall_counts_as_revision = models.BooleanField(default=True)
    gestures = models.BooleanField(default=True)
    show_intervals = models.BooleanField(default=True)
    quick_minutes_per_day = models.SmallIntegerField(default=30)
    vacation_until = models.DateField(null=True, blank=True)
    improve_scheduler_consent = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    params = models.ForeignKey(RecallParams, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        db_table = "recall_settings"
        constraints = [
            models.CheckConstraint(
                condition=Q(desired_retention__gte="0.80", desired_retention__lte="0.97"),
                name="recall_settings_retention_range",
            ),
            models.CheckConstraint(
                condition=Q(new_per_day__gte=0, new_per_day__lte=100), name="recall_settings_new_range"
            ),
            models.CheckConstraint(
                condition=Q(reviews_per_day__gte=20, reviews_per_day__lte=500), name="recall_settings_reviews_range"
            ),
            models.CheckConstraint(
                condition=Q(max_interval_days__gte=30, max_interval_days__lte=3650),
                name="recall_settings_interval_range",
            ),
            models.CheckConstraint(
                condition=Q(leech_threshold__gte=4, leech_threshold__lte=20), name="recall_settings_leech_range"
            ),
            models.CheckConstraint(
                condition=Q(day_start_hour__gte=0, day_start_hour__lte=6), name="recall_settings_day_start_range"
            ),
            models.CheckConstraint(
                condition=Q(quick_minutes_per_day__gte=5, quick_minutes_per_day__lte=240),
                name="recall_settings_quick_range",
            ),
            in_("catchup_mode", ("auto", "off", "on"), "recall_settings_catchup_valid"),
        ]


SUBSCRIPTION_UNLOCK_MODES = ("with_coverage", "all")
SUBSCRIPTION_STATUSES = ("active", "archived")


class RecallSubscription(UUIDModel):
    UNLOCK_MODES = SUBSCRIPTION_UNLOCK_MODES
    STATUSES = SUBSCRIPTION_STATUSES

    user_id = models.UUIDField()
    deck = models.ForeignKey(RecallDeck, on_delete=models.PROTECT, related_name="subscriptions")
    pinned_version = models.ForeignKey(RecallDeckVersion, on_delete=models.PROTECT, related_name="+")
    synced_version = models.ForeignKey(RecallDeckVersion, on_delete=models.PROTECT, related_name="+")
    pending_version = models.ForeignKey(
        RecallDeckVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    follow_updates = models.BooleanField(default=True)
    unlock_mode = models.CharField(max_length=14, default="with_coverage")
    min_importance = models.CharField(max_length=10, default="bullet")
    status = models.CharField(max_length=10, default="active")
    subscribed_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recall_subscription"
        constraints = [
            in_("unlock_mode", SUBSCRIPTION_UNLOCK_MODES, "recall_subscription_unlock_valid"),
            in_("status", SUBSCRIPTION_STATUSES, "recall_subscription_status_valid"),
            in_("min_importance", ITEM_IMPORTANCES, "recall_subscription_tier_valid"),
            models.UniqueConstraint(fields=["user_id", "deck"], name="recall_subscription_user_deck_uniq"),
        ]
        indexes = [
            models.Index(fields=["deck", "follow_updates", "status"], name="recall_sub_sync_idx"),
            models.Index(fields=["user_id", "status"], name="recall_sub_user_idx"),
        ]


CARD_STATUSES = ("active", "suspended", "archived", "deleted")
CARD_SUSPEND_REASONS = ("manual", "parked", "leech")
CARD_RECHECK_REASONS = ("content_changed", "amendment")


class RecallCard(UUIDModel):
    STATUSES = CARD_STATUSES
    SUSPEND_REASONS = CARD_SUSPEND_REASONS
    RECHECK_REASONS = CARD_RECHECK_REASONS
    """One student's scheduled unit of an item (and cloze number). The memory columns are a cache of the log."""

    user_id = models.UUIDField()
    item = models.ForeignKey(RecallItem, on_delete=models.PROTECT, related_name="cards")
    ordinal = models.SmallIntegerField(default=0)  # 0 default face, 1..20 cloze number, 100 reverse face
    subscription = models.ForeignKey(
        RecallSubscription, null=True, blank=True, on_delete=models.SET_NULL, related_name="cards"
    )
    item_version = models.ForeignKey(RecallItemVersion, on_delete=models.PROTECT, related_name="+")
    chapter_id = models.UUIDField(null=True, blank=True)  # denormalised for filters, kept in sync by the service
    subject_key = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001
    importance = models.SmallIntegerField(default=0)  # 0 bullet, 1 important, 2 mandatory
    state = models.SmallIntegerField(default=0)  # 0 new, 1 learning, 2 review, 3 relearning
    step = models.SmallIntegerField(null=True, blank=True)
    stability = models.FloatField(null=True, blank=True)  # real on write; days
    difficulty = models.FloatField(null=True, blank=True)
    due_scheduled_at = models.DateTimeField(null=True, blank=True)
    postponed_until = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    last_review_at = models.DateTimeField(null=True, blank=True)
    reps = models.IntegerField(default=0)
    lapses = models.IntegerField(default=0)
    last_lapse_at = models.DateTimeField(null=True, blank=True)
    leech = models.BooleanField(default=False)
    status = models.CharField(max_length=10, default="active")
    suspend_reason = models.CharField(max_length=8, null=True, blank=True)  # noqa: DJ001
    buried_until = models.DateTimeField(null=True, blank=True)
    needs_recheck = models.BooleanField(default=False)
    recheck_reason = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001
    recheck_ref = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001
    scheduler_version = models.CharField(max_length=16, default=SCHEDULER_VERSION)
    params = models.ForeignKey(RecallParams, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    rev = models.IntegerField(default=1)  # incremented on every change; the offline pack carries it
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recall_card"
        constraints = [
            models.UniqueConstraint(fields=["user_id", "item", "ordinal"], name="recall_card_user_item_ordinal_uniq"),
            models.UniqueConstraint(
                fields=["id", "user_id"], name="recall_card_id_user_uniq"
            ),  # target of composite FKs
            in_("status", CARD_STATUSES, "recall_card_status_valid"),
            models.CheckConstraint(condition=Q(state__gte=0, state__lte=3), name="recall_card_state_range"),
            models.CheckConstraint(
                condition=Q(importance__gte=0, importance__lte=2), name="recall_card_importance_range"
            ),
            models.CheckConstraint(
                condition=Q(difficulty__isnull=True) | Q(difficulty__gte=1, difficulty__lte=10),
                name="recall_card_difficulty_range",
            ),
            models.CheckConstraint(
                condition=Q(stability__isnull=True) | Q(stability__gt=0), name="recall_card_stability_positive"
            ),
            models.CheckConstraint(
                condition=Q(state=0, stability__isnull=True) | Q(state__gt=0, stability__isnull=False),
                name="recall_card_new_iff_no_stability",
            ),
            models.CheckConstraint(
                condition=Q(state=0, due_at__isnull=True) | Q(state__gt=0, due_at__isnull=False),
                name="recall_card_new_iff_no_due",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user_id", "due_at"], condition=Q(status="active", state__gt=0), name="recall_card_due_idx"
            ),
            models.Index(
                fields=["user_id", "-importance", "created_at"],
                condition=Q(status="active", state=0),
                name="recall_card_new_idx",
            ),
            models.Index(fields=["user_id", "chapter_id", "status"], name="recall_card_chapter_idx"),
            models.Index(
                fields=["user_id", "-last_lapse_at"],
                condition=Q(lapses__gt=0, status="active"),
                name="recall_card_forgotten_idx",
            ),
            models.Index(
                fields=["user_id", "needs_recheck"], condition=Q(needs_recheck=True), name="recall_card_recheck_idx"
            ),
            models.Index(fields=["item"], name="recall_card_item_idx"),
            models.Index(fields=["subscription"], condition=Q(subscription__isnull=False), name="recall_card_sub_idx"),
        ]


SESSION_SOURCES = ("today", "chapter", "deck", "forgotten", "quick", "catchup", "cram", "review_ahead")
SESSION_STATUSES = ("open", "closed", "auto_closed")


class RecallSession(UUIDModel):
    SOURCES = SESSION_SOURCES
    STATUSES = SESSION_STATUSES

    user_id = models.UUIDField()
    client_id = models.UUIDField()
    source = models.CharField(max_length=14)
    spec = models.JSONField(default=dict, blank=True)  # {"v": 1, "chapter_id": ..., "deck_id": ...}
    status = models.CharField(max_length=12, default="open")
    started_at = models.DateTimeField()
    last_event_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    tz = models.CharField(max_length=64)
    local_date = models.DateField()
    planned_count = models.SmallIntegerField(default=0)
    reviewed = models.IntegerField(default=0)
    new_count = models.IntegerField(default=0)
    again = models.IntegerField(default=0)
    hard = models.IntegerField(default=0)
    good = models.IntegerField(default=0)
    easy = models.IntegerField(default=0)
    active_seconds = models.IntegerField(default=0)

    class Meta:
        db_table = "recall_session"
        constraints = [
            in_("source", SESSION_SOURCES, "recall_session_source_valid"),
            in_("status", SESSION_STATUSES, "recall_session_status_valid"),
            models.UniqueConstraint(fields=["user_id", "client_id"], name="recall_session_client_uniq"),
        ]
        indexes = [
            models.Index(fields=["user_id", "-started_at"], name="recall_session_recent_idx"),
            models.Index(
                fields=["status", "last_event_at"], condition=Q(status="open"), name="recall_session_open_idx"
            ),
        ]


SCHEDULEEVENT_KINDS = (
    "content_reset",
    "forget",
    "postpone",
    "unpostpone",
    "horizon",
    "manual_due",
    "suspend",
    "unsuspend",
)
SCHEDULEEVENT_REASONS = (
    "",
    "typo_free",
    "substantive",
    "amendment",
    "rebalance",
    "vacation",
    "student",
    "exam_horizon",
    "parked",
)


class RecallScheduleEvent(models.Model):
    KINDS = SCHEDULEEVENT_KINDS
    REASONS = SCHEDULEEVENT_REASONS
    """State changes that are not reviews. Replay uses content_reset, forget, postpone and unpostpone."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    card = models.ForeignKey(RecallCard, on_delete=models.CASCADE, related_name="schedule_events")
    kind = models.CharField(max_length=14)
    at = models.DateTimeField()
    from_due = models.DateTimeField(null=True, blank=True)
    to_due = models.DateTimeField(null=True, blank=True)
    stability_before = models.FloatField(null=True, blank=True)
    stability_after = models.FloatField(null=True, blank=True)
    reason_code = models.CharField(max_length=14, blank=True, default="")
    ref = models.CharField(max_length=80, null=True, blank=True)  # noqa: DJ001
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recall_scheduleevent"
        constraints = [
            in_("kind", SCHEDULEEVENT_KINDS, "recall_scheduleevent_kind_valid"),
            in_("reason_code", SCHEDULEEVENT_REASONS, "recall_scheduleevent_reason_valid"),
        ]
        indexes = [models.Index(fields=["user_id", "card", "at"], name="recall_schedev_card_idx")]

    def __str__(self) -> str:
        return f"RecallScheduleEvent {self.pk}"


# ------------------------------------------------------------------------------------- the review log


REVIEWLOG_KINDS = ("review", "undo")
REVIEWLOG_MODES = ("normal", "catchup", "quick_revision", "cram", "review_ahead")
REVIEWLOG_FLAGS = ("offline", "late", "clamped_time", "stale_content", "deleted_card", "duplicate_device")


class RecallReviewLog(models.Model):
    KINDS = REVIEWLOG_KINDS
    MODES = REVIEWLOG_MODES
    FLAGS = REVIEWLOG_FLAGS
    """
    Append-only facts. Hash partitioned by `user_id` on PostgreSQL (16 partitions), a plain table on SQLite; created by raw SQL
    in migration 0003 (hence `managed = False`). Fact columns never change; the derived columns, `counts_for_scheduling` and
    `flags` may be rewritten only by the replay service (`SET LOCAL recall.replaying = 'on'`); account erasure sets
    `recall.erasing` to allow deletes. See ERD 2.8.
    """

    pk = models.CompositePrimaryKey("user_id", "id")
    user_id = models.UUIDField()
    id = models.UUIDField()  # client generated (UUID v7): the idempotency key
    kind = models.CharField(max_length=8, default="review")
    card_id = models.UUIDField()
    item_id = models.UUIDField()
    item_version_id = models.UUIDField()
    session_id = models.UUIDField(null=True, blank=True)
    rating = models.SmallIntegerField(null=True, blank=True)
    reviewed_at = models.DateTimeField()
    received_at = models.DateTimeField()
    duration_ms = models.IntegerField(null=True, blank=True)
    mode = models.CharField(max_length=16, default="normal")
    counts_for_scheduling = models.BooleanField(default=True)
    device_id = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001
    tz_offset_min = models.SmallIntegerField(default=0)
    local_date = models.DateField()
    voids_id = models.UUIDField(null=True, blank=True)
    flags = models.JSONField(default=list, blank=True)
    phase_before = models.SmallIntegerField(null=True, blank=True)
    stability_before = models.FloatField(null=True, blank=True)
    difficulty_before = models.FloatField(null=True, blank=True)
    elapsed_days = models.IntegerField(null=True, blank=True)
    retrievability_before = models.FloatField(null=True, blank=True)
    phase_after = models.SmallIntegerField(null=True, blank=True)
    stability_after = models.FloatField(null=True, blank=True)
    difficulty_after = models.FloatField(null=True, blank=True)
    scheduled_days = models.FloatField(null=True, blank=True)
    due_after = models.DateTimeField(null=True, blank=True)
    params_id = models.UUIDField(null=True, blank=True)
    scheduler_version = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001

    class Meta:
        db_table = "recall_reviewlog"
        managed = False

    def __str__(self) -> str:
        return f"RecallReviewLog {self.pk}"


# ------------------------------------------------------------------------- rollups, report, audit


class RecallDailyRollup(models.Model):
    """Derived and rebuildable. Incremented only when a log row was newly inserted; an undo applies negative deltas."""

    pk = models.CompositePrimaryKey("user_id", "local_date")
    user_id = models.UUIDField()
    local_date = models.DateField()
    new_cards = models.IntegerField(default=0)
    learn_reviews = models.IntegerField(default=0)
    review_reviews = models.IntegerField(default=0)
    relearn_reviews = models.IntegerField(default=0)
    again = models.IntegerField(default=0)
    hard = models.IntegerField(default=0)
    good = models.IntegerField(default=0)
    easy = models.IntegerField(default=0)
    mandatory_reviews = models.IntegerField(default=0)
    seconds = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recall_dailyrollup"

    def __str__(self) -> str:
        return f"RecallDailyRollup {self.pk}"


class RecallChapterRollup(UUIDModel):
    user_id = models.UUIDField()
    local_date = models.DateField()
    chapter_id = models.UUIDField(null=True, blank=True)  # null is Unsorted
    reviews = models.IntegerField(default=0)
    again = models.IntegerField(default=0)
    mandatory_reviews = models.IntegerField(default=0)

    class Meta:
        db_table = "recall_chapterrollup"
        constraints = [
            # Two partial uniques instead of `coalesce(chapter_id, zero uuid)`, so SQLite and PostgreSQL behave the same
            models.UniqueConstraint(
                fields=["user_id", "local_date", "chapter_id"],
                condition=Q(chapter_id__isnull=False),
                name="recall_chapterrollup_chapter_uniq",
            ),
            models.UniqueConstraint(
                fields=["user_id", "local_date"],
                condition=Q(chapter_id__isnull=True),
                name="recall_chapterrollup_unsorted_uniq",
            ),
        ]


REPORT_TARGETS = ("item", "share", "deck")
REPORT_REASONS = ("wrong", "outdated", "copyright", "abusive", "spam", "other")
REPORT_STATUSES = ("open", "actioned", "dismissed")


class RecallReport(UUIDModel):
    TARGETS = REPORT_TARGETS
    REASONS = REPORT_REASONS
    STATUSES = REPORT_STATUSES
    """A student's report of a card (FR-F15-52). The note is never logged."""

    target_kind = models.CharField(max_length=8)
    target_id = models.UUIDField()
    item_version_id = models.UUIDField(null=True, blank=True)
    reporter_user_id = models.UUIDField()
    reason = models.CharField(max_length=12)
    note = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(max_length=10, default="open")
    handled_by = models.UUIDField(null=True, blank=True)
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recall_report"
        constraints = [
            in_("target_kind", REPORT_TARGETS, "recall_report_target_valid"),
            in_("reason", REPORT_REASONS, "recall_report_reason_valid"),
            in_("status", REPORT_STATUSES, "recall_report_status_valid"),
            models.UniqueConstraint(
                fields=["reporter_user_id", "target_kind", "target_id"],
                condition=Q(status="open"),
                name="recall_report_one_open_per_reporter",
            ),
        ]
        indexes = [models.Index(fields=["status", "target_kind", "created_at"], name="recall_report_queue_idx")]


AUDITLOG_ACTIONS = (
    "deck_publish", "item_withdraw", "share_takedown", "attest_own_words", "params_activate", "force_replay",
    "quota_change",
)  # fmt: skip


class RecallAuditLog(UUIDModel):
    ACTIONS = AUDITLOG_ACTIONS
    """Who did what to which object. Ids and counts only, never text."""

    actor_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=20)
    target_kind = models.CharField(max_length=16)
    target_id = models.CharField(max_length=80)
    detail = models.JSONField(default=dict, blank=True)  # {"v": 1, ...}

    class Meta:
        db_table = "recall_auditlog"
        constraints = [in_("action", AUDITLOG_ACTIONS, "recall_auditlog_action_valid")]
        indexes = [models.Index(fields=["target_kind", "target_id", "created_at"], name="recall_audit_target_idx")]


# ------------------------------------------------------------------------------------------- quota


class RecallQuotaPlan(TimeStampedModel):
    """Limits per plan (PRD 8.3). `free` and `pro` are seeded; reviewing is never limited."""

    plan_code = models.CharField(max_length=32, primary_key=True)
    max_cards = models.IntegerField()
    max_cards_per_deck = models.IntegerField()
    max_decks = models.IntegerField()
    max_active_shares = models.IntegerField()
    ai_suggestions_per_day = models.IntegerField()
    ai_batches_per_day = models.IntegerField()
    share_imports_per_day = models.IntegerField()
    pack_size = models.IntegerField()

    class Meta:
        db_table = "recall_quotaplan"

    def __str__(self) -> str:
        return self.plan_code


class RecallQuotaUsage(TimeStampedModel):
    """What a student holds now. Changed only by conditional UPDATEs (`services.quota`), never read-then-write."""

    user_id = models.UUIDField(primary_key=True)
    cards_active = models.IntegerField(default=0)  # own cards, not counting platform subscriptions
    decks_active = models.IntegerField(default=0)
    shares_active = models.IntegerField(default=0)
    reconciled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recall_quotausage"
        constraints = [
            models.CheckConstraint(
                condition=Q(cards_active__gte=0, decks_active__gte=0, shares_active__gte=0),
                name="recall_quotausage_nonnegative",
            )
        ]
