"""Thin views of Replace edition (contract R3): `notes`, `notes_pdf` and `notes_ai` (fail closed). No Gemini is involved, but the feature ships with R3."""

from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import flag_required

from . import selectors
from . import serializers_documents as doc_out
from . import serializers_replace as out
from .errors import NotesFeatureDisabled
from .selectors import reanchor as attention
from .services import reanchor, resumable, unlock
from .views import NOTES_FLAG, PDF_FLAG, NotesView
from .views_ai import AI_FLAG


class ReplaceView(NotesView):
    throttle_scope = "notes_write"
    permission_classes = [
        IsAuthenticated,
        flag_required(NOTES_FLAG, NotesFeatureDisabled),
        flag_required(PDF_FLAG, NotesFeatureDisabled),
        flag_required(AI_FLAG, NotesFeatureDisabled, strict=True),
    ]


def _detail(user_id, document_id) -> dict:
    view = selectors.get_document(user_id, document_id)
    if view is None:
        raise NotFound("Document not found.")
    return doc_out.document_detail(view)


class DocumentReplaceView(ReplaceView):
    def get_throttles(self):
        self.throttle_scope = "notes_upload" if self.request.method == "POST" else "notes_read"
        return super().get_throttles()

    def post(self, request, document_id):
        d = self.parse(out.ReplaceBody, request.data).validated_data
        result = reanchor.request_replace(
            request.user.id,
            document_id,
            client_id=d["client_id"],
            filename=d["filename"],
            bytes=d["bytes"],
            mime=d["mime"],
            page_count_hint=d["page_count_hint"],
            edition_label=d["edition_label"],
        )
        body = {
            "document": _detail(request.user.id, result.document.id),
            "upload": doc_out.upload_dict(result.upload, resumable.hint(request.user.id, result.document)),
        }
        return Response(body, status=201 if result.created else 200)


class AttentionView(ReplaceView):
    throttle_scope = "notes_read"

    def get(self, request, document_id):
        q = self.parse(out.AttentionQuery, request.query_params).validated_data
        found = attention.get_attention(request.user.id, document_id, status=q.get("status"))
        if found is None:
            raise NotFound("Document not found.")
        return Response(out.attention_out(found))


class AttentionItemView(ReplaceView):
    def post(self, request, document_id, item_id):
        d = self.parse(out.ResolveBody, request.data).validated_data
        item = reanchor.resolve_item(request.user.id, document_id, item_id, action=d["action"], page=d["page"])
        return Response(out.item_out(item))


class DocumentUnlockView(ReplaceView):
    """Unlock for search: the password is sealed at once and never stored or logged. 202, then the document's `unlock_status` tells."""

    throttle_scope = "notes_unlock"

    def post(self, request, document_id):
        d = self.parse(out.UnlockBody, request.data).validated_data
        document = unlock.request_unlock(request.user.id, document_id, d["password"])
        return Response(
            {"document_id": document.id, "unlock_status": document.unlock_status}, status=status.HTTP_202_ACCEPTED
        )


class ResumableView(ReplaceView):
    """Sending a big PDF in parts (flag `notes_ai`, S3 credentials set). `POST` opens it or says which parts storage holds."""

    throttle_scope = "notes_upload"

    def post(self, request, document_id):
        return Response(resumable.start(request.user.id, document_id))


class ResumablePartsView(ReplaceView):
    throttle_scope = "notes_upload"

    def post(self, request, document_id):
        d = self.parse(out.PartNumbers, request.data).validated_data
        return Response({"parts": resumable.sign_parts(request.user.id, document_id, d["numbers"])})


class ResumableFinishView(ReplaceView):
    throttle_scope = "notes_upload"

    def post(self, request, document_id):
        d = self.parse(out.FinishBody, request.data).validated_data
        return Response(resumable.finish(request.user.id, document_id, d["parts"]))
