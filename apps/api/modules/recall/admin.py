"""
Django admin of the recall system (F-15 W11): the editors' tool for platform decks (FR-F15-44 to 53, PRD 9.4 "staff").

Who may do what (D44): a staff login (`is_staff`) is matched by e-mail to a `profiles` row; that row's role gives the scopes
(`domain/staff.py`): `editor` = `recall.deck.author` (items, versions, draft deck versions, reports), `admin` = author plus
`recall.deck.publish` (publish, quota plans, read-only student state). Superusers have both. Everyone else sees nothing.

Rules enforced here, all through `services/decks.py` so the API and the seed loader behave the same:
- Only PLATFORM items and decks are listed or opened. A student's own cards and decks (their text) are not reachable.
- A live item version or a published deck version is never edited: an edit is a new draft version.
- Publishing is atomic and refuses a deck holding an item whose rights status is `unknown`.
- Student state is read only and shows no card text; the review log view lists facts.
"""

from __future__ import annotations

import json
import uuid

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from core.admin_base import ReadOnlyAdmin
from core.errors import CodedError

from .adapters import profiles as profiles_adapter
from .adapters import syllabus as syllabus_adapter
from .domain import staff
from .errors import InvalidFields
from .models import (
    RecallAuditLog,
    RecallCard,
    RecallDeck,
    RecallDeckVersion,
    RecallDeckVersionItem,
    RecallItem,
    RecallItemVersion,
    RecallQuotaPlan,
    RecallReport,
    RecallReviewLog,
)
from .services import decks as deck_service

# --- permissions (D44) --------------------------------------------------------------------------------------------


def scopes_of(request) -> frozenset[str]:
    """The recall scopes of the logged-in staff user, worked out once per request."""
    cached = getattr(request, "_recall_scopes", None)
    if cached is not None:
        return cached
    user = request.user
    if not (user.is_active and user.is_staff):
        scopes: frozenset[str] = frozenset()
    elif user.is_superuser:
        scopes = staff.scopes_for(None, is_superuser=True)
    else:
        scopes = staff.scopes_for(profiles_adapter.role_of_email(user.email))
    request._recall_scopes = scopes
    return scopes


class ScopedAdmin(admin.ModelAdmin):
    """Every permission is a scope check. `view_scope` reads, `change_scope` adds, changes and deletes."""

    view_scope = staff.AUTHOR
    change_scope = staff.AUTHOR
    allow_delete = False

    def has_module_permission(self, request):
        return self.view_scope in scopes_of(request)

    def has_view_permission(self, request, obj=None):
        return self.view_scope in scopes_of(request)

    def has_add_permission(self, request):
        return self.change_scope in scopes_of(request)

    def has_change_permission(self, request, obj=None):
        return self.change_scope in scopes_of(request)

    def has_delete_permission(self, request, obj=None):
        return self.allow_delete and self.change_scope in scopes_of(request)


def _actor(request):
    """The id recorded as the editor: the matched profile is unknown here, so staff actions carry no student id."""
    return None


def _refs(ids) -> list[str]:
    out = []
    for item in RecallItem.objects.filter(pk__in=ids):
        out.append(item.external_ref or str(item.pk))
    return sorted(out)


def _fields_errors(exc: CodedError) -> list[str]:
    errors = (exc.extra or {}).get("errors") or []
    return [f"{e.get('field', 'fields')}: {e.get('message', e.get('code', ''))}" for e in errors] or [str(exc.detail)]


# --- items ----------------------------------------------------------------------------------------------------


class JsonFieldsMixin(forms.ModelForm):
    """`fields_json` (the kind's fields as JSON) and `change_note`, checked against the kind's rules before saving."""

    fields_json = forms.CharField(
        label="Fields (JSON)",
        widget=forms.Textarea(attrs={"rows": 10, "cols": 90, "spellcheck": "false"}),
        help_text='For a pointer: {"prompt_md": "…", "answer_md": "…"}. The kinds and their fields are in docs/F-15-ROLLOUT.md.',
    )

    def clean_fields_json(self):
        raw = self.cleaned_data["fields_json"]
        try:
            value = json.loads(raw)
        except ValueError as exc:
            raise ValidationError(f"Not valid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValidationError("Fields must be a JSON object.")
        return value

    def _check_kind(self, kind: str, fields: dict) -> dict:
        try:
            return deck_service.validate_fields(kind, fields)
        except InvalidFields as exc:
            raise ValidationError(_fields_errors(exc)) from exc
        except CodedError as exc:
            raise ValidationError(str(exc.detail)) from exc


class PlatformItemAddForm(JsonFieldsMixin):
    change_note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    class Meta:
        model = RecallItem
        fields = (
            "kind", "importance", "chapter", "topic", "tags", "reference_keys", "rights_status", "source_label",
            "source_url", "external_ref",
        )  # fmt: skip

    def clean(self):
        data = super().clean()
        if data.get("kind") and data.get("fields_json") is not None:
            data["fields_json"] = self._check_kind(data["kind"], data["fields_json"])
        return data


class PlatformItemChangeForm(forms.ModelForm):
    class Meta:
        model = RecallItem
        fields = (
            "importance", "chapter", "topic", "tags", "reference_keys", "rights_status", "source_label", "source_url",
            "status", "needs_editor_check", "external_ref",
        )  # fmt: skip


@admin.register(RecallItem)
class PlatformItemAdmin(ScopedAdmin):
    """Platform items only. Text lives in versions (see "Item versions"); this page holds what does not change per edit."""

    list_display = (
        "ref",
        "kind",
        "importance",
        "chapter_key",
        "rights_status",
        "status",
        "live_no",
        "draft_no",
        "needs_check",
    )
    list_filter = ("kind", "importance", "rights_status", "status", "needs_editor_check")
    search_fields = ("external_ref", "search_text", "chapter_key")
    ordering = ("-updated_at",)
    raw_id_fields = ("chapter", "topic")
    list_per_page = 50

    def get_readonly_fields(self, request, obj=None):
        return ("kind", "versions_summary") if obj else ()

    def get_queryset(self, request):
        return (
            super().get_queryset(request).filter(ownership="platform").select_related("live_version", "current_version")
        )

    def get_form(self, request, obj=None, **kwargs):
        kwargs["form"] = PlatformItemChangeForm if obj else PlatformItemAddForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return [
                (None, {"fields": ("kind", "importance", "chapter", "topic", "fields_json", "change_note")}),
                ("Rights and source", {"fields": ("rights_status", "source_label", "source_url")}),
                ("Other", {"fields": ("tags", "reference_keys", "external_ref")}),
            ]
        return [
            (None, {"fields": ("kind", "importance", "chapter", "topic", "status", "versions_summary")}),
            ("Rights and source", {"fields": ("rights_status", "source_label", "source_url")}),
            ("Other", {"fields": ("tags", "reference_keys", "external_ref", "needs_editor_check")}),
        ]

    @admin.display(description="Reference", ordering="external_ref")
    def ref(self, obj):
        return obj.external_ref or str(obj.pk)[:8]

    @admin.display(description="Live")
    def live_no(self, obj):
        return obj.live_version.version_no if obj.live_version_id else "-"

    @admin.display(description="Draft")
    def draft_no(self, obj):
        cur = obj.current_version
        return cur.version_no if cur and cur.state == "draft" else "-"

    @admin.display(description="Check", boolean=True)
    def needs_check(self, obj):
        return obj.needs_editor_check

    @admin.display(description="Versions")
    def versions_summary(self, obj):
        rows = [
            format_html("v{} {} ({}) {}", v.version_no, v.state, v.change_kind, (v.plain_text or "")[:80])
            for v in obj.versions.order_by("-version_no")[:10]
        ]
        return format_html("<br>".join(["{}"] * len(rows)), *rows) if rows else "-"

    def save_model(self, request, obj, form, change):
        if not change:
            data = form.cleaned_data
            external_ref = data.get("external_ref") or f"ed-{uuid.uuid4().hex[:8]}"
            item = deck_service.create_platform_item(
                _actor(request),
                kind=data["kind"],
                fields=data["fields_json"],
                importance=data["importance"],
                chapter_id=data["chapter"].pk if data.get("chapter") else None,
                topic_id=data["topic"].pk if data.get("topic") else None,
                tags=data.get("tags") or [],
                reference_keys=data.get("reference_keys") or [],
                rights_status=data["rights_status"],
                source_label=data.get("source_label", ""),
                source_url=data.get("source_url"),
                external_ref=external_ref,
            )
            obj.pk, obj._state.adding = item.pk, False
            obj.refresh_from_db()
            return
        if "chapter" in form.changed_data or "topic" in form.changed_data:
            link = syllabus_adapter.link_columns(
                obj.chapter_id, obj.topic_id if obj.topic_id and obj.chapter_id else None
            )
            for key, value in link.items():
                setattr(obj, key if key.endswith("_key") else key, value)
        super().save_model(request, obj, form, change)


# --- item versions --------------------------------------------------------------------------------------------


class VersionAddForm(JsonFieldsMixin):
    class Meta:
        model = RecallItemVersion
        fields = ("item", "change_kind", "change_note")

    def clean(self):
        data = super().clean()
        item = data.get("item")
        if item is not None and item.ownership != "platform":
            raise ValidationError("Only platform items have editor versions.")
        if item is not None and data.get("fields_json") is not None:
            data["fields_json"] = self._check_kind(item.kind, data["fields_json"])
        return data


class VersionChangeForm(JsonFieldsMixin):
    class Meta:
        model = RecallItemVersion
        fields = ("change_kind", "change_note")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance
        if instance.pk:
            self.fields["fields_json"].initial = json.dumps(
                {k: v for k, v in instance.fields.items() if k != "v"}, indent=2, ensure_ascii=False
            )

    def clean(self):
        data = super().clean()
        if data.get("fields_json") is not None:
            data["fields_json"] = self._check_kind(self.instance.item.kind, data["fields_json"])
        return data


@admin.register(RecallItemVersion)
class PlatformItemVersionAdmin(ScopedAdmin):
    """A new version is always a draft. Only a draft can be edited; a live or superseded version is a record."""

    list_display = ("item_ref", "version_no", "state", "change_kind", "excerpt", "created_at")
    list_filter = ("state", "change_kind")
    search_fields = ("item__external_ref", "plain_text")
    ordering = ("-created_at",)
    raw_id_fields = ("item",)
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).filter(item__ownership="platform").select_related("item")

    def get_form(self, request, obj=None, **kwargs):
        kwargs["form"] = VersionChangeForm if obj else VersionAddForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return [(None, {"fields": ("item", "change_kind", "fields_json", "change_note")})]
        base = ["item_info", "state", "version_no", "content_hash", "live_at", "superseded_at"]
        if obj.state == "draft":
            return [(None, {"fields": (*base, "change_kind", "fields_json", "change_note")})]
        return [(None, {"fields": (*base, "change_kind", "change_note", "fields_view")})]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        always = ("item_info", "state", "version_no", "content_hash", "live_at", "superseded_at", "fields_view")
        return always if obj.state == "draft" else (*always, "change_kind", "change_note")

    @admin.display(description="Item")
    def item_ref(self, obj):
        return obj.item.external_ref or str(obj.item_id)[:8]

    item_info = item_ref

    @admin.display(description="Excerpt")
    def excerpt(self, obj):
        return (obj.plain_text or "")[:80]

    @admin.display(description="Fields")
    def fields_view(self, obj):
        return format_html(
            "<pre>{}</pre>", json.dumps({k: v for k, v in obj.fields.items() if k != "v"}, indent=2, ensure_ascii=False)
        )

    def save_model(self, request, obj, form, change):
        data = form.cleaned_data
        item = obj.item if change else data["item"]
        version = deck_service.new_item_version(
            _actor(request),
            item,
            data["fields_json"],
            change_kind=data["change_kind"],
            note=data.get("change_note", ""),
        )
        obj.pk, obj._state.adding = version.pk, False
        obj.refresh_from_db()
        if not change and version.state != "draft":
            messages.info(request, "That text is the same as the newest version, so no new version was made.")


# --- decks and deck versions -----------------------------------------------------------------------------------


class DeckForm(forms.ModelForm):
    class Meta:
        model = RecallDeck
        fields = ("title", "slug", "description", "status", "course", "level", "subject", "chapter")


@admin.register(RecallDeck)
class PlatformDeckAdmin(ScopedAdmin):
    list_display = ("title", "slug", "status", "live_no", "draft_no", "chapter_key")
    list_filter = ("status",)
    search_fields = ("title", "slug")
    raw_id_fields = ("course", "level", "subject", "chapter")
    readonly_fields = ("live_version", "draft_version")
    form = DeckForm
    actions = ["start_draft"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(kind="platform")
            .select_related("live_version", "draft_version", "chapter")
        )

    def get_fields(self, request, obj=None):
        fields = [*DeckForm.Meta.fields]
        return [*fields, "live_version", "draft_version"] if obj else fields

    @admin.display(description="Live")
    def live_no(self, obj):
        return obj.live_version.version_no if obj.live_version_id else "-"

    @admin.display(description="Draft")
    def draft_no(self, obj):
        return obj.draft_version.version_no if obj.draft_version_id else "-"

    @admin.display(description="Chapter")
    def chapter_key(self, obj):
        return obj.chapter.key if obj.chapter_id else "-"

    def save_model(self, request, obj, form, change):
        obj.kind, obj.owner_user_id = "platform", None
        if obj.chapter_id:
            link = syllabus_adapter.link_columns(obj.chapter_id)
            obj.course_id, obj.level_id, obj.subject_id = link["course_id"], link["level_id"], link["subject_id"]
        super().save_model(request, obj, form, change)

    @admin.action(description="Start a draft version (a copy of the live one)")
    def start_draft(self, request, queryset):
        for deck in queryset:
            version = deck_service.start_draft_version(_actor(request), deck)
            messages.success(request, f"{deck.title}: draft version {version.version_no} is ready to edit.")


class DeckVersionForm(forms.ModelForm):
    item_refs = forms.CharField(
        required=False,
        label="Items (one reference per line, in order)",
        widget=forms.Textarea(attrs={"rows": 14, "cols": 60, "spellcheck": "false"}),
        help_text="Item references (the Reference column of Items) or ids. Write `ref@3` to pin version 3 of that item. "
        "Leave the box untouched to keep the current rows.",
    )

    class Meta:
        model = RecallDeckVersion
        fields = ("deck", "changelog_md")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and "item_refs" in self.fields:
            rows = RecallDeckVersionItem.objects.filter(deck_version=self.instance).select_related(
                "item", "item_version"
            )
            self.fields["item_refs"].initial = "\n".join(
                f"{r.item.external_ref or r.item_id}@{r.item_version.version_no}"
                for r in rows.order_by("position", "item_id")
            )

    def clean(self):
        data = super().clean()
        raw = data.get("item_refs", "")
        entries, problems = [], []
        for line in raw.splitlines():
            ref, _, pin = line.strip().partition("@")
            if not ref:
                continue
            found, missing = deck_service.resolve_item_refs([ref])
            if missing:
                problems.append(f"No platform item {ref!r}.")
                continue
            item, chosen = found[0], None
            if pin:
                chosen = item.versions.filter(version_no=int(pin)).first() if pin.isdigit() else None
                if chosen is None:
                    problems.append(f"{ref} has no version {pin!r}.")
                    continue
            entries.append((item, chosen))
        if problems:
            raise ValidationError(problems)
        data["entries"] = entries
        return data


@admin.register(RecallDeckVersion)
class PlatformDeckVersionAdmin(ScopedAdmin):
    """A draft is edited here and published with the button (needs `recall.deck.publish`); other states are read only."""

    list_display = ("deck", "version_no", "state", "item_count", "published_at")
    list_filter = ("state",)
    search_fields = ("deck__title",)
    raw_id_fields = ("deck",)
    ordering = ("-created_at",)
    form = DeckVersionForm
    change_form_template = "admin/recall/recalldeckversion/change_form.html"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deck__kind="platform").select_related("deck")

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return [(None, {"fields": ("deck",)})]
        editable = obj.state in ("draft", "in_review")
        main = ["deck", "version_no", "state", "changelog_md"] + (["item_refs"] if editable else ["rows_view"])
        return [
            (None, {"fields": main}),
            ("Result", {"fields": ("item_count", "tier_counts", "diff_summary", "published_at")}),
        ]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        always = (
            "deck",
            "version_no",
            "state",
            "item_count",
            "tier_counts",
            "diff_summary",
            "published_at",
            "rows_view",
        )
        return always if obj.state in ("draft", "in_review") else (*always, "changelog_md")

    def has_delete_permission(self, request, obj=None):
        return (
            obj is not None
            and obj.state == "draft"
            and super().has_view_permission(request)
            and staff.AUTHOR in scopes_of(request)
        )

    @admin.display(description="Items")
    def rows_view(self, obj):
        rows = (
            RecallDeckVersionItem.objects.filter(deck_version=obj)
            .select_related("item", "item_version")
            .order_by("position", "item_id")
        )
        lines = [
            format_html(
                "{}. {} v{} ({}, {})",
                r.position + 1,
                r.item.external_ref or str(r.item_id)[:8],
                r.item_version.version_no,
                r.item.importance,
                r.change_vs_prev,
            )
            for r in rows
        ]
        return format_html("<br>".join(["{}"] * len(lines)), *lines) if lines else "-"

    def render_change_form(self, request, context, *args, **kwargs):
        context["can_publish"] = staff.PUBLISH in scopes_of(request)
        return super().render_change_form(request, context, *args, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            draft = deck_service.start_draft_version(_actor(request), obj.deck)
            obj.pk, obj._state.adding = draft.pk, False
            obj.refresh_from_db()
            return
        if obj.state not in ("draft", "in_review"):
            raise Http404
        super().save_model(request, obj, form, change)
        if form.cleaned_data.get("item_refs", "").strip():
            deck_service.set_draft_rows(obj, form.cleaned_data["entries"])

    def response_change(self, request, obj):
        if "_publish" in request.POST:
            if staff.PUBLISH not in scopes_of(request):
                messages.error(request, "Publishing needs the recall.deck.publish scope.")
            else:
                try:
                    version = deck_service.publish_deck_version(
                        _actor(request), obj.deck_id, obj.pk, changelog_md=obj.changelog_md
                    )
                    messages.success(
                        request, f"Published {obj.deck.title} version {version.version_no}: {version.diff_summary}"
                    )
                except CodedError as exc:
                    ids = (exc.extra or {}).get("item_ids")
                    detail = f" Items: {', '.join(_refs(ids))}." if ids else ""
                    messages.error(request, f"Not published: {exc.detail}{detail} Nothing changed.")
        return super().response_change(request, obj)

    actions = ["publish_selected"]

    @admin.action(description="Publish selected draft versions (students see them at once)")
    def publish_selected(self, request, queryset):
        if staff.PUBLISH not in scopes_of(request):
            messages.error(request, "Publishing needs the recall.deck.publish scope.")
            return
        for version in queryset.select_related("deck"):
            try:
                deck_service.publish_deck_version(_actor(request), version.deck_id, version.pk)
                messages.success(request, f"Published {version.deck.title} version {version.version_no}.")
            except CodedError as exc:
                ids = (exc.extra or {}).get("item_ids")
                detail = f" Items: {', '.join(_refs(ids))}." if ids else ""
                messages.error(
                    request, f"{version.deck.title} v{version.version_no} not published: {exc.detail}{detail}"
                )


# --- reports ---------------------------------------------------------------------------------------------------


@admin.register(RecallReport)
class ReportAdmin(ScopedAdmin):
    """The reports queue (FR-F15-52): what was reported, the version she saw and how many students reported it."""

    list_display = (
        "created_at",
        "target_kind",
        "item_ref",
        "version_no",
        "reason",
        "reporters",
        "status",
        "handled_at",
    )
    list_filter = ("status", "reason", "target_kind")
    ordering = ("status", "-created_at")
    actions = ["mark_actioned", "mark_dismissed", "flag_items"]
    readonly_fields = (
        "target_kind", "target_id", "item_version_id", "reason", "note", "created_at", "handled_at", "item_ref", "version_no",
        "reporters",
    )  # fmt: skip
    fields = (
        "target_kind",
        "item_ref",
        "version_no",
        "reporters",
        "reason",
        "note",
        "status",
        "handled_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return staff.AUTHOR in scopes_of(request)

    @admin.display(description="Item")
    def item_ref(self, obj):
        item = RecallItem.objects.filter(pk=obj.target_id).first() if obj.target_kind == "item" else None
        return (item.external_ref or str(item.pk)[:8]) if item else "-"

    @admin.display(description="Version seen")
    def version_no(self, obj):
        v = RecallItemVersion.objects.filter(pk=obj.item_version_id).first() if obj.item_version_id else None
        return v.version_no if v else "-"

    @admin.display(description="Reporters")
    def reporters(self, obj):
        return RecallReport.objects.filter(target_kind=obj.target_kind, target_id=obj.target_id, status="open").count()

    def _close(self, request, queryset, status):
        n = queryset.filter(status="open").update(status=status, handled_at=timezone.now())
        messages.success(request, f"{n} report(s) marked {status}.")

    @admin.action(description="Mark actioned (the item was fixed)")
    def mark_actioned(self, request, queryset):
        self._close(request, queryset, "actioned")

    @admin.action(description="Dismiss (no change needed)")
    def mark_dismissed(self, request, queryset):
        self._close(request, queryset, "dismissed")

    @admin.action(description="Flag the items for an editor check")
    def flag_items(self, request, queryset):
        ids = list(queryset.filter(target_kind="item").values_list("target_id", flat=True))
        n = RecallItem.objects.filter(pk__in=ids, ownership="platform").update(
            needs_editor_check=True, check_reason="report", updated_at=timezone.now()
        )
        messages.success(request, f"{n} item(s) flagged.")


# --- plans, and read-only student state ------------------------------------------------------------------------


@admin.register(RecallQuotaPlan)
class QuotaPlanAdmin(ScopedAdmin):
    """Limits per plan. Needs the publish scope, and every change is written to the audit log (numbers only)."""

    view_scope = staff.PUBLISH
    change_scope = staff.PUBLISH
    list_display = ("plan_code", "max_cards", "max_cards_per_deck", "max_decks", "pack_size")
    readonly_fields = ("plan_code",)

    def has_add_permission(self, request):
        return False  # `free` and `pro` are seeded; billing decides plans later

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        RecallAuditLog.objects.create(
            actor_id=_actor(request),
            action="quota_change",
            target_kind="quotaplan",
            target_id=obj.plan_code,
            detail={"v": 1, "changed": {name: form.cleaned_data[name] for name in form.changed_data}},
        )


@admin.register(RecallCard)
class CardAdmin(ReadOnlyAdmin):
    """Read only, ids and numbers only: a student's card text is never shown here."""

    list_display = ("id", "user_id", "item_id", "ordinal", "state", "status", "due_at", "reps", "lapses", "leech")
    list_filter = ("state", "status", "leech")
    search_fields = ("id", "user_id", "item_id")
    ordering = ("-updated_at",)
    list_per_page = 50
    exclude = ("item", "item_version", "subscription", "params")

    change_list_template = "admin/recall/recallcard/change_list.html"
    REVIEW_PAGE = 100

    def has_module_permission(self, request):
        return staff.PUBLISH in scopes_of(request)

    def has_view_permission(self, request, obj=None):
        return staff.PUBLISH in scopes_of(request)

    def get_urls(self):
        extra = [path("review-log/", self.admin_site.admin_view(self.review_log), name="recall_recallcard_reviewlog")]
        return extra + super().get_urls()

    def review_log(self, request):
        """
        The review log, read only (D45). Its primary key is composite, which Django's admin cannot list, so it is one
        paginated page of facts (no card text) under the cards, with an optional `?user=` filter.
        """
        if not self.has_view_permission(request):
            raise Http404
        qs = RecallReviewLog.objects.all().order_by("-reviewed_at", "-id")
        user_filter = request.GET.get("user", "").strip()
        if user_filter:
            try:
                qs = qs.filter(user_id=uuid.UUID(user_filter))
            except ValueError:
                messages.error(request, "That is not a student id.")
                user_filter = ""
        page = Paginator(qs, self.REVIEW_PAGE).get_page(request.GET.get("page"))
        context = {
            **self.admin_site.each_context(request),
            "title": "Review log",
            "page": page,
            "user_filter": user_filter,
        }
        return TemplateResponse(request, "admin/recall/recallcard/review_log.html", context)


@admin.register(RecallAuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "action", "target_kind", "target_id", "detail")
    list_filter = ("action",)
    ordering = ("-created_at",)

    def has_module_permission(self, request):
        return staff.PUBLISH in scopes_of(request)

    def has_view_permission(self, request, obj=None):
        return staff.PUBLISH in scopes_of(request)
