"""
Thin views of the PDF library (contract R2 "Documents"): auth, the `notes_pdf` flag (`views.PdfView`), parse, call a service or selector,
serialise. Every route answers 403 `feature_disabled` when `notes_pdf` is off for the student. Nothing here touches the ORM.
"""

from __future__ import annotations

from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from . import selectors, services
from . import serializers_documents as out
from .errors import DocumentConflict
from .selectors import DocumentFilter
from .views import PdfView, PdfWriteView


def _detail_or_404(user_id, document_id) -> dict:
    view = selectors.get_document(user_id, document_id)
    if view is None:
        raise NotFound("Document not found.")
    return out.document_detail(view)


def _filter_of(d: dict) -> DocumentFilter:
    return DocumentFilter(
        level_id=d.get("level"),
        subject_key=d.get("subject"),
        chapter_key=d.get("chapter"),
        tag_id=d.get("tag"),
        status=d.get("status"),
        source=d.get("source"),
        q=d.get("q", ""),
        trashed=d["trashed"],
        sort=d["sort"],
    )


class DocumentListCreateView(PdfWriteView):
    def get(self, request):
        d = self.parse(out.ListQuery, request.query_params).validated_data
        page = selectors.list_documents(request.user.id, _filter_of(d), cursor=d.get("cursor"), limit=d.get("limit"))
        return Response({"items": [out.document_summary(v) for v in page.items], "next_cursor": page.next_cursor})

    def get_throttles(self):
        self.throttle_scope = "notes_upload" if self.request.method == "POST" else "notes_read"
        return super().get_throttles()

    def post(self, request):
        d = self.parse(out.ReserveSerializer, request.data).validated_data
        result = services.documents.reserve_document(
            request.user.id,
            client_id=d["client_id"],
            filename=d["filename"],
            bytes=d["bytes"],
            mime=d["mime"],
            page_count_hint=d["page_count_hint"],
            source_kind=d["source_kind"],
            chapter_id=d["chapter_id"],
            topic_id=d["topic_id"],
        )
        body = {
            "document": _detail_or_404(request.user.id, result.document.id),
            "upload": out.upload_dict(result.upload),
        }
        return Response(body, status=201 if result.created else 200)


class DocumentCompleteView(PdfWriteView):
    def post(self, request, document_id):
        document = services.documents.complete_document(request.user.id, document_id)
        return Response(_detail_or_404(request.user.id, document.id))


class DocumentAbortView(PdfWriteView):
    def post(self, request, document_id):
        document = services.documents.abort_document(request.user.id, document_id)
        return Response({"id": document.id, "status": "expired"})


class DocumentDetailView(PdfWriteView):
    def get(self, request, document_id):
        return Response(_detail_or_404(request.user.id, document_id))

    def patch(self, request, document_id):
        s = self.parse(out.PatchSerializer, request.data)
        try:
            document = services.documents.update_document(
                request.user.id, document_id, base_rev=s.validated_data.get("base_rev"), changes=s.changes()
            )
        except DocumentConflict:
            raise DocumentConflict(extra={"theirs": _detail_or_404(request.user.id, document_id)}) from None
        return Response(_detail_or_404(request.user.id, document.id))

    def delete(self, request, document_id):
        if request.query_params.get("permanent") in ("1", "true"):
            services.document_trash.purge_document(request.user.id, document_id)
            return Response({"id": document_id, "purged": True})
        document = services.document_trash.trash_document(request.user.id, document_id)
        return Response({"id": document.id, "deleted_at": document.deleted_at, "purge_after": document.purge_after})


class DocumentRestoreView(PdfWriteView):
    def post(self, request, document_id):
        document = services.document_trash.restore_document(request.user.id, document_id)
        return Response(_detail_or_404(request.user.id, document.id))


class DocumentRangesView(PdfWriteView):
    def put(self, request, document_id):
        d = self.parse(out.RangesSerializer, request.data).validated_data
        result = services.document_ranges.set_page_ranges(request.user.id, document_id, d["ranges"])
        links = selectors.link_views(result.ranges)
        return Response(
            {
                "ranges": [out.page_range(r, link) for r, link in zip(result.ranges, links, strict=True)],
                "relinked": result.relinked,
            }
        )


class DocumentProgressView(PdfWriteView):
    def put(self, request, document_id):
        d = self.parse(out.ProgressSerializer, request.data).validated_data
        document = services.documents.update_progress(
            request.user.id,
            document_id,
            last_page=d["last_page"],
            last_zoom=d["last_zoom"],
            page_tone=d.get("page_tone"),
            set_tone="page_tone" in d,
        )
        return Response(
            {
                "last_page": document.last_page,
                "last_zoom": document.last_zoom,
                "page_tone": document.page_tone,
                "last_opened_at": document.last_opened_at,
            }
        )


class DocumentProcessingView(PdfView):
    def get(self, request, document_id):
        processing = selectors.get_processing(request.user.id, document_id)
        if processing is None:
            raise NotFound("Document not found.")
        return Response(out.processing_dict(processing))


class DocumentPageTextView(PdfView):
    def get(self, request, document_id):
        d = self.parse(out.PagesTextQuery, request.query_params).validated_data
        text = selectors.get_page_text(request.user.id, document_id, d["from"], d["to"])
        if text is None:
            raise NotFound("Document not found.")
        return Response(out.page_text_dict(text))


class DocumentSearchView(PdfView):
    throttle_scope = "notes_search"

    def get(self, request, document_id):
        d = self.parse(out.DocumentSearchQuery, request.query_params).validated_data
        found = selectors.search_document(request.user.id, document_id, d["q"], d["limit"])
        if found is None:
            raise NotFound("Document not found.")
        return Response(out.document_search_dict(found))
