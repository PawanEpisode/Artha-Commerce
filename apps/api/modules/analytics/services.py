"""
Business logic and write services for Performance Analytics (F-10).
Handles session fact ingestion, reconciliation, fix set creation, snapshots, and account privacy.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from .domain.facts import build_facts
from .domain.limits import FIX_SET_DEFAULT_SIZE, FIX_SET_MAX_SIZE, FIX_SET_MIN_SIZE
from .domain.readiness import ReadinessResult
from .integrations import practice as practice_adapter
from .integrations import questionbank as qb_adapter
from .integrations import syllabus as syllabus_adapter
from .models import (
    ChapterFact,
    Goal,
    MistakeTag,
    ReadinessProfile,
    ReadinessSnapshot,
    Report,
    SessionRun,
    Settings,
    Share,
    TopicFact,
    UserState,
)

logger = logging.getLogger(__name__)


@dataclass
class RefreshResult:
    session_id: uuid.UUID
    state: str
    fact_rows: int
    changed: bool


def refresh_session(user_id: uuid.UUID, session_id: uuid.UUID) -> RefreshResult:
    """
    Idempotent refresh algorithm (ERD section 3.4).
    Processes session answers into chapter and topic facts under a row-level lock.
    """
    now = timezone.now()

    with transaction.atomic():
        # Step 1: Lock or insert SessionRun row
        run, _ = SessionRun.objects.select_for_update().get_or_create(
            session_id=session_id,
            defaults={
                "user_id": user_id,
                "origin_module": "unknown",
                "mode": "untimed",
                "completion": "submitted",
                "session_created_at": now,
                "local_date": now.date(),
                "state": SessionRun.State.OK,
                "refreshed_at": now,
            },
        )

        # Step 2: Load session from practice
        sess = practice_adapter.get_session(user_id, session_id)
        if not sess:
            # Session was deleted or not found
            forget_session(user_id, session_id)
            return RefreshResult(session_id=session_id, state="removed", fact_rows=0, changed=True)

        if sess["status"] not in ("submitted", "auto_submitted", "abandoned"):
            # Session not finished yet
            return RefreshResult(session_id=session_id, state=run.state, fact_rows=0, changed=False)

        # Update run metadata
        run.user_id = user_id
        run.origin_module = sess.get("origin_module") or "unknown"
        run.mode = sess.get("mode") or "untimed"
        run.completion = sess.get("status") or "submitted"
        run.session_created_at = sess.get("created_at") or now
        run.local_date = sess.get("local_date") or now.date()
        run.tz = sess.get("tz") or "Asia/Kolkata"

        # Step 3: Load answers & version labels
        answers = practice_adapter.get_session_answers(user_id, session_id)
        version_ids = [a["question_version_id"] for a in answers if a.get("question_version_id")]
        labels_by_ver = qb_adapter.get_labels_of_versions(version_ids)

        # Step 4: Pure fact calculation
        facts_payload = build_facts(sess, answers, labels_by_ver)
        content_hash = facts_payload["content_hash"]

        # Step 5: Check if content hash is identical
        if run.content_hash == content_hash and run.state == SessionRun.State.OK:
            run.refreshed_at = now
            run.save(update_fields=["refreshed_at"])
            return RefreshResult(session_id=session_id, state=run.state, fact_rows=run.fact_rows, changed=False)

        # Step 6: Upsert facts
        chapter_facts = facts_payload["chapter_facts"]
        topic_facts = facts_payload["topic_facts"]
        mistake_tags = facts_payload["mistake_tags"]

        for cf in chapter_facts:
            ChapterFact.objects.update_or_create(
                session_id=session_id,
                chapter_id=cf["chapter_id"],
                kind=cf["kind"],
                difficulty=cf["difficulty"],
                source_kind=cf["source_kind"],
                is_repeat=cf["is_repeat"],
                local_date=cf["local_date"],
                defaults={
                    "user_id": user_id,
                    "subject_key": cf["subject_key"],
                    "chapter_key": cf["chapter_key"],
                    "mode": cf["mode"],
                    "answered": cf["answered"],
                    "correct": cf["correct"],
                    "incorrect": cf["incorrect"],
                    "partial": cf["partial"],
                    "skipped": cf["skipped"],
                    "credit_sum": cf["credit_sum"],
                    "est_answered": cf["est_answered"],
                    "est_credit_sum": cf["est_credit_sum"],
                    "pending": cf["pending"],
                    "time_n": cf["time_n"],
                    "time_ms_sum": cf["time_ms_sum"],
                    "sugg_n": cf["sugg_n"],
                    "sugg_ms_sum": cf["sugg_ms_sum"],
                    "nosugg_marks_sum": cf["nosugg_marks_sum"],
                    "marks_awarded_sum": cf["marks_awarded_sum"],
                    "marks_max_sum": cf["marks_max_sum"],
                    "refreshed_at": now,
                },
            )

        for tf in topic_facts:
            TopicFact.objects.update_or_create(
                session_id=session_id,
                topic_id=tf["topic_id"],
                is_repeat=tf["is_repeat"],
                local_date=tf["local_date"],
                defaults={
                    "user_id": user_id,
                    "chapter_id": tf["chapter_id"],
                    "subject_key": tf["subject_key"],
                    "mode": tf["mode"],
                    "answered": tf["answered"],
                    "correct": tf["correct"],
                    "incorrect": tf["incorrect"],
                    "partial": tf["partial"],
                    "skipped": tf["skipped"],
                    "credit_sum": tf["credit_sum"],
                    "est_answered": tf["est_answered"],
                    "est_credit_sum": tf["est_credit_sum"],
                    "refreshed_at": now,
                },
            )

        # Step 7: Prune stale facts for this session
        ChapterFact.objects.filter(session_id=session_id, refreshed_at__lt=now).delete()
        TopicFact.objects.filter(session_id=session_id, refreshed_at__lt=now).delete()

        # Mistake tags
        MistakeTag.objects.filter(session_id=session_id).delete()
        for mt in mistake_tags:
            MistakeTag.objects.create(
                session_id=session_id,
                position=mt["position"],
                user_id=user_id,
                chapter_id=mt["chapter_id"],
                subject_key=mt["subject_key"],
                topic_id=mt.get("topic_id"),
                reason=mt["reason"],
                local_date=mt["local_date"],
                tagged_at=mt.get("tagged_at") or now,
                refreshed_at=now,
            )

        total_rows = len(chapter_facts) + len(topic_facts)

        # Step 8: Update SessionRun and UserState
        run.content_hash = content_hash
        run.fact_rows = total_rows
        run.state = SessionRun.State.OK
        run.attempts = 0
        run.last_error = None
        run.refreshed_at = now
        if not run.first_refreshed_at:
            run.first_refreshed_at = now
        run.save()

        user_state, _ = UserState.objects.get_or_create(user_id=user_id)
        user_state.facts_version += 1
        user_state.last_fact_at = now
        if sess.get("submitted_at"):
            user_state.last_session_at = max(user_state.last_session_at or now, sess["submitted_at"])
        user_state.save()

        return RefreshResult(session_id=session_id, state=run.state, fact_rows=total_rows, changed=True)


def forget_session(user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    """Removes all facts for a deleted or forgotten session."""
    with transaction.atomic():
        ChapterFact.objects.filter(session_id=session_id).delete()
        TopicFact.objects.filter(session_id=session_id).delete()
        MistakeTag.objects.filter(session_id=session_id).delete()

        SessionRun.objects.filter(session_id=session_id).update(
            state=SessionRun.State.REMOVED,
            fact_rows=0,
            refreshed_at=timezone.now(),
        )

        user_state, _ = UserState.objects.get_or_create(user_id=user_id)
        user_state.facts_version += 1
        user_state.last_fact_at = timezone.now()
        user_state.save()


def refresh_pending(user_id: uuid.UUID, limit: int = 5) -> int:
    """
    Finds finished sessions from practice that have not been ingested or need refresh.
    Returns count of sessions refreshed.
    """
    from modules.practice.models import Session as PracticeSession

    unindexed = (
        PracticeSession.objects.filter(user_id=user_id, status__in=["submitted", "auto_submitted"])
        .exclude(id__in=SessionRun.objects.filter(user_id=user_id, state=SessionRun.State.OK).values_list("session_id", flat=True))
        .order_by("-submitted_at")[:limit]
    )

    count = 0
    for sess in unindexed:
        refresh_session(user_id, sess.id)
        count += 1
    return count


def build_fix_set(
    user_id: uuid.UUID,
    *,
    scope_type: str,     # 'topic' or 'chapter'
    scope_id: uuid.UUID,
    size: int = FIX_SET_DEFAULT_SIZE,
    client_id: uuid.UUID | None = None,
    tz: str = "Asia/Kolkata",
) -> dict[str, Any]:
    """
    Generates a targeted revision session for a struggling topic or chapter.
    """
    cl_id = client_id or uuid.uuid4()
    size = max(FIX_SET_MIN_SIZE, min(FIX_SET_MAX_SIZE, size))

    target_name = "Practice Set"
    if scope_type == "topic":
        q_ids = qb_adapter.find_fix_candidates(topic_id=scope_id, limit=size)
        target_name = syllabus_adapter.get_topic_name(scope_id)
    else:
        q_ids = qb_adapter.find_fix_candidates(chapter_id=scope_id, limit=size)
        ch_info = syllabus_adapter.get_chapter_by_id(scope_id)
        if ch_info:
            target_name = ch_info.get("name", "Chapter")

    if not q_ids:
        # Fallback: get any playable questions in the course
        q_ids = qb_adapter.find_fix_candidates(limit=size)

    items = [{"question_id": qid} for qid in q_ids]
    title = f"Fix: {target_name}"

    created = practice_adapter.create_fix_session(
        user_id=user_id,
        items=items,
        client_id=cl_id,
        tz=tz,
        title=title,
        origin_ref=f"{scope_type}:{scope_id}",
    )

    return {
        "session_id": str(created.id),
        "title": created.title,
        "question_count": len(items),
        "item_count": len(items),
        "mode": created.mode,
    }


def save_snapshot(
    user_id: uuid.UUID,
    readiness: ReadinessResult,
    *,
    today: date,
    scope: str = "overall",
    scope_key: str = "",
    profile_id: uuid.UUID | None = None,
) -> None:
    """
    Saves or updates today's readiness snapshot.
    """
    profile = None
    if profile_id:
        profile = ReadinessProfile.objects.filter(id=profile_id).first()
    if not profile:
        profile = ReadinessProfile.objects.filter(status=ReadinessProfile.Status.ACTIVE).first()
    if not profile:
        return

    comp_dicts = [
        {
            "key": c.key,
            "label": c.label,
            "value": c.value,
            "weight": c.weight,
            "points": c.points,
            "available": c.available,
        }
        for c in readiness.components
    ]

    ReadinessSnapshot.objects.update_or_create(
        user_id=user_id,
        scope=scope,
        scope_key=scope_key,
        snapshot_date=today,
        defaults={
            "score": Decimal(str(readiness.score)) if readiness.score is not None else None,
            "half_width": Decimal(str(readiness.half_width)) if readiness.half_width is not None else None,
            "confidence": readiness.confidence,
            "state": readiness.state,
            "profile": profile,
            "formula_version": profile.version,
            "components": comp_dicts,
            "inputs": readiness.inputs,
            "computed_at": timezone.now(),
        },
    )


def delete_all_for_user(user_id: uuid.UUID) -> dict[str, int]:
    """
    Erases all student analytics facts for DPDP compliance (closes AUD-004).
    """
    with transaction.atomic():
        cf_cnt, _ = ChapterFact.objects.filter(user_id=user_id).delete()
        tf_cnt, _ = TopicFact.objects.filter(user_id=user_id).delete()
        mt_cnt, _ = MistakeTag.objects.filter(user_id=user_id).delete()
        sr_cnt, _ = SessionRun.objects.filter(user_id=user_id).delete()
        rs_cnt, _ = ReadinessSnapshot.objects.filter(user_id=user_id).delete()
        g_cnt, _ = Goal.objects.filter(user_id=user_id).delete()
        s_cnt, _ = Settings.objects.filter(user_id=user_id).delete()
        rep_cnt, _ = Report.objects.filter(user_id=user_id).delete()
        sh_cnt, _ = Share.objects.filter(user_id=user_id).delete()

        UserState.objects.filter(user_id=user_id).update(
            facts_version=0,
            last_fact_at=None,
            last_session_at=None,
            data_deleted_at=timezone.now(),
        )

        return {
            "chapter_facts": cf_cnt,
            "topic_facts": tf_cnt,
            "mistake_tags": mt_cnt,
            "session_runs": sr_cnt,
            "readiness_snapshots": rs_cnt,
            "goals": g_cnt,
            "settings": s_cnt,
            "reports": rep_cnt,
            "shares": sh_cnt,
        }


def export_for_user(user_id: uuid.UUID) -> dict[str, Any]:
    """
    Exports all personal analytics data for data portability.
    """
    cf = list(
        ChapterFact.objects.filter(user_id=user_id).values(
            "subject_key", "chapter_key", "kind", "difficulty", "answered", "correct", "local_date"
        )
    )
    snapshots = list(
        ReadinessSnapshot.objects.filter(user_id=user_id).values(
            "scope", "scope_key", "snapshot_date", "score", "confidence", "state"
        )
    )
    goals = list(Goal.objects.filter(user_id=user_id).values("metric", "period", "target", "effective_from"))

    return {
        "chapter_facts": cf,
        "readiness_snapshots": snapshots,
        "goals": goals,
    }
