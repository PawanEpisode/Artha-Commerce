"""
New study material for a cohort (X-01.1 W3.4, `content_published`). The module that owns the content announces it once
through `core.events.CONTENT_PUBLISHED`; this service reaches the students it is for.

For each student with an active enrolment on the level (or any level of the course) it creates the notification (dedupe
key `content:{item_id}`, so a repeated announcement or a retry never sends twice) and plans a `deliver_deferred` job a
moment ahead, so the push is sent by the queue or the sweep and never inside the publisher's request. Quiet hours, the
cap, the category switch ("New content") and the strict send flag are all judged when that job fires.

The audience is read a page at a time and capped at `MAX_AUDIENCE` students per announcement. A larger cohort is
logged as `content_audience_truncated` and the rest is not notified: the in-process event bus has no outbox yet (F-06),
and one request must not write an unbounded number of rows. Re-announcing the same item resumes where the cap stopped,
because the students who already have it are skipped by their dedupe key; a publishing module with large cohorts should
announce again, or move this fan-out to a cursor job, before the first big release.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from modules.coverage import selectors as coverage_selectors

from .. import flags
from ..domain.deeplinks import InvalidDeepLink, validate_deep_link
from ..logs import log_event
from ..scheduling import jobs
from ..scheduling.planning import IMMEDIATE_DELAY
from . import notify as notify_service

EVENT = "content_published"
PAGE = 500
MAX_AUDIENCE = 5000
TITLE_MAX = 160


@dataclass(frozen=True)
class FanOut:
    notified: int = 0
    skipped: int = 0  # already had it, or sending is not on for them
    failed: int = 0
    truncated: bool = False


def announce(
    *, item_id, title, level_id=None, course_id=None, link: str | None = None, now: datetime | None = None
) -> FanOut:
    """Notify the cohort once. Bad input, a switch that is off, or an empty cohort just returns an empty result."""
    if not flags.master_enabled() or flags.event_disabled(EVENT):
        return FanOut()
    title = str(title or "").strip()[:TITLE_MAX]
    item = str(item_id or "").strip()
    if not title or not item or (level_id is None and course_id is None):
        log_event(logging.WARNING, "content_announcement_ignored", reason="incomplete")
        return FanOut()
    if link:
        try:
            validate_deep_link(link)
        except InvalidDeepLink:
            log_event(logging.WARNING, "content_announcement_ignored", reason="invalid_link")
            return FanOut()
    now = now or timezone.now()
    notified = skipped = failed = 0
    after = None
    seen = 0
    while seen < MAX_AUDIENCE:
        page = coverage_selectors.audience_user_ids(
            level_id=level_id, course_id=course_id, after=after, limit=min(PAGE, MAX_AUDIENCE - seen)
        )
        if not page:
            return FanOut(notified, skipped, failed)
        for user_id in page:
            try:
                if _notify_one(user_id, item, title, link, now):
                    notified += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001 - one student's failure must not stop the others
                failed += 1
                log_event(logging.ERROR, "content_notify_failed", error_type=type(exc).__name__)
        seen += len(page)
        after = page[-1]
    more = coverage_selectors.audience_user_ids(level_id=level_id, course_id=course_id, after=after, limit=1)
    if more:
        log_event(logging.ERROR, "content_audience_truncated", cap=MAX_AUDIENCE)
    return FanOut(notified, skipped, failed, truncated=bool(more))


def _notify_one(user_id, item: str, title: str, link: str | None, now: datetime) -> bool:
    if not flags.send_flag_enabled(user_id):
        return False
    notification, created = notify_service.create_notification(
        user_id,
        EVENT,
        context={"item_id": item, "title": title, **({"link": link} if link else {})},
        dedupe_parts={"item_id": item},
        now=now,
    )
    if not created:
        return False
    jobs.plan_deferred(notification, now + IMMEDIATE_DELAY)
    return True
