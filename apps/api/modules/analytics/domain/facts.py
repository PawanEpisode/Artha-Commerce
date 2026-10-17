"""
Pure fact builder for Performance Analytics (F-10 ERD 3.4).
Given a session and its answers + question labels, builds:
1. Chapter facts (analytics_chapterfact)
2. Topic facts (analytics_topicfact)
3. Mistake tags (analytics_mistaketag)
4. Canonical content hash for zero-write idempotency
"""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from .limits import MAX_ANSWER_TIME_MS, MIN_ANSWER_TIME_MS

ZERO_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def canonical_json(obj: Any) -> str:
    """Produces sorted, deterministic JSON string for hashing."""
    return json.dumps(obj, sort_keys=True, default=str)


def compute_content_hash(rows: dict[str, Any]) -> str:
    """Computes SHA-256 hex digest of canonical JSON facts."""
    return hashlib.sha256(canonical_json(rows).encode("utf-8")).hexdigest()


def build_facts(
    session: dict[str, Any],
    answers: list[dict[str, Any]],
    labels_by_version: dict[uuid.UUID, dict[str, Any]],
) -> dict[str, Any]:
    """
    Pure transformation from raw practice answers to aggregated fact dictionaries.

    Returns:
    {
        "chapter_facts": list[dict],
        "topic_facts": list[dict],
        "mistake_tags": list[dict],
        "content_hash": str,
    }
    """
    session_id = session["id"]
    user_id = session["user_id"]
    mode = session.get("mode", "untimed")
    local_date = session["local_date"]

    chapter_acc: dict[tuple, dict[str, Any]] = {}
    topic_acc: dict[tuple, dict[str, Any]] = {}
    mistake_tags: list[dict[str, Any]] = []

    for ans in answers:
        version_id = ans.get("question_version_id")
        labels = labels_by_version.get(version_id, {})

        chapter_id = ans.get("chapter_id") or labels.get("primary_chapter_id") or ZERO_UUID
        topic_id = labels.get("primary_topic_id")
        subject_key = labels.get("subject_key") or ans.get("subject_key") or "unmapped"
        chapter_key = labels.get("chapter_key") or ""

        kind = ans.get("kind", "mcq_single")
        difficulty = int(labels.get("difficulty") or 0)
        source_kind = labels.get("source_kind") or "platform"
        is_repeat = bool(ans.get("is_repeat", False))

        result = ans.get("result")
        status = ans.get("status")
        grading_source = ans.get("grading_source", "auto")
        time_spent_ms = int(ans.get("time_spent_ms") or 0)
        suggested_sec = labels.get("suggested_seconds")

        marks_awarded = Decimal(str(ans.get("marks_awarded") or "0.00"))
        marks_max = Decimal(str(ans.get("marks_max") or "1.00"))

        # Scoring & credit
        is_graded = result in ("correct", "incorrect", "partial")
        is_correct = result == "correct"
        is_incorrect = result == "incorrect"
        is_partial = result == "partial"
        is_skipped = status == "skipped" or result == "skipped"
        is_pending = status == "pending_evaluation" or result == "pending"

        credit = Decimal("0.000")
        if is_correct:
            credit = Decimal("1.000")
        elif is_partial and marks_max > Decimal("0"):
            credit = min(Decimal("1.000"), max(Decimal("0.000"), marks_awarded / marks_max))

        is_est = is_graded and grading_source in ("self", "ai")

        # Time tracking validity
        is_timed_valid = is_graded and (MIN_ANSWER_TIME_MS <= time_spent_ms <= MAX_ANSWER_TIME_MS)

        # 1. Accumulate Chapter Facts
        cf_key = (session_id, chapter_id, kind, difficulty, source_kind, is_repeat, local_date)
        if cf_key not in chapter_acc:
            chapter_acc[cf_key] = {
                "session_id": session_id,
                "chapter_id": chapter_id,
                "kind": kind,
                "difficulty": difficulty,
                "source_kind": source_kind,
                "is_repeat": is_repeat,
                "local_date": local_date,
                "user_id": user_id,
                "subject_key": subject_key,
                "chapter_key": chapter_key,
                "mode": mode,
                "answered": 0,
                "correct": 0,
                "incorrect": 0,
                "partial": 0,
                "skipped": 0,
                "credit_sum": Decimal("0.000"),
                "est_answered": 0,
                "est_credit_sum": Decimal("0.000"),
                "pending": 0,
                "time_n": 0,
                "time_ms_sum": 0,
                "sugg_n": 0,
                "sugg_ms_sum": 0,
                "nosugg_marks_sum": Decimal("0.00"),
                "marks_awarded_sum": Decimal("0.00"),
                "marks_max_sum": Decimal("0.00"),
            }

        cf = chapter_acc[cf_key]
        if is_graded:
            cf["answered"] += 1
            cf["credit_sum"] += credit
            cf["marks_awarded_sum"] += marks_awarded
            cf["marks_max_sum"] += marks_max
            if is_correct:
                cf["correct"] += 1
            elif is_incorrect:
                cf["incorrect"] += 1
            elif is_partial:
                cf["partial"] += 1

            if is_est:
                cf["est_answered"] += 1
                cf["est_credit_sum"] += credit

            if is_timed_valid:
                cf["time_n"] += 1
                cf["time_ms_sum"] += time_spent_ms
                if suggested_sec is not None and suggested_sec > 0:
                    cf["sugg_n"] += 1
                    cf["sugg_ms_sum"] += int(suggested_sec) * 1000
                else:
                    cf["nosugg_marks_sum"] += marks_max

        elif is_skipped:
            cf["skipped"] += 1
        elif is_pending:
            cf["pending"] += 1

        # 2. Accumulate Topic Facts (if primary topic confirmed)
        if topic_id:
            tf_key = (session_id, topic_id, is_repeat, local_date)
            if tf_key not in topic_acc:
                topic_acc[tf_key] = {
                    "session_id": session_id,
                    "topic_id": topic_id,
                    "is_repeat": is_repeat,
                    "local_date": local_date,
                    "user_id": user_id,
                    "chapter_id": chapter_id,
                    "subject_key": subject_key,
                    "mode": mode,
                    "answered": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "partial": 0,
                    "skipped": 0,
                    "credit_sum": Decimal("0.000"),
                    "est_answered": 0,
                    "est_credit_sum": Decimal("0.000"),
                }

            tf = topic_acc[tf_key]
            if is_graded:
                tf["answered"] += 1
                tf["credit_sum"] += credit
                if is_correct:
                    tf["correct"] += 1
                elif is_incorrect:
                    tf["incorrect"] += 1
                elif is_partial:
                    tf["partial"] += 1

                if is_est:
                    tf["est_answered"] += 1
                    tf["est_credit_sum"] += credit
            elif is_skipped:
                tf["skipped"] += 1

        # 3. Mistake Tagging
        mistake_reason = ans.get("mistake_reason")
        if mistake_reason:
            mistake_tags.append(
                {
                    "session_id": session_id,
                    "position": ans["position"],
                    "user_id": user_id,
                    "chapter_id": chapter_id,
                    "subject_key": subject_key,
                    "topic_id": topic_id,
                    "reason": mistake_reason,
                    "local_date": local_date,
                    "tagged_at": ans.get("checked_at") or ans.get("updated_at") or session.get("submitted_at"),
                }
            )

    chapter_facts = list(chapter_acc.values())
    topic_facts = list(topic_acc.values())

    payload_to_hash = {
        "chapter_facts": sorted(
            chapter_facts,
            key=lambda x: (
                str(x["chapter_id"]),
                x["kind"],
                x["difficulty"],
                x["source_kind"],
                x["is_repeat"],
            ),
        ),
        "topic_facts": sorted(
            topic_facts,
            key=lambda x: (str(x["topic_id"]), x["is_repeat"]),
        ),
        "mistake_tags": sorted(mistake_tags, key=lambda x: x["position"]),
    }

    content_hash = compute_content_hash(payload_to_hash)

    return {
        "chapter_facts": chapter_facts,
        "topic_facts": topic_facts,
        "mistake_tags": mistake_tags,
        "content_hash": content_hash,
    }
