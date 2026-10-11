"""
Recall reacts to other modules' events by name and payload; it never imports the module that announces. Every handler only
queues a job, so a slow or failing consumer cannot hurt the publisher's write (`core.events` swallows errors anyway).
"""

from __future__ import annotations

from . import jobs

ENROLLMENT_EXAM_CHANGED = "enrollment_exam_changed"  # F-02: exam date or target term edited, or the enrolment archived


def on_enrollment_exam_changed(*, user_id, **_ignored) -> None:
    jobs.queue_student(user_id)


def register() -> None:
    from core import events

    events.subscribe(ENROLLMENT_EXAM_CHANGED, on_enrollment_exam_changed)
