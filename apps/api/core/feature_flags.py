"""
Server-side feature flags, evaluated by PostHog for the signed-in student (distinct id = Supabase user id, the same
id the web identifies with, so web and API always agree).

Same rule as the web hook `useFeatureFlag`: only an explicit `false` turns a feature off. No PostHog key (local
development, tests), an unknown flag, a timeout or any PostHog error all mean ON, so a flag outage never locks
students out. Answers are cached in memory for a short time so a flag costs at most one PostHog call per student
per minute per server instance.
"""

from __future__ import annotations

import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)

_client = None
_cache: dict[tuple[str, str], tuple[float, bool | None]] = {}
_CACHE_LIMIT = 10_000


def _posthog():
    """One lazily created client. `sync_mode` and no local evaluation: no background threads on serverless."""
    global _client
    if not settings.POSTHOG_API_KEY:
        return None
    if _client is None:
        from posthog import Posthog

        _client = Posthog(
            project_api_key=settings.POSTHOG_API_KEY,
            host=settings.POSTHOG_HOST,
            sync_mode=True,
            enable_local_evaluation=False,
            feature_flags_request_timeout_seconds=settings.POSTHOG_FLAG_TIMEOUT_SECONDS,
            feature_flags_request_max_retries=0,
        )
    return _client


def _lookup(name: str, distinct_id) -> bool | None:
    """True or False when PostHog answered; None when it could not (no key, unknown flag or any error)."""
    client = _posthog()
    if client is None:
        return None
    key = (name, str(distinct_id))
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < settings.FEATURE_FLAG_CACHE_SECONDS:
        return cached[1]
    try:
        value = client.get_feature_flag(name, str(distinct_id), send_feature_flag_events=False)
    except Exception:  # noqa: BLE001 - a flag service problem must never break the API
        logger.warning("PostHog flag lookup failed for %s; treating it as unknown", name, exc_info=True)
        return None
    answer = None if value is None else value is not False  # None: the flag does not exist or could not be evaluated
    if len(_cache) >= _CACHE_LIMIT:
        _cache.clear()
    _cache[key] = (now, answer)
    return answer


def flag_enabled(name: str, distinct_id, *, strict: bool = False) -> bool:
    """
    Never raises. Default (fail open): False only when PostHog says the flag is off for this user.
    `strict=True` (fail closed) is for actions that must never happen by accident, such as sending notifications:
    only an explicit answer of on counts, so a missing key, an unknown flag or an outage all mean off.
    """
    answer = _lookup(name, distinct_id)
    if answer is None:
        return not strict
    return answer


def clear_flag_cache() -> None:
    _cache.clear()
