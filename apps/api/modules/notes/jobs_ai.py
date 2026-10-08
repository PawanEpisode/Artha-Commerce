"""
Handlers of the R3 AI jobs and their expiry, registered by `notes.jobs.register_handlers`. Glue only: the work is in
`services.summary`. `notes.summarize` is a heavy (worker) job because it waits on Google; the tick never runs it.
"""

from __future__ import annotations

from .services import ai_jobs, ai_ocr, reanchor, summary, unlock

JOB_SUMMARIZE = summary.JOB_SUMMARIZE
JOB_OCR_AI = ai_ocr.JOB_OCR_AI
JOB_REANCHOR = reanchor.JOB_REANCHOR
JOB_UNLOCK = unlock.JOB_UNLOCK
JOB_EXPIRE_UNLOCK = "notes.expire_unlock"
JOB_EXPIRE_AI = "notes.expire_ai"


def summarize_job(payload: dict) -> dict:
    return summary.run_summary(payload)


def ocr_ai_job(payload: dict) -> dict:
    return ai_ocr.run_ai_ocr(payload)


def reanchor_job(payload: dict) -> dict:
    return reanchor.run_reanchor(payload)


def unlock_job(payload: dict) -> dict:
    return unlock.run_unlock(payload)


def expire_unlock_job(payload: dict) -> dict:
    return {"cleared": unlock.expire_secrets()}


def expire_ai_job(payload: dict) -> dict:
    return {"expired": ai_jobs.expire_drafts()}


def register_handlers(jobs_module) -> None:
    jobs_module.register_handler(JOB_SUMMARIZE, summarize_job)
    jobs_module.register_gave_up_handler(JOB_SUMMARIZE, summary.give_up)
    jobs_module.register_handler(JOB_OCR_AI, ocr_ai_job)
    jobs_module.register_gave_up_handler(JOB_OCR_AI, ai_ocr.give_up)
    jobs_module.register_handler(JOB_REANCHOR, reanchor_job)
    jobs_module.register_gave_up_handler(JOB_REANCHOR, reanchor.give_up)
    jobs_module.register_handler(JOB_UNLOCK, unlock_job)
    jobs_module.register_gave_up_handler(JOB_UNLOCK, unlock.give_up)
    jobs_module.register_handler(JOB_EXPIRE_UNLOCK, expire_unlock_job)
    jobs_module.register_handler(JOB_EXPIRE_AI, expire_ai_job)
