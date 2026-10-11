"""
Recall reacts to other modules' events by name and payload; it never imports the module that announces. Every handler only
queues a job, so a slow or failing consumer cannot hurt the publisher's write (`core.events` swallows errors anyway).

    enrollment_exam_changed      F-02: exam date or target term edited, or the enrolment archived        -> exam horizon of her cards
    enrollment_scheme_changed    F-02: her active enrolment moved to a new scheme (user_id, new_scheme_id) -> her own cards follow the map
    recall_deck_published        recall itself: a platform deck version went live (deck_version_id)       -> sync followers, mark pins
    amendment_published          F-14 (not built; the contract is its ERD events section)                 -> flag items and her cards
    amendment_corrected          F-14: only when `material` is true
    amendment_retracted          F-14: clears the flags a publication set
    recall_session_completed     recall itself (a session closed)                                         -> the chapter pass check (a job) and the opt-in tracker session
    recall_chapter_pass_completed  recall itself (a chapter set was passed)                               -> one coverage revision, when her `recall_counts_as_revision` is on
"""

from __future__ import annotations

from uuid import UUID

from core import jobs as core_jobs

from . import jobs
from .adapters import coverage as coverage_adapter
from .domain import amendments as amendment_domain
from .selectors import study as study_selectors
from .services import amendments as amendment_service
from .services import chapter_pass as chapter_pass_service
from .services import remap as remap_service
from .services import sync as sync_service
from .services import tracker_forward

ENROLLMENT_EXAM_CHANGED = "enrollment_exam_changed"  # F-02: exam date or target term edited, or the enrolment archived
ENROLLMENT_SCHEME_CHANGED = "enrollment_scheme_changed"  # F-02: the active enrolment moved to another scheme
ENROLLMENT_SCHEME_SWITCHED = (
    "enrollment_scheme_switched"  # PRD section 9 name; F-02 emits `..._changed`, both are heard
)
DECK_PUBLISHED = "recall_deck_published"
SESSION_COMPLETED = "recall_session_completed"
CHAPTER_PASS_COMPLETED = chapter_pass_service.EVENT_CHAPTER_PASS


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


def on_session_completed_chapter_pass(*, user_id, session_id, by_chapter=(), **_ignored) -> None:
    """Queue the chapter pass check of a closed session, only when it touched a chapter. One insert: nothing heavy on the close."""
    if any(c.get("chapter_id") for c in by_chapter):
        chapter_pass_service.queue_session(user_id, session_id)


def on_session_completed_tracker(
    *, user_id, session_id, started_at=None, active_seconds=0, by_chapter=(), **_ignored
) -> None:
    """FR-F15-73: one auto study session for the tracker, under the tracker's own rules (a few queries; never raises)."""
    tracker_forward.forward_session(
        user_id, session_id=session_id, started_at=started_at, active_seconds=active_seconds, by_chapter=by_chapter
    )


def on_chapter_pass_completed(*, user_id, chapter_id, session_id, **_ignored) -> None:
    """FR-F15-64: a passed chapter set counts as one revision in coverage, only while her `recall_counts_as_revision` is on."""
    if not study_selectors.get_settings(user_id).recall_counts_as_revision:
        return
    coverage_adapter.record_revision_done(user_id, UUID(str(chapter_id)), session_id=session_id)


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
    events.subscribe(SESSION_COMPLETED, on_session_completed_chapter_pass)
    events.subscribe(SESSION_COMPLETED, on_session_completed_tracker)
    events.subscribe(CHAPTER_PASS_COMPLETED, on_chapter_pass_completed)
    events.subscribe(amendment_domain.PUBLISHED, on_amendment_published)
    events.subscribe(amendment_domain.CORRECTED, on_amendment_corrected)
    events.subscribe(amendment_domain.RETRACTED, on_amendment_retracted)
