"""
The chapter recall pass (FR-F15-64), worked out after a session closes and never on the review path.

`recall_session_completed` queues one job per session (`recall.chapter_pass`, deduplicated on the session id). The job looks at
each chapter the session touched: when the rule in `domain.chapter_pass` holds and no pass of that chapter was announced in the
last 7 days, the pass is written on the session (`chapter_passes`, the only memory the 7-day rule needs) and
`recall_chapter_pass_completed` is emitted after the commit. A replayed job finds the chapter already written on its session
and re-emits the same event, so a crash between the commit and the emit loses nothing; the consumers are idempotent
(coverage by a client id derived from the session and chapter).

Payload of the event, ids and counts only: `user_id`, `session_id`, `chapter_id`, `chapter_key`, `local_date`, `set_size`,
`coverage_of_set`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db import connection, transaction
from django.utils import timezone

from core import events
from core import jobs as core_jobs

from ..adapters import syllabus as syllabus_adapter
from ..domain import chapter_pass as rule
from ..models import RecallSession
from ..selectors import chapter_pass as reads

JOB_CHAPTER_PASS = "recall.chapter_pass"
EVENT_CHAPTER_PASS = "recall_chapter_pass_completed"


@dataclass(frozen=True)
class Announced:
    chapter_id: str
    chapter_key: str | None
    set_size: int
    coverage_of_set: float
    new: bool  # False when this is a re-emit of a pass the session already carried


def queue_session(user_id, session_id) -> None:
    """Queue the pass check of one closed session. Cheap: one insert, merged with a job already waiting for the session."""
    core_jobs.enqueue(
        JOB_CHAPTER_PASS,
        {"user_id": str(user_id), "session_id": str(session_id)},
        dedupe_key=f"{JOB_CHAPTER_PASS}:{session_id}",
    )


def _lock(user_id) -> None:
    """One check at a time per student, so two sessions closing together cannot both announce the same chapter."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"recall.chapter_pass:{user_id}"])


def evaluate_session(user_id, session_id, *, now: datetime | None = None) -> list[Announced]:
    """Announce the chapter passes this session earned. Idempotent: a second run announces the same passes again, writes nothing."""
    now = now or timezone.now()
    with transaction.atomic():
        _lock(user_id)
        session = RecallSession.objects.select_for_update().filter(user_id=user_id, id=session_id).first()
        if session is None or session.status == "open":
            return []  # a session that is still open will queue its own check when it closes
        carried = {p["chapter_id"]: p for p in session.chapter_passes or ()}
        found: list[tuple[str, int, float, bool]] = []  # chapter id, set size, coverage, new
        written = list(session.chapter_passes or ())
        for chapter_id in reads.chapters_of_session(user_id, session.id):
            key = str(chapter_id)
            if key in carried:
                found.append((key, carried[key]["set_size"], carried[key]["coverage_of_set"], False))
                continue
            state = reads.pass_state(user_id, chapter_id, now=now)
            if not state.passed:
                continue
            last = reads.last_pass_at(user_id, chapter_id, now=now, exclude_session_id=session.id)
            if not rule.cooldown_over(last, now):
                continue
            written.append(
                {
                    "chapter_id": key,
                    "at": now.isoformat(),
                    "set_size": state.set_size,
                    "coverage_of_set": state.coverage_of_set,
                }
            )
            found.append((key, state.set_size, state.coverage_of_set, True))
        if len(written) != len(session.chapter_passes or ()):
            session.chapter_passes = written
            session.save(update_fields=["chapter_passes", "updated_at"])
        keys = syllabus_adapter.chapter_refs(UUID(c[0]) for c in found)
        announced = [
            Announced(c, getattr(keys.get(UUID(c)), "key", None), size, coverage, new)
            for c, size, coverage, new in found
        ]
        for a in announced:
            payload = {
                "user_id": str(user_id),
                "session_id": str(session.id),
                "chapter_id": a.chapter_id,
                "chapter_key": a.chapter_key,
                "local_date": session.local_date.isoformat(),
                "set_size": a.set_size,
                "coverage_of_set": a.coverage_of_set,
            }
            transaction.on_commit(lambda p=payload: events.emit(EVENT_CHAPTER_PASS, **p))
        return announced


def run_job(payload: dict) -> dict:
    announced = evaluate_session(payload["user_id"], UUID(payload["session_id"]))
    return {"passes": len(announced), "new": sum(1 for a in announced if a.new)}
