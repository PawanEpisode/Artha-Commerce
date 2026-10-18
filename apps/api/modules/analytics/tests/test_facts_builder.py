"""
Tests for pure fact builder and content hash calculation.
"""

import uuid
from datetime import date
from decimal import Decimal

from modules.analytics.domain.facts import build_facts


def test_build_facts_aggregation_and_hash():
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    version_id = uuid.uuid4()

    session = {
        "id": session_id,
        "user_id": user_id,
        "mode": "untimed",
        "local_date": date(2026, 10, 15),
    }

    answers = [
        # 1: Correct MCQ with valid time
        {
            "position": 1,
            "question_version_id": version_id,
            "chapter_id": chapter_id,
            "kind": "mcq_single",
            "result": "correct",
            "status": "graded",
            "grading_source": "auto",
            "marks_awarded": Decimal("1.00"),
            "marks_max": Decimal("1.00"),
            "time_spent_ms": 15000,
            "mistake_reason": None,
        },
        # 2: Incorrect MCQ with mistake reason
        {
            "position": 2,
            "question_version_id": version_id,
            "chapter_id": chapter_id,
            "kind": "mcq_single",
            "result": "incorrect",
            "status": "graded",
            "grading_source": "auto",
            "marks_awarded": Decimal("0.00"),
            "marks_max": Decimal("1.00"),
            "time_spent_ms": 25000,
            "mistake_reason": "silly",
        },
    ]

    labels = {
        version_id: {
            "difficulty": 2,
            "source_kind": "platform",
            "suggested_seconds": 60,
            "primary_topic_id": topic_id,
            "subject_key": "taxation",
            "chapter_key": "salaries",
        }
    }

    res = build_facts(session, answers, labels)

    assert len(res["chapter_facts"]) == 1
    cf = res["chapter_facts"][0]
    assert cf["answered"] == 2
    assert cf["correct"] == 1
    assert cf["incorrect"] == 1
    assert cf["time_n"] == 2
    assert cf["time_ms_sum"] == 40000

    assert len(res["topic_facts"]) == 1
    tf = res["topic_facts"][0]
    assert tf["topic_id"] == topic_id
    assert tf["answered"] == 2

    assert len(res["mistake_tags"]) == 1
    mt = res["mistake_tags"][0]
    assert mt["reason"] == "silly"
    assert mt["position"] == 2

    assert isinstance(res["content_hash"], str)
    assert len(res["content_hash"]) == 64

    # Idempotency check: running with exact same inputs yields identical hash
    res2 = build_facts(session, answers, labels)
    assert res2["content_hash"] == res["content_hash"]
