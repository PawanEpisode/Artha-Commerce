"""Input validation and output shapes of the R3 AI endpoints (contract R3)."""

from __future__ import annotations

from rest_framework import serializers

from .models import AiJob
from .services import ai_ocr
from .services.summary import INCLUDE, SummaryRequest


class ConsentBody(serializers.Serializer):
    version = serializers.CharField(max_length=32)


class SummaryBody(serializers.Serializer):
    client_id = serializers.UUIDField()
    chapter_id = serializers.UUIDField()
    include = serializers.ListField(
        child=serializers.ChoiceField(choices=list(INCLUDE)), required=False, allow_empty=False, max_length=2
    )


class AcceptBody(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False, allow_blank=False)
    body_md = serializers.CharField(max_length=100_000, required=False, allow_blank=False, trim_whitespace=False)


class ChapterQuery(serializers.Serializer):
    chapter_id = serializers.UUIDField()


def consent_out(data: dict) -> dict:
    return {
        "text": data["text"],
        "consented": data["consented"],
        "version": data["version"],
        "consented_at": data["consented_at"],
        "withdrawn_at": data["withdrawn_at"],
        "available": data["available"],
    }


def job_out(job: AiJob, *, estimate_seconds: int = 0, cached: bool = False) -> dict:
    """
    `{id, kind, status, chapter: {chapter_id, level_id, subject_key, chapter_key}, item_count, estimate_seconds, cached,
    error_code, charged, created_at, finished_at, expires_at, draft, result_note_id}`. `draft` is `{title, body_md, sources:
    [{n, kind, id, page, document_id, label}], dropped}` only while the job is `ready`.
    """
    scope = job.scope or {}
    draft = None
    if job.status == AiJob.Status.READY and job.result_md is not None:
        meta = job.result_json or {}
        draft = {
            "title": meta.get("title", "Exam summary"),
            "body_md": job.result_md,
            "sources": meta.get("sources", []),
            "dropped": meta.get("dropped", 0),
        }
    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "chapter": {
            "chapter_id": scope.get("chapter_id"),
            "level_id": scope.get("level_id"),
            "subject_key": scope.get("subject_key"),
            "chapter_key": scope.get("chapter_key"),
        },
        "item_count": job.item_count,
        "estimate_seconds": estimate_seconds,
        "cached": cached,
        "error_code": job.error_code,
        "charged": job.charged,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "expires_at": job.expires_at,
        "draft": draft,
        "result_note_id": str(job.result_note_id) if job.result_note_id else None,
    }


def request_out(result: SummaryRequest) -> dict:
    return job_out(result.job, estimate_seconds=result.estimate_seconds, cached=result.cached)


def ocr_job_out(job: AiJob, *, estimate_seconds: int = 0) -> dict:
    """
    `{id, kind: "ocr_page_ai", status, document_id, pages, done: {page: "clear"|"partial"}, failed: {page: code},
    refunded_pages, charged_pages, estimate_seconds, error_code, created_at, finished_at}`. Never any page text: that is read
    from the document like any other page.
    """
    info = ai_ocr.summary_of(job)
    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "document_id": (job.scope or {}).get("document_id"),
        "pages": info["pages"],
        "done": info["done"],
        "failed": info["failed"],
        "refunded_pages": info["refunded_pages"],
        "charged_pages": len(info["pages"]) - len(info["refunded_pages"]),
        "estimate_seconds": estimate_seconds,
        "error_code": job.error_code,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


def ai_ocr_out(result: ai_ocr.AiOcrRequest) -> dict:
    """The answer to `POST documents/{id}/ocr/ {mode: "ai"}`: the job (null when every page was skipped) and why pages were."""
    return {
        "mode": "ai",
        "job": ocr_job_out(result.job, estimate_seconds=result.estimate_seconds) if result.job else None,
        "charged_pages": result.charged_pages,
        "skipped": result.skipped,
        "estimate_seconds": result.estimate_seconds,
    }
