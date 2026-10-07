"""
Thin views of OCR and export (contract R2): parse, call a service or selector, serialise. They extend `NotesView` (the `notes`
flag) and add `notes_pdf`, except the archive, which is a data-portability feature and needs only `notes`.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.feature_flags import flag_enabled
from core.permissions import flag_required

from . import serializers_ocr_export as out
from .errors import NotesFeatureDisabled
from .selectors import exports as export_selectors
from .services import archive, exports, ocr
from .views import NOTES_FLAG, PDF_FLAG, NotesView


class PdfNotesView(NotesView):
    permission_classes = [
        IsAuthenticated,
        flag_required(NOTES_FLAG, NotesFeatureDisabled),
        flag_required(PDF_FLAG, NotesFeatureDisabled),
    ]


class DocumentOcrView(PdfNotesView):
    throttle_scope = "notes_write"

    def post(self, request, document_id):
        d = self.parse(out.OcrBody, request.data).validated_data
        result = ocr.request_ocr(
            request.user.id, document_id, mode=d["mode"], lang=d.get("lang"), pages=d.get("pages") or None
        )
        return Response(out.ocr_out(result), status=status.HTTP_202_ACCEPTED)


class DocumentExportView(PdfNotesView):
    throttle_scope = "notes_export"

    def post(self, request, document_id):
        d = self.parse(out.ExportBody, request.data).validated_data
        result = exports.request_export(request.user.id, document_id, d.get("options"), client_id=d["client_id"])
        view = export_selectors.get_export(request.user.id, result.job.id)
        code = status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK
        return Response({"export": out.export_job_out(view)}, status=code)


class ArchiveView(NotesView):
    """ "Download my notes": only the `notes` flag, because a student's own text is theirs whatever the PDF release is doing."""

    throttle_scope = "notes_export"

    def post(self, request):
        d = self.parse(out.ArchiveBody, request.data).validated_data
        job, created = archive.request_archive(request.user.id, client_id=d["client_id"])
        view = export_selectors.get_export(request.user.id, job.id)
        code = status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
        return Response({"export": out.export_job_out(view)}, status=code)


class ExportDetailView(NotesView):
    """A student's own export, the PDF kind only while `notes_pdf` is on; an archive needs only `notes`."""

    def get(self, request, export_id):
        view = export_selectors.get_export(request.user.id, export_id)
        if view is None:
            raise NotFound("Export not found.")
        if view.job.kind == "pdf" and not flag_enabled(PDF_FLAG, request.user.id):
            raise NotesFeatureDisabled
        return Response(out.export_job_out(view))
