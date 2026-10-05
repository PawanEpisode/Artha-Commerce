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
import uuid

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

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


class PaperFilter(admin.SimpleListFilter):
    """
    Papers of the scheme picked in the scheme filter. Hidden until a scheme is picked (there are hundreds of papers
    across all schemes). `scheme_param` is the admin's own query parameter of the scheme filter on this page and
    `subject_path` the lookup that leads from the listed model to its paper.
    """

    title = "paper"
    parameter_name = "paper"
    scheme_param = ""
    subject_path = ""

    def _scheme_id(self, request) -> str | None:
        return request.GET.get(self.scheme_param) or None

    def lookups(self, request, model_admin):
        scheme_id = self._scheme_id(request)
        if not scheme_id:
            return []
        subjects = Subject.objects.filter(scheme_id=scheme_id).order_by("sort_order", "key")
        return [(str(s.id), f"{s.paper_number}. {s.name}" if s.paper_number else s.name) for s in subjects]

    def queryset(self, request, queryset):
        value = self.value()
        scheme_id = self._scheme_id(request)
        # A paper left over from another scheme (the scheme filter was changed afterwards) is ignored.
        if value and scheme_id and Subject.objects.filter(pk=value, scheme_id=scheme_id).exists():
            return queryset.filter(**{self.subject_path: value})
        return queryset


class ChapterFilter(admin.SimpleListFilter):
    """Chapters of the paper picked in the paper filter. Hidden until a paper is picked."""

    title = "chapter"
    parameter_name = "chapter"

    def lookups(self, request, model_admin):
        paper = request.GET.get("paper")
        if not paper:
            return []
        chapters = Chapter.objects.filter(subject_id=paper).order_by("sort_order", "key")
        return [(str(c.id), c.name[:80]) for c in chapters]

    def queryset(self, request, queryset):
        value = self.value()
        paper = request.GET.get("paper")
        if value and paper and Chapter.objects.filter(pk=value, subject_id=paper).exists():
            return queryset.filter(chapter_id=value)
        return queryset


class ChapterPaperFilter(PaperFilter):
    scheme_param = "subject__scheme__id__exact"
    subject_path = "subject_id"


class TopicPaperFilter(PaperFilter):
    scheme_param = "chapter__subject__scheme__id__exact"
    subject_path = "chapter__subject_id"


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


class ReorderMixin:
    """
    Drag-and-drop ordering (`sort_order`) for papers, chapters and topics.

    Inline tables are reordered in the browser and saved with the form. Change lists post the new order to
    `<model>/reorder/` at once; that only works while the list is filtered to one parent (`reorder_scope_param` is set),
    because `sort_order` is numbered within a parent. See static/syllabus/admin/reorder.js.
    """

    change_list_template = "admin/syllabus/reorderable_change_list.html"
    reorder_parent_field = ""  # "scheme" for papers, "subject" for chapters, "chapter" for topics
    reorder_scope_param = ""  # change list query parameter that pins the list to one parent
    reorder_scope_hint = ""

    class Media:
        css = {"all": ("syllabus/admin/reorder.css",)}
        js = ("syllabus/admin/reorder.js",)

    def _reorder_url_name(self) -> str:
        return f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_reorder"

    def get_urls(self):
        custom = [
            path(
                "reorder/",
                self.admin_site.admin_view(require_POST(self.reorder_view)),
                name=self._reorder_url_name().removeprefix("admin:"),
            )
        ]
        return custom + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        enabled = bool(request.GET.get(self.reorder_scope_param)) and self.has_change_permission(request)
        config = {"url": reverse(self._reorder_url_name()), "enabled": enabled, "hint": self.reorder_scope_hint}
        return super().changelist_view(request, {**(extra_context or {}), "reorder_config": config})

    def reorder_view(self, request):
        try:
            body = json.loads(request.body or b"{}")
            ids = [str(uuid.UUID(str(i))) for i in body["ids"]]
        except (ValueError, KeyError, TypeError):
            return JsonResponse({"error": "The new order could not be read."}, status=400)
        if not 1 <= len(ids) <= 500 or len(set(ids)) != len(ids):
            return JsonResponse({"error": "The new order could not be read."}, status=400)
        by_id = {str(o.pk): o for o in self.model.objects.filter(pk__in=ids)}
        if len(by_id) != len(ids):
            return JsonResponse({"error": "Some rows no longer exist."}, status=404)
        parents = {getattr(o, f"{self.reorder_parent_field}_id") for o in by_id.values()}
        if len(parents) != 1:
            return JsonResponse({"error": self.reorder_scope_hint}, status=400)
        if not all(self.has_change_permission(request, o) for o in by_id.values()):
            return JsonResponse({"error": "You may not change these rows."}, status=403)

        siblings = list(
            self.model.objects.filter(**{f"{self.reorder_parent_field}_id": parents.pop()}).order_by(
                "sort_order", "key"
            )
        )
        slots = [i for i, o in enumerate(siblings) if str(o.pk) in by_id]  # positions the dragged rows occupy now
        arranged = list(siblings)
        for slot, row_id in zip(slots, ids, strict=True):
            arranged[slot] = by_id[row_id]
        changed = []
        for order, obj in enumerate(arranged):
            if obj.sort_order != order:
                obj.sort_order = order
                changed.append(obj)
        self.model.objects.bulk_update(changed, ["sort_order"])
        for obj in changed:
            if str(obj.pk) in by_id:
                self.log_change(request, obj, f"Moved to position {obj.sort_order + 1}.")
        scheme = scheme_of(arranged[0])
        return JsonResponse(
            {
                "orders": {str(o.pk): o.sort_order for o in arranged},
                "published": bool(scheme and scheme.status == Scheme.Status.PUBLISHED),
            }
        )


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
    list_display = ("name", "course", "level", "code", "exam_start", "exam_end", "is_open")
    list_filter = ("course", "level", "is_open")
    list_editable = ("is_open",)
    list_select_related = ("course", "level")
    search_fields = ("name", "code", "level__name", "course__code")


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
    list_select_related = ("level", "level__course", "from_term", "to_term", "from_term__level", "to_term__level")

    class Media:
        css = {"all": ("syllabus/admin/reorder.css",)}
        js = ("syllabus/admin/reorder.js",)

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
                pending = ChapterMap.objects.filter(to_chapter__subject__scheme=scheme, needs_review=True).count()
                if pending:
                    self.message_user(
                        request,
                        f"{pending} chapter maps into {scheme.code} still need review. Students who switch to it "
                        "carry progress through them as they stand: confirm or fix them under Chapter maps.",
                        messages.WARNING,
                    )
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
        report = services.build_default_chapter_map(old, new)
        self.message_user(
            request,
            f"{old.code} to {new.code}: {report.summary()}",
            messages.WARNING if report.needs_review else messages.SUCCESS,
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
    fields = ("key", "name", "section", "marks_min", "marks_max", "weight_source", "sort_order", "is_active")
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
class SubjectAdmin(ReorderMixin, DraftOnlyDeleteMixin, LiveEditWarningMixin, ActivateActionsMixin, admin.ModelAdmin):
    reorder_parent_field = "scheme"
    reorder_scope_param = "scheme__id__exact"
    reorder_scope_hint = "Pick one scheme in the filter on the right to drag its papers into order."
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
    list_filter = ("scheme__level__course", "scheme__level", "scheme", "group", "kind", "is_optional", "is_active")
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
class ChapterAdmin(ReorderMixin, DraftOnlyDeleteMixin, LiveEditWarningMixin, ActivateActionsMixin, admin.ModelAdmin):
    reorder_parent_field = "subject"
    reorder_scope_param = "paper"
    reorder_scope_hint = "Pick one scheme, then one paper, in the filter on the right to drag its chapters into order."
    form = ChapterForm
    list_display = (
        "name",
        "subject",
        "section",
        "marks_min",
        "marks_max",
        "weight_source",
        "target_practice_sets",
        "target_revisions",
        "target_mocks",
        "topic_total",
        "sort_order",
        "is_active",
    )
    list_filter = (
        "subject__scheme__level__course",
        "subject__scheme__level",
        "subject__scheme",
        ChapterPaperFilter,
        "weight_source",
        "is_active",
    )
    list_editable = (
        "marks_min",
        "marks_max",
        "weight_source",
        "target_practice_sets",
        "target_revisions",
        "target_mocks",
        "sort_order",
        "is_active",
    )
    search_fields = ("name", "key", "section", "subject__name")
    autocomplete_fields = ("subject",)
    inlines = [TopicInline]
    actions = ["make_active", "make_inactive"]
    list_select_related = ("subject", "subject__scheme")

    @admin.display(description="Topics")
    def topic_total(self, obj):
        return obj.topics.filter(is_active=True).count()

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is not None and db_field.name.startswith("target_"):
            # Targets are small counts (0 to 20): keep the editable list columns narrow.
            field.widget.attrs.update({"min": 0, "max": 20, "style": "width: 4.5em"})
        return field

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        text = form.cleaned_data.get("add_topics", "")
        if text.strip():
            self.message_user(request, f"Added {services.add_topics_from_text(form.instance, text)} topics.")


@admin.register(Topic)
class TopicAdmin(ReorderMixin, DraftOnlyDeleteMixin, LiveEditWarningMixin, ActivateActionsMixin, admin.ModelAdmin):
    reorder_parent_field = "chapter"
    reorder_scope_param = "chapter"
    reorder_scope_hint = (
        "Pick a scheme, a paper and then a chapter in the filter on the right to drag its topics into order."
    )
    list_display = ("name", "paper", "chapter_name", "scheme_name", "kind", "sort_order", "is_active")
    list_filter = (
        "chapter__subject__scheme__level__course",
        "chapter__subject__scheme",
        TopicPaperFilter,
        ChapterFilter,
        "kind",
        "is_active",
    )
    list_editable = ("kind", "sort_order", "is_active")
    search_fields = ("name", "key", "chapter__name", "chapter__subject__name")
    autocomplete_fields = ("chapter",)
    actions = ["make_active", "make_inactive"]
    list_select_related = ("chapter", "chapter__subject", "chapter__subject__scheme__level__course")
    ordering = (
        "chapter__subject__scheme__level__course__code",
        "chapter__subject__scheme__level__sort_order",
        "chapter__subject__sort_order",
        "chapter__sort_order",
        "sort_order",
    )

    @admin.display(description="Paper", ordering="chapter__subject__sort_order")
    def paper(self, obj):
        return obj.chapter.subject.name

    @admin.display(description="Chapter", ordering="chapter__sort_order")
    def chapter_name(self, obj):
        return obj.chapter.name

    @admin.display(description="Scheme")
    def scheme_name(self, obj):
        return str(obj.chapter.subject.scheme)


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
    """The review queue for proposed maps: low-confidence rows are listed first, flagged until an editor confirms them."""

    form = ChapterMapForm
    list_display = (
        "old_chapter",
        "new_chapter",
        "relation",
        "carry_ratio",
        "basis",
        "confidence",
        "needs_review",
    )
    list_filter = ("needs_review", "relation", "basis", "to_chapter__subject__scheme")
    list_editable = ("relation", "carry_ratio", "needs_review")
    list_select_related = ("from_chapter__subject__scheme", "to_chapter__subject__scheme")
    autocomplete_fields = ("from_chapter", "to_chapter")
    search_fields = ("from_chapter__name", "to_chapter__name")
    readonly_fields = ("basis", "confidence")
    actions = ["mark_reviewed"]
    ordering = ("-needs_review", "confidence", "to_chapter__subject__sort_order", "to_chapter__sort_order")

    @admin.display(description="Old chapter", ordering="from_chapter__name")
    def old_chapter(self, obj):
        c = obj.from_chapter
        return f"{c.subject.scheme.code} | {c.subject.name} | {c.name}"

    @admin.display(description="New chapter", ordering="to_chapter__name")
    def new_chapter(self, obj):
        c = obj.to_chapter
        return f"{c.subject.scheme.code} | {c.subject.name} | {c.name}"

    def save_model(self, request, obj, form, change):
        # An editor who changes a proposed row has looked at it: it leaves the review queue unless they say otherwise.
        if change and form.has_changed() and "needs_review" not in form.changed_data:
            obj.needs_review = False
        super().save_model(request, obj, form, change)

    @admin.action(description="Mark as reviewed (keep as proposed)")
    def mark_reviewed(self, request, queryset):
        self.message_user(request, f"{queryset.filter(needs_review=True).update(needs_review=False)} maps confirmed.")


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
