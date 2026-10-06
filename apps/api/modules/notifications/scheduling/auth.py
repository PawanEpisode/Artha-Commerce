"""
Who may call the internal endpoints (FR-N16): the queue, proven by its signature, or the scheduler, proven by the cron
secret. No student identity, no cookies. Every check is constant time and a refusal never says why.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from django.conf import settings

from ..logs import log_event
from . import queue

SIGNATURE_HEADER = "Upstash-Signature"
BEARER = "Bearer "


def _same(a: str, b: str) -> bool:
    """Compare digests so neither the content nor the length of the secret leaks through timing."""
    return hmac.compare_digest(hashlib.sha256(a.encode()).digest(), hashlib.sha256(b.encode()).digest())


def verify_queue_request(request, job_id) -> bool:
    """A call from the queue to `jobs/{job_id}/fire/`: the signature must match the raw body and the callback URL."""
    signature = request.headers.get(SIGNATURE_HEADER, "")
    if not signature:
        log_event(logging.WARNING, "internal_auth_failed", endpoint="fire", reason="no_signature")
        return False
    try:
        url = queue.fire_callback_url(job_id)
        body = request.body.decode("utf-8")
    except (queue.QueueNotConfigured, UnicodeDecodeError):
        log_event(logging.WARNING, "internal_auth_failed", endpoint="fire", reason="not_verifiable")
        return False
    ok = queue.get_signature_verifier().verify(signature=signature, body=body, url=url)
    if not ok:
        log_event(logging.WARNING, "internal_auth_failed", endpoint="fire", reason="bad_signature")
    return ok


def verify_cron_request(request) -> bool:
    """A call from Vercel cron or pg_cron to `sweep/`: `Authorization: Bearer <CRON_SECRET>`."""
    secret = getattr(settings, "CRON_SECRET", "")
    header = request.headers.get("Authorization", "")
    ok = bool(secret) and header.startswith(BEARER) and _same(header[len(BEARER) :], secret)
    if not ok:
        log_event(logging.WARNING, "internal_auth_failed", endpoint="sweep", reason="bad_secret")
    return ok
