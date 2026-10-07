"""Input validation and output shapes of OCR and export (contract R2): `ExportJob` and the OCR answer."""

from __future__ import annotations

from rest_framework import serializers

from .domain.pagespec import MAX_SPEC_CHARS
from .selectors.exports import ExportView
from .services.exports import SUGGESTION_KEY
from .services.ocr import LANGS, OcrRequest


class OcrBody(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["tesseract", "ai"])
    lang = serializers.ChoiceField(choices=list(LANGS), required=False)
    pages = serializers.CharField(required=False, allow_blank=True, max_length=MAX_SPEC_CHARS)


class ExportBody(serializers.Serializer):
    client_id = serializers.UUIDField()
    # Shape and values are checked by `domain.export_options` against the page count, which needs the document.
    options = serializers.DictField(required=False)

    def validate_options(self, value):
        tags = value.get("tags")
        if isinstance(tags, list):
            try:
                value = {**value, "tags": [str(serializers.UUIDField().to_internal_value(t)) for t in tags]}
            except (serializers.ValidationError, TypeError, AttributeError) as exc:
                raise serializers.ValidationError("Tags are ids.") from exc
        return value


class ArchiveBody(serializers.Serializer):
    client_id = serializers.UUIDField()


def ocr_out(result: OcrRequest) -> dict:
    return {
        "status": result.status,
        "ocr_pages_total": result.ocr_pages_total,
        "charged_pages": result.charged_pages,
        "estimate_seconds": result.estimate_seconds,
    }


def export_job_out(view: ExportView) -> dict:
    """
    `{id, kind, document_id, status, progress, page_count, error_code, download_url, expires_at, options, created_at}` plus
    `details: {suggested_pages}` when a PDF export was too large (contract addition). The suggestion is stored among the
    options under a private key, so it is moved out of `options` here.
    """
    job = view.job
    options = {k: v for k, v in job.options.items() if k != SUGGESTION_KEY}
    suggestion = job.options.get(SUGGESTION_KEY)
    return {
        "id": str(job.id),
        "kind": job.kind,
        "document_id": str(job.document_id) if job.document_id else None,
        "status": view.status,
        "progress": job.progress if view.status != "done" else 100,
        "page_count": job.page_count,
        "error_code": job.error_code,
        "download_url": view.download_url,
        "expires_at": job.expires_at.isoformat()
        if job.expires_at
        else None,  # when the file goes; the link itself lasts 24 h
        "options": options,
        "created_at": job.created_at.isoformat(),
        "details": {"suggested_pages": suggestion} if suggestion else None,
    }
