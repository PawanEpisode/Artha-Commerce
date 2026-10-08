"""
Thin views for /api/v1/notes/: auth, the `notes` flag, parse, call a service or selector, serialise. No ORM and no business
rules here. Every view extends `NotesView` (flag gated) except export, the cron tick, and `DELETE` on the note list
(the account wipe), which must work with the flag off (FR-F03-68): the flag test enumerates the URLs and checks that rule.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.errors import FeatureDisabled
from core.feature_flags import flag_enabled
from core.http import request_has_secret, tagged_response
from core.permissions import ParsedAPIView, flag_required

from . import jobs, selectors, serializers, services
from .errors import NotesFeatureDisabled
from .selectors import NoteFilter
from .views_search import pdf_search_payload

NOTES_FLAG = "notes"
PDF_FLAG = "notes_pdf"
TICK_HEADER = "X-Notes-Tick-Secret"


class NotesView(ParsedAPIView):
    permission_classes = [IsAuthenticated, flag_required(NOTES_FLAG, NotesFeatureDisabled)]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notes_read"


class WriteView(NotesView):
    throttle_scope = "notes_write"


class PdfView(NotesView):
    """R2 endpoints (documents, marks, exports): the `notes` flag AND the `notes_pdf` flag, both fail open like every flag."""

    permission_classes = [*NotesView.permission_classes, flag_required(PDF_FLAG)]


class PdfWriteView(PdfView):
    throttle_scope = "notes_write"


def _card_or_404(user_id, note_id):
    card = selectors.get_note(user_id, note_id)
    if card is None:
        raise NotFound("Note not found.")
    return card


def _filter_of(d: dict) -> NoteFilter:
    return NoteFilter(
        level_id=d.get("level"),
        subject_key=d.get("subject"),
        chapter_key=d.get("chapter"),
        topic_key=d.get("topic"),
        tag_id=d.get("tag"),
        unfiled=d.get("unfiled", False),
        kind=d.get("kind"),
        pinned=d.get("pinned"),
        q=d.get("q", ""),
        date_from=d.get("from"),
        date_to=d.get("to"),
        extra={k: d[k] for k in ("color", "doc") if d.get(k)},
    )


def _page(page, build) -> dict:
    return {"items": [build(i) for i in page.items], "next_cursor": page.next_cursor}


# --- Notes ------------------------------------------------------------------------------------------------------------
class NoteListCreateView(WriteView):
    """
    `GET`/`POST notes/` are the note list and create (flag gated). `DELETE notes/` wipes the account and stays open
    with the flag off (FR-F03-68): it shares this path because the contract puts both on `notes/`.
    """

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_throttles(self):
        if self.request.method == "DELETE":
            self.throttle_scope = "notes_account"
        return super().get_throttles()

    def get(self, request):
        d = self.parse(serializers.NoteListQuery, request.query_params).validated_data
        if d["trashed"]:
            page = selectors.list_trash(request.user.id, cursor=d.get("cursor"), limit=d.get("limit"))
        else:
            page = selectors.list_notes(request.user.id, _filter_of(d), cursor=d.get("cursor"), limit=d.get("limit"))
        return Response(_page(page, serializers.note_summary))

    def post(self, request):
        return _create_note(self, request, None)

    def delete(self, request):
        return Response({"deleted": services.account.delete_all_for_user(request.user.id)})


def _create_note(view, request, note_id):
    """`POST notes/` and `PUT notes/{id}/`: one idempotent create. 201 when new, 200 with the stored note when replayed."""
    d = view.parse(serializers.NoteCreateSerializer, request.data, path_id=note_id).validated_data
    result = services.create_note(
        request.user.id,
        client_id=d.get("client_id"),
        note_id=d.get("id"),
        title=d["title"],
        body_md=d["body_md"],
        chapter_id=d["chapter_id"],
        topic_id=d["topic_id"],
        tag_ids=d["tag_ids"],
    )
    card = _card_or_404(request.user.id, result.note.id)
    return Response(serializers.note_detail(card), status=201 if result.created else 200)


class NoteDetailView(WriteView):
    def get(self, request, note_id):
        return Response(serializers.note_detail(_card_or_404(request.user.id, note_id)))

    def put(self, request, note_id):
        return _create_note(self, request, note_id)

    def patch(self, request, note_id):
        s = self.parse(serializers.NotePatchSerializer, request.data)
        d = s.validated_data
        result = services.update_note(
            request.user.id,
            note_id,
            base_rev=d["base_rev"],
            patch=s.patch(),
            base_body_md=d.get("base_body_md"),
            base=d.get("base"),
            source=d["source"],
            resolution=d.get("resolution"),
        )
        card = _card_or_404(request.user.id, result.note.id)
        return Response(
            {
                **serializers.note_detail(card),
                "merged": result.merged,
                "restored": result.restored,
                "overwritten": result.overwritten,
            }
        )

    def delete(self, request, note_id):
        note = services.trash_note(request.user.id, note_id)
        return Response({"id": note.id, "deleted_at": note.deleted_at, "purge_after": note.purge_after})


class NoteRestoreView(WriteView):
    def post(self, request, note_id):
        note = services.restore_note(request.user.id, note_id)
        return Response(serializers.note_detail(_card_or_404(request.user.id, note.id)))


class VersionListView(NotesView):
    def get(self, request, note_id):
        rows = selectors.list_versions(request.user.id, note_id)
        if rows is None:
            raise NotFound("Note not found.")
        return Response({"items": [serializers.version_row(v) for v in rows]})


class VersionDetailView(NotesView):
    def get(self, request, note_id, rev):
        version = selectors.get_version(request.user.id, note_id, rev)
        if version is None:
            raise NotFound("Version not found.")
        return Response(serializers.version_detail(version))


class VersionRestoreView(WriteView):
    def post(self, request, note_id, rev):
        note = services.restore_version(request.user.id, note_id, rev)
        return Response(serializers.note_detail(_card_or_404(request.user.id, note.id)))


class ChangesView(NotesView):
    def get(self, request):
        d = self.parse(serializers.ChangesQuery, request.query_params).validated_data
        notes, next_since, more = selectors.changes(request.user.id, since=d.get("since"), limit=d["limit"])
        items = [serializers.note_detail(c) for c in selectors.cards_of(notes)]
        return Response({"items": items, "next_since": next_since, "has_more": more})


class ClipView(WriteView):
    def post(self, request):
        d = self.parse(serializers.ClipSerializer, request.data).validated_data
        result = services.create_clip(
            request.user.id,
            client_id=d["client_id"],
            text_md=d["text_md"],
            source=d["source"],
            chapter_id=d["chapter_id"],
            topic_id=d["topic_id"],
            tag_ids=d["tag_ids"],
        )
        card = _card_or_404(request.user.id, result.note.id)
        return Response(
            {"note": serializers.note_detail(card), "created": result.created}, status=201 if result.created else 200
        )


# --- Aggregation, counts, overview, search ------------------------------------------------------------------------------
class AggregateView(NotesView):
    def get(self, request):
        d = self.parse(serializers.AggregateQuery, request.query_params).validated_data
        page = selectors.aggregate(
            request.user.id, _filter_of(d), tab=d["tab"], cursor=d.get("cursor"), limit=d.get("limit")
        )
        return Response(_page(page, serializers.aggregate_item))


class AggregateCountsView(NotesView):
    def get(self, request):
        d = self.parse(serializers.CountsQuery, request.query_params).validated_data
        counts = selectors.subject_counts(request.user.id, d["level"], d["subject"])
        if counts is None:
            raise NotFound("Subject not found.")
        return tagged_response(request, serializers.subject_counts_dict(counts))


class ChapterOverviewView(NotesView):
    def get(self, request, chapter_key):
        d = self.parse(serializers.CountsQuery, request.query_params).validated_data
        overview = selectors.chapter_overview(request.user.id, d["level"], d["subject"], chapter_key)
        if overview is None:
            raise NotFound("Chapter not found.")
        return Response(serializers.overview_dict(overview))


class SearchView(NotesView):
    throttle_scope = "notes_search"

    def get(self, request):
        d = self.parse(serializers.SearchQuery, request.query_params).validated_data
        scope = d["scope"]
        pdf_on = scope != "notes" and flag_enabled(PDF_FLAG, request.user.id)  # R2: PDF text and marks need `notes_pdf`
        if scope == "pdf" and not pdf_on:
            raise FeatureDisabled
        flt = NoteFilter(level_id=d.get("level"), subject_key=d.get("subject"), chapter_key=d.get("chapter"))
        page = selectors.search(request.user.id, d["q"], scope=scope, flt=flt, limit=d["limit"], cursor=d.get("cursor"))
        body = _page(page, serializers.search_hit)
        if pdf_on:
            items, meta = pdf_search_payload(
                request.user.id, d["q"], scope=scope, limit=d["limit"], first_page=not d.get("cursor"), flt=flt
            )
            body["items"] += items
            if meta is not None:
                body["meta"] = meta
        return Response(body)


# --- Tags -------------------------------------------------------------------------------------------------------------
class TagListCreateView(WriteView):
    def get(self, request):
        return Response({"items": [serializers.tag_view(v) for v in selectors.list_tags(request.user.id)]})

    def post(self, request):
        d = self.parse(serializers.TagCreateSerializer, request.data).validated_data
        tag, created = services.tags.create_tag(request.user.id, d["name"], d["color_key"])
        return Response(
            serializers.tag_dict(tag, selectors.get_tag(request.user.id, tag.id).count), status=201 if created else 200
        )


class TagDetailView(WriteView):
    def patch(self, request, tag_id):
        changes = self.parse(serializers.TagUpdateSerializer, request.data).validated_data
        tag = services.tags.update_tag(request.user.id, tag_id, changes)
        return Response(serializers.tag_dict(tag, selectors.get_tag(request.user.id, tag.id).count))

    def delete(self, request, tag_id):
        services.tags.delete_tag(request.user.id, tag_id)
        return Response(status=204)


class ItemTagsView(WriteView):
    def put(self, request):
        d = self.parse(serializers.ItemTagsSerializer, request.data).validated_data
        note = services.retag_note(request.user.id, d["item_id"], d["tag_ids"])
        card = _card_or_404(request.user.id, note.id)
        return Response({"item_type": "note", "item_id": note.id, "tags": [serializers.tag_dict(t) for t in card.tags]})


class ChapterSuggestView(WriteView):
    def post(self, request):
        d = self.parse(serializers.ChapterSuggestSerializer, request.data).validated_data
        found = selectors.suggestions_for(request.user.id, d["text"], d.get("level_id"))
        return Response({"suggestions": [serializers.suggestion_dict(s) for s in found]})


# --- Settings, usage --------------------------------------------------------------------------------------------------
class SettingsView(WriteView):
    def get(self, request):
        return Response(serializers.settings_dict(services.settings.get_or_create_settings(request.user.id)))

    def put(self, request):
        changes = self.parse(serializers.SettingsSerializer, request.data).validated_data
        return Response(serializers.settings_dict(services.settings.update_settings(request.user.id, changes)))

    patch = put


class UsageView(NotesView):
    def get(self, request):
        return Response(serializers.usage_dict(selectors.usage(request.user.id)))


# --- Account data (never gated), cron ---------------------------------------------------------------------------------
class DataView(ParsedAPIView):
    """Export and delete everything notes holds for the student. Open with the flag off: data rights come first."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notes_account"


class ExportView(DataView):
    def get(self, request):
        return Response(services.account.export_for_user(request.user.id))


class TickView(ParsedAPIView):
    """
    Cron entry (Vercel Cron GET, or a POST from any scheduler): purges old trash, thins versions, reconciles usage and
    expires stale uploads, bounded to 20 seconds and safe to repeat. Authenticated by a shared secret, not a student token.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes: list = []

    def _tick(self, request):
        if not request_has_secret(request, settings.NOTES_TICK_SECRET, TICK_HEADER):
            return Response({"error": {"code": "forbidden", "message": "Not allowed.", "details": None}}, status=403)
        return Response(jobs.tick())

    get = post = _tick
