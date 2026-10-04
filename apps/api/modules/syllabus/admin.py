"""
Content admin for the syllabus taxonomy (X-05). Editors maintain schemes, papers, chapters and topics here, without code.

Rules enforced in this file:
- Students never see a scheme until it is published, and only people with the publish permission can do that.
- Nodes of a published or retired scheme cannot be deleted (students' progress points at them). Switch them off with
  "active" instead; progress is kept.
- Editing a published scheme is allowed (typo fixes) but warns that the change is live at once.
- Bulk work: paste chapters and topics as lists, import or export a whole scheme as JSON.
"""

from __future__ import annotations

import json

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from modules.profiles.models import Profile

from . import services
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

# --- shared helpers --------------------------------------------------------------------------


def scheme_of(obj) -> Scheme | None:
    """The scheme a taxonomy node belongs to."""
    if isinstance(obj, Scheme):
        return obj
    if isinstance(obj, (SyllabusGroup, Subject)):
        return obj.scheme
    if isinstance(obj, Chapter):
        return obj.subject.scheme
    if isinstance(obj, Topic):
        return obj.chapter.subject.scheme
    return None


class DraftOnlyDeleteMixin:
    """Deleting is only possible while the scheme is a draft. Afterwards use the 'active' switch."""

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        if not allowed or obj is None:
            return allowed
        scheme = scheme_of(obj)
        return scheme is None or scheme.status == Scheme.Status.DRAFT


class LiveEditWarningMixin:
    """After saving a node of a published scheme, remind the editor that students see the change immediately."""

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        scheme = scheme_of(form.instance)
        if scheme and scheme.status == Scheme.Status.PUBLISHED:
            messages.warning(request, f"Scheme {scheme.code} is published: this change is live for students now.")


class ActivateActionsMixin:
    @admin.action(description="Switch on (show to students)")
    def make_active(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_active=True)} switched on.")

    @admin.action(description="Switch off (hide, keep student progress)")
    def make_inactive(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_active=False)} switched off.")


# --- reference data --------------------------------------------------------------------------


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "institute_name", "is_active")
    search_fields = ("code", "name")


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ("name", "course", "code", "sort_order", "is_active")
    list_filter = ("course", "is_active")
    list_editable = ("sort_order",)
    search_fields = ("name", "code")


@admin.register(ExamTerm)
class ExamTermAdmin(admin.ModelAdmin):
    list_display = ("name", "course", "code", "exam_start", "exam_end", "is_open")
    list_filter = ("course", "is_open")
    list_editable = ("is_open",)
    search_fields = ("name", "code")


# --- scheme ----------------------------------------------------------------------------------


class GroupInline(DraftOnlyDeleteMixin, admin.TabularInline):
    model = SyllabusGroup
    extra = 0
    fields = ("key", "name", "sort_order")


class SubjectInline(DraftOnlyDeleteMixin, admin.TabularInline):
    model = Subject
    extra = 0
    fields = ("key", "name", "paper_number", "group", "total_marks", "kind", "is_optional", "sort_order", "is_active")
    show_change_link = True  # open the paper to edit its chapters

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "group":
            scheme_id = request.resolver_match.kwargs.get("object_id")
            kwargs["queryset"] = (
                SyllabusGroup.objects.filter(scheme_id=scheme_id) if scheme_id else SyllabusGroup.objects.none()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SchemeImportForm(forms.Form):
    file = forms.FileField(required=False, label="JSON file")
    text = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 12, "cols": 90}), label="Or paste JSON")

    def clean(self):
        cleaned = super().clean()
        raw = ""
        if cleaned.get("file"):
            raw = cleaned["file"].read().decode("utf-8-sig", errors="replace")
        elif cleaned.get("text"):
            raw = cleaned["text"]
        if not raw.strip():
            raise ValidationError("Upload a file or paste JSON.")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"That is not valid JSON: {exc}") from exc
        if not isinstance(data, dict) or not {"course", "level", "scheme"} <= set(data):
            raise ValidationError('The file needs "course", "level" and "scheme" at the top level.')
        cleaned["data"] = data
        return cleaned


@admin.register(Scheme)
class SchemeAdmin(DraftOnlyDeleteMixin, admin.ModelAdmin):
    change_list_template = "admin/syllabus/scheme/change_list.html"
    list_display = ("name", "level", "code", "status_badge", "subject_total", "from_term", "to_term", "published_at")
    list_filter = ("level__course", "level", "status")
    search_fields = ("code", "name", "level__code")
    readonly_fields = ("status", "published_at")
    autocomplete_fields = ("from_term", "to_term")
    inlines = [GroupInline, SubjectInline]
    actions = ["publish_selected", "retire_selected", "build_chapter_map", "export_json"]
    list_select_related = ("level", "level__course", "from_term", "to_term")

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colour = {"draft": "#8a6d00", "published": "#146c2e", "retired": "#666"}[obj.status]
        return format_html('<strong style="color:{}">{}</strong>', colour, obj.get_status_display())

    @admin.display(description="Papers")
    def subject_total(self, obj):
        return obj.subjects.filter(is_active=True).count()

    def has_publish_permission(self, request):
        return request.user.has_perm("syllabus.publish_scheme")

    @admin.action(description="Publish (students can see it)", permissions=["publish"])
    def publish_selected(self, request, queryset):
        for scheme in queryset:
            try:
                services.publish_scheme(scheme)
                self.message_user(request, f"Published {scheme}.", messages.SUCCESS)
            except ValidationError as exc:
                self.message_user(request, f"{scheme}: {'; '.join(exc.messages)}", messages.ERROR)

    @admin.action(description="Retire (hide from new students, keep data)", permissions=["publish"])
    def retire_selected(self, request, queryset):
        for scheme in queryset:
            try:
                services.retire_scheme(scheme)
                self.message_user(request, f"Retired {scheme}.", messages.SUCCESS)
            except ValidationError as exc:
                self.message_user(request, f"{scheme}: {'; '.join(exc.messages)}", messages.ERROR)

    @admin.action(description="Create chapter map from the previous scheme (carry-over for students)")
    def build_chapter_map(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one (the new) scheme.", messages.ERROR)
            return
        new = queryset.get()
        old = new.level.schemes.exclude(pk=new.pk).order_by("-published_at", "-code").first()
        if old is None:
            self.message_user(request, "This level has no other scheme to map from.", messages.ERROR)
            return
        created = services.build_default_chapter_map(old, new)
        self.message_user(
            request,
            f"Mapped {created} new chapters from {old.code} to {new.code}. Review splits and merges under Chapter maps.",
            messages.SUCCESS,
        )

    @admin.action(description="Download as JSON (same format as the seed files)")
    def export_json(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one scheme to download.", messages.ERROR)
            return None
        scheme = queryset.get()
        body = json.dumps(services.scheme_to_dict(scheme), indent=2, ensure_ascii=False)
        response = HttpResponse(body, content_type="application/json")
        response["Content-Disposition"] = (
            f'attachment; filename="{scheme.level.course.code}-{scheme.level.code}-{scheme.code}.json"'
        )
        return response

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if form.instance.status == Scheme.Status.PUBLISHED:
            messages.warning(request, "This scheme is published: changes are live for students now.")

    def get_urls(self):
        custom = [path("import/", self.admin_site.admin_view(self.import_view), name="syllabus_scheme_import")]
        return custom + super().get_urls()

    def import_view(self, request):
        if not self.has_add_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        form = SchemeImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            data = form.cleaned_data["data"]
            existing = Scheme.objects.filter(
                level__course__code=data["course"], level__code=data["level"], code=data["scheme"].get("code")
            ).first()
            if existing and existing.status != Scheme.Status.DRAFT:
                form.add_error(
                    None, f"Scheme {existing.code} is {existing.status}. Only draft schemes can be imported into."
                )
            else:
                try:
                    scheme = services.load_scheme_from_dict(data)
                except (ObjectDoesNotExist, KeyError, TypeError, ValueError, IntegrityError, ValidationError) as exc:
                    form.add_error(None, f"Could not import: {type(exc).__name__}: {exc}")
                else:
                    self.message_user(
                        request, f"Imported {scheme} as a draft. Review it, then publish.", messages.SUCCESS
                    )
                    return redirect(reverse("admin:syllabus_scheme_change", args=[scheme.pk]))
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Import scheme from JSON",
            "opts": self.model._meta,
        }
        return render(request, "admin/syllabus/scheme/import.html", context)


# --- groups, papers, chapters, topics --------------------------------------------------------


class ChapterInline(DraftOnlyDeleteMixin, admin.TabularInline):
    model = Chapter
    extra = 0
    fields = ("key", "name", "marks_min", "marks_max", "weight_source", "sort_order", "is_active")
    show_change_link = True  # open the chapter to edit its topics


class TopicInline(DraftOnlyDeleteMixin, admin.TabularInline):
    model = Topic
    extra = 0
    fields = ("key", "name", "kind", "sort_order", "is_active")


class SubjectForm(forms.ModelForm):
    add_chapters = forms.CharField(
        required=False,
        label="Add chapters in bulk",
        widget=forms.Textarea(attrs={"rows": 6, "cols": 80}),
        help_text="One chapter per line. Optional marks after a bar: <code>GST Basics | 5-8</code> or <code>Audit | 6</code>. "
        "Names that already exist are skipped. Keys are created for you.",
    )

    class Meta:
        model = Subject
        fields = "__all__"  # noqa: DJ007 - admin-only form: every editable field is intended

    def clean(self):
        cleaned = super().clean()
        group, scheme = cleaned.get("group"), cleaned.get("scheme")
        if group and scheme and group.scheme_id != scheme.id:
            self.add_error("group", "Pick a group from the same scheme as the paper.")
        return cleaned


@admin.register(Subject)
class SubjectAdmin(DraftOnlyDeleteMixin, LiveEditWarningMixin, ActivateActionsMixin, admin.ModelAdmin):
    form = SubjectForm
    list_display = (
        "name",
        "scheme",
        "group",
        "paper_number",
        "total_marks",
        "chapter_total",
        "sort_order",
        "is_active",
    )
    list_filter = ("scheme__level__course", "scheme__level", "scheme", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name", "key")
    autocomplete_fields = ("scheme",)
    inlines = [ChapterInline]
    actions = ["make_active", "make_inactive"]
    list_select_related = ("scheme", "scheme__level", "group")

    @admin.display(description="Chapters")
    def chapter_total(self, obj):
        return obj.chapters.filter(is_active=True).count()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        text = form.cleaned_data.get("add_chapters", "")
        if text.strip():
            self.message_user(request, f"Added {services.add_chapters_from_text(form.instance, text)} chapters.")


class ChapterForm(forms.ModelForm):
    add_topics = forms.CharField(
        required=False,
        label="Add topics in bulk",
        widget=forms.Textarea(attrs={"rows": 6, "cols": 80}),
        help_text="One topic per line. Optional type after a bar: <code>Blocked credit | section</code> "
        "(concept, section, rule, standard, formula, case_law, illustration). Existing names are skipped.",
    )

    class Meta:
        model = Chapter
        fields = "__all__"  # noqa: DJ007 - admin-only form: every editable field is intended


@admin.register(Chapter)
class ChapterAdmin(DraftOnlyDeleteMixin, LiveEditWarningMixin, ActivateActionsMixin, admin.ModelAdmin):
    form = ChapterForm
    list_display = (
        "name",
        "subject",
        "marks_min",
        "marks_max",
        "weight_source",
        "topic_total",
        "sort_order",
        "is_active",
    )
    list_filter = (
        "subject__scheme__level__course",
        "subject__scheme__level",
        "subject__scheme",
        "weight_source",
        "is_active",
    )
    list_editable = ("marks_min", "marks_max", "weight_source", "sort_order", "is_active")
    search_fields = ("name", "key", "subject__name")
    autocomplete_fields = ("subject",)
    inlines = [TopicInline]
    actions = ["make_active", "make_inactive"]
    list_select_related = ("subject", "subject__scheme")

    @admin.display(description="Topics")
    def topic_total(self, obj):
        return obj.topics.filter(is_active=True).count()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        text = form.cleaned_data.get("add_topics", "")
        if text.strip():
            self.message_user(request, f"Added {services.add_topics_from_text(form.instance, text)} topics.")


@admin.register(Topic)
class TopicAdmin(DraftOnlyDeleteMixin, LiveEditWarningMixin, ActivateActionsMixin, admin.ModelAdmin):
    list_display = ("name", "chapter", "kind", "sort_order", "is_active")
    list_filter = ("chapter__subject__scheme", "kind", "is_active")
    list_editable = ("kind", "sort_order", "is_active")
    search_fields = ("name", "key", "chapter__name")
    autocomplete_fields = ("chapter",)
    actions = ["make_active", "make_inactive"]
    list_select_related = ("chapter", "chapter__subject")


# --- chapter maps ----------------------------------------------------------------------------


class ChapterMapForm(forms.ModelForm):
    class Meta:
        model = ChapterMap
        fields = "__all__"  # noqa: DJ007 - admin-only form: every editable field is intended

    def clean(self):
        cleaned = super().clean()
        a, b = cleaned.get("from_chapter"), cleaned.get("to_chapter")
        if a and b:
            if a.subject.scheme_id == b.subject.scheme_id:
                raise ValidationError("The two chapters must be in different schemes.")
            if a.subject.scheme.level_id != b.subject.scheme.level_id:
                raise ValidationError("Both chapters must belong to the same level.")
        return cleaned


@admin.register(ChapterMap)
class ChapterMapAdmin(admin.ModelAdmin):
    form = ChapterMapForm
    list_display = ("from_chapter", "to_chapter", "relation", "carry_ratio")
    list_filter = ("relation", "to_chapter__subject__scheme")
    autocomplete_fields = ("from_chapter", "to_chapter")
    search_fields = ("from_chapter__name", "to_chapter__name")


# --- "Report a wrong item" inbox -------------------------------------------------------------

_ADMIN_NAME = {
    "course": "course",
    "level": "level",
    "scheme": "scheme",
    "subject": "subject",
    "chapter": "chapter",
    "topic": "topic",
}


@admin.register(SyllabusReport)
class SyllabusReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "node_type", "item", "message", "reporter", "status")
    list_filter = ("status", "node_type")
    search_fields = ("message",)
    readonly_fields = ("node_type", "node_id", "item", "message", "reporter", "created_at")
    fields = ("status", "item", "message", "reporter", "created_at")
    actions = ["mark_accepted", "mark_rejected", "mark_fixed"]
    ordering = ("status", "-created_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Item")
    def item(self, obj):
        from .services import _NODE_MODELS

        model = _NODE_MODELS.get(obj.node_type)
        node = model.objects.filter(pk=obj.node_id).first() if model else None
        if node is None:
            return "(deleted)"
        url = reverse(f"admin:syllabus_{_ADMIN_NAME[obj.node_type]}_change", args=[node.pk])
        return format_html('<a href="{}">{}</a>', url, str(node))

    @admin.display(description="Reported by")
    def reporter(self, obj):
        if not obj.user_id:
            return "Anonymous"
        profile = Profile.objects.filter(pk=obj.user_id).only("email").first()
        return profile.email if profile and profile.email else str(obj.user_id)

    def _set(self, request, queryset, status):
        self.message_user(request, f"{queryset.update(status=status)} reports marked {status}.")

    @admin.action(description="Mark as accepted (will fix)")
    def mark_accepted(self, request, queryset):
        self._set(request, queryset, SyllabusReport.Status.ACCEPTED)

    @admin.action(description="Mark as rejected")
    def mark_rejected(self, request, queryset):
        self._set(request, queryset, SyllabusReport.Status.REJECTED)

    @admin.action(description="Mark as fixed")
    def mark_fixed(self, request, queryset):
        self._set(request, queryset, SyllabusReport.Status.FIXED)
