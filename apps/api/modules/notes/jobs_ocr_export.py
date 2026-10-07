"""
Handlers of the heavy OCR and export jobs, and the light expiry job, registered by `notes.jobs.register_handlers`. Glue only:
the work is in `services.ocr`, `services.exports` and `services.archive`. The one thing added here is the end of the line: when
an attempt that fails is the LAST one, the service's `give_up` runs (status `failed`, refunds) before the error propagates.
"""

from __future__ import annotations

from core import jobs as core_jobs

from .services import archive, exports, ocr

JOB_OCR = ocr.JOB_OCR
JOB_EXPORT_PDF = exports.JOB_EXPORT_PDF
JOB_EXPORT_ARCHIVE = archive.JOB_EXPORT_ARCHIVE
JOB_EXPIRE_EXPORTS = "notes.expire_exports"


def _last_attempt() -> bool:
    job = core_jobs.current_job()
    return job is not None and job.attempts >= job.max_attempts


def ocr_job(payload: dict) -> dict:
    try:
        return ocr.run_chunk(payload)
    except Exception:
        if _last_attempt():
            ocr.give_up(payload)
        raise


def export_pdf_job(payload: dict) -> dict:
    try:
        return exports.run_pdf_export(payload["export_id"])
    except Exception:
        if _last_attempt():
            exports.give_up(payload["export_id"])
        raise


def export_archive_job(payload: dict) -> dict:
    try:
        return archive.run_archive(payload["export_id"])
    except Exception:
        if _last_attempt():
            archive.give_up(payload["export_id"])
        raise


def expire_exports_job(payload: dict) -> dict:
    return exports.expire_exports()


def register_handlers(jobs_module) -> None:
    jobs_module.register_handler(JOB_OCR, ocr_job)
    jobs_module.register_handler(JOB_EXPORT_PDF, export_pdf_job)
    jobs_module.register_handler(JOB_EXPORT_ARCHIVE, export_archive_job)
    jobs_module.register_handler(JOB_EXPIRE_EXPORTS, expire_exports_job)
