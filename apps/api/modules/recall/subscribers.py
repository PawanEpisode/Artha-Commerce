"""
Recall reacts to other modules' events by name and payload; it never imports the module that announces. Every handler only
queues a job, so a slow or failing consumer cannot hurt the publisher's write (`core.events` swallows errors anyway).

    enrollment_exam_changed      F-02: exam date or target term edited, or the enrolment archived        -> exam horizon of her cards
    enrollment_scheme_changed    F-02: her active enrolment moved to a new scheme (user_id, new_scheme_id) -> her own cards follow the map
    recall_deck_published        recall itself: a platform deck version went live (deck_version_id)       -> sync followers, mark pins
    amendment_published          F-14 (not built; the contract is its ERD events section)                 -> flag items and her cards
    amendment_corrected          F-14: only when `material` is true
    amendment_retracted          F-14: clears the flags a publication set
"""

from __future__ import annotations

from uuid import UUID

from core import jobs as core_jobs

from . import jobs
from .domain import amendments as amendment_domain
from .services import amendments as amendment_service
from .services import remap as remap_service
from .services import sync as sync_service

ENROLLMENT_EXAM_CHANGED = "enrollment_exam_changed"  # F-02: exam date or target term edited, or the enrolment archived
ENROLLMENT_SCHEME_CHANGED = "enrollment_scheme_changed"  # F-02: the active enrolment moved to another scheme
ENROLLMENT_SCHEME_SWITCHED = "enrollment_scheme_switched"  # PRD section 9 name; F-02 emits `..._changed`, both are heard
DECK_PUBLISHED = "recall_deck_published"


def on_enrollment_exam_changed(*, user_id, **_ignored) -> None:
    jobs.queue_student(user_id)


def on_enrollment_scheme_changed(*, user_id, new_scheme_id=None, **_ignored) -> None:
    if new_scheme_id:
        remap_service.queue_student(user_id, new_scheme_id)


def on_deck_published(*, deck_version_id=None, deck_id=None, version_no=None, **_ignored) -> None:
    """A deck version is live: sync the followers in chunks of 200 and mark the pinned subscriptions (one job per version and chunk)."""
    if deck_version_id is None and deck_id is not None and version_no is not None:
        from .models import RecallDeckVersion

        found = (
            RecallDeckVersion.objects.filter(deck_id=deck_id, version_no=version_no)
            .values_list("id", flat=True)
            .first()
        )
        deck_version_id = found
    if deck_version_id is None:
        return
    core_jobs.enqueue(
        sync_service.JOB_SYNC_SUBSCRIBERS,
        {"deck_version_id": str(UUID(str(deck_version_id))), "chunk": 0, "after": None},
        dedupe_key=f"{sync_service.JOB_SYNC_SUBSCRIBERS}:{deck_version_id}:0",
    )


def _amendment(kind: str):
    def handler(**payload) -> None:
        amendment_service.queue_event(kind, payload)

    handler.__name__ = f"on_{kind}"
    return handler


on_amendment_published = _amendment(amendment_domain.PUBLISHED)
on_amendment_corrected = _amendment(amendment_domain.CORRECTED)
on_amendment_retracted = _amendment(amendment_domain.RETRACTED)


def register() -> None:
    from core import events

    events.subscribe(ENROLLMENT_EXAM_CHANGED, on_enrollment_exam_changed)
    events.subscribe(ENROLLMENT_SCHEME_CHANGED, on_enrollment_scheme_changed)
    events.subscribe(ENROLLMENT_SCHEME_SWITCHED, on_enrollment_scheme_changed)  # the name the PRD proposed for F-02
    events.subscribe(DECK_PUBLISHED, on_deck_published)
    events.subscribe(amendment_domain.PUBLISHED, on_amendment_published)
    events.subscribe(amendment_domain.CORRECTED, on_amendment_corrected)
    events.subscribe(amendment_domain.RETRACTED, on_amendment_retracted)
