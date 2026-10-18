"""
Read selectors for Performance Analytics (F-10).
Optimized queries over fact tables with in-memory mathematical models and 304 ETag generation.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Max, Sum
from django.utils import timezone

from .domain.diagnosis import diagnose_time_vs_score
from .domain.limits import (
    MIN_ANSWERS_TOPIC,
)
from .domain.maths import (
    beta_shrinkage,
    wilson_score_interval,
)
from .domain.readiness import ReadinessResult, compute_readiness
from .integrations import coverage as coverage_adapter
from .integrations import syllabus as syllabus_adapter
from .integrations import tracking as tracking_adapter
from .models import (
    ChapterFact,
    MistakeTag,
    TopicFact,
    UserState,
)


def resolve_date_range(range_key: str, tz_name: str = "Asia/Kolkata") -> tuple[date, date]:
    """Resolves date filter to (start_date, end_date) using local calendar."""
    today = timezone.localdate()
    if range_key == "7d":
        return today - timedelta(days=6), today
    elif range_key == "90d":
        return today - timedelta(days=89), today
    elif range_key == "all":
        return date(2020, 1, 1), today
    # default 30d
    return today - timedelta(days=29), today


def get_data_stamp(user_id: uuid.UUID) -> str:
    """Generates an ETag string for HTTP 304 Not Modified validation."""
    state = UserState.objects.filter(user_id=user_id).first()
    version = state.facts_version if state else 0
    today = timezone.localdate().isoformat()
    raw = f"{user_id}:{version}:{today}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def get_overview(user_id: uuid.UUID, range_key: str = "30d") -> dict[str, Any]:
    """High-level KPI overview across practice, time, and coverage."""
    start_date, end_date = resolve_date_range(range_key)
    today = timezone.localdate()

    facts = ChapterFact.objects.filter(
        user_id=user_id,
        local_date__gte=start_date,
        local_date__lte=end_date,
    )

    agg = facts.aggregate(
        total_ans=Sum("answered"),
        total_cor=Sum("correct"),
        total_inc=Sum("incorrect"),
        total_par=Sum("partial"),
        total_credit=Sum("credit_sum"),
        distinct_days=Count("local_date", distinct=True),
    )

    total_answered = agg["total_ans"] or 0
    total_correct = agg["total_cor"] or 0
    distinct_days = agg["distinct_days"] or 0
    credit_sum = agg["total_credit"] or Decimal("0.000")

    overall_accuracy = (
        round(float(credit_sum) / float(total_answered), 3) if total_answered > 0 else 0.0
    )
    center, lower, upper = wilson_score_interval(float(credit_sum), total_answered)

    # Today's activity
    today_facts = ChapterFact.objects.filter(user_id=user_id, local_date=today).aggregate(
        ans=Sum("answered"),
        cor=Sum("correct"),
        credit=Sum("credit_sum"),
    )
    today_ans = today_facts["ans"] or 0
    today_credit = today_facts["credit"] or Decimal("0.000")
    today_accuracy = (
        round(float(today_credit) / float(today_ans), 3) if today_ans > 0 else None
    )

    # Study time from tracking
    ch_seconds = tracking_adapter.get_seconds_by_chapter(user_id, start_date, end_date)
    total_seconds = sum(ch_seconds.values())

    # Subject breakdown
    subj_facts = facts.values("subject_key").annotate(
        ans=Sum("answered"),
        cor=Sum("correct"),
        credit=Sum("credit_sum"),
    )

    cov_fractions = coverage_adapter.get_subject_coverage_fractions(user_id)

    subjects_summary = []
    for sf in subj_facts:
        skey = sf["subject_key"]
        s_ans = sf["ans"] or 0
        s_credit = sf["credit"] or Decimal("0.000")
        s_acc = round(float(s_credit) / float(s_ans), 3) if s_ans > 0 else 0.0
        s_info = syllabus_adapter.get_subject_by_key_or_id(skey)
        name = s_info.get("name", skey.replace("-", " ").title()) if s_info else skey
        sid = s_info.get("id") if s_info else None
        cov_pct = round(cov_fractions.get(sid, 0.0) * 100.0, 1) if sid else 0.0

        subjects_summary.append({
            "subject_key": skey,
            "subject_name": name,
            "answered": s_ans,
            "correct": sf["cor"] or 0,
            "accuracy": s_acc,
            "coverage_pct": cov_pct,
        })

    subjects_summary.sort(key=lambda x: -x["answered"])

    # User state watermark
    state = UserState.objects.filter(user_id=user_id).first()
    last_fact_at = state.last_fact_at.isoformat() if state and state.last_fact_at else None

    hrs = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    study_hours_formatted = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"
    cov_pct = round((sum(cov_fractions.values()) / max(1, len(cov_fractions))) * 100.0, 1) if cov_fractions else 0.0

    return {
        "range_key": range_key,
        "from_date": start_date.isoformat(),
        "to_date": end_date.isoformat(),
        "total_answered": total_answered,
        "total_correct": total_correct,
        "overall_accuracy": overall_accuracy,
        "overall_accuracy_pct": round(overall_accuracy * 100.0),
        "accuracy_ci": {
            "center": round(center, 3),
            "lower": round(lower, 3),
            "upper": round(upper, 3),
        },
        "study_seconds": total_seconds,
        "study_hours_formatted": study_hours_formatted,
        "coverage_percentage": cov_pct,
        "distinct_study_days": distinct_days,
        "days_active": distinct_days,
        "questions_today": today_ans,
        "accuracy_today": today_accuracy,
        "subjects": subjects_summary,
        "facts_version": state.facts_version if state else 0,
        "last_updated_at": last_fact_at,
        "last_calculated_at": last_fact_at or timezone.now().isoformat(),
    }


def get_performance(
    user_id: uuid.UUID,
    *,
    subject_key: str | None = None,
    range_key: str = "30d",
    group_by: str = "chapter",
) -> list[dict[str, Any]]:
    """Performance explorer grouped by chapter, difficulty, question kind, or source."""
    start_date, end_date = resolve_date_range(range_key)
    qs = ChapterFact.objects.filter(
        user_id=user_id,
        local_date__gte=start_date,
        local_date__lte=end_date,
    )
    if subject_key:
        qs = qs.filter(subject_key=subject_key)

    if group_by == "difficulty":
        rows = qs.values("difficulty").annotate(
            ans=Sum("answered"),
            cor=Sum("correct"),
            credit=Sum("credit_sum"),
        ).order_by("difficulty")
        items = []
        for r in rows:
            ans = r["ans"] or 0
            cor = r["cor"] or 0
            credit = r["credit"] or Decimal("0.000")
            acc = round(float(credit) / float(ans), 3) if ans > 0 else 0.0
            shrunk = beta_shrinkage(float(credit), ans)
            center, lower, upper = wilson_score_interval(float(credit), ans)
            g_key = str(r["difficulty"])
            g_name = f"Level {r['difficulty']}" if r["difficulty"] > 0 else "Unrated"
            items.append({
                "key": g_key,
                "label": g_name,
                "group_key": g_key,
                "group_name": g_name,
                "answered": ans,
                "correct": cor,
                "accuracy": acc,
                "accuracy_pct": round(acc * 100.0, 1),
                "shrunk_accuracy_pct": round(shrunk * 100.0, 1),
                "wilson_low_pct": round(lower * 100.0, 1),
                "wilson_high_pct": round(upper * 100.0, 1),
                "study_seconds": 0,
                "avg_pace_ratio": None,
            })
        return items

    elif group_by == "kind":
        rows = qs.values("kind").annotate(
            ans=Sum("answered"),
            cor=Sum("correct"),
            credit=Sum("credit_sum"),
        ).order_by("-ans")
        items = []
        for r in rows:
            ans = r["ans"] or 0
            cor = r["cor"] or 0
            credit = r["credit"] or Decimal("0.000")
            acc = round(float(credit) / float(ans), 3) if ans > 0 else 0.0
            shrunk = beta_shrinkage(float(credit), ans)
            center, lower, upper = wilson_score_interval(float(credit), ans)
            g_key = r["kind"]
            g_name = r["kind"].replace("_", " ").title()
            items.append({
                "key": g_key,
                "label": g_name,
                "group_key": g_key,
                "group_name": g_name,
                "answered": ans,
                "correct": cor,
                "accuracy": acc,
                "accuracy_pct": round(acc * 100.0, 1),
                "shrunk_accuracy_pct": round(shrunk * 100.0, 1),
                "wilson_low_pct": round(lower * 100.0, 1),
                "wilson_high_pct": round(upper * 100.0, 1),
                "study_seconds": 0,
                "avg_pace_ratio": None,
            })
        return items

    elif group_by == "source":
        rows = qs.values("source_kind").annotate(
            ans=Sum("answered"),
            cor=Sum("correct"),
            credit=Sum("credit_sum"),
        ).order_by("-ans")
        items = []
        for r in rows:
            ans = r["ans"] or 0
            cor = r["cor"] or 0
            credit = r["credit"] or Decimal("0.000")
            acc = round(float(credit) / float(ans), 3) if ans > 0 else 0.0
            shrunk = beta_shrinkage(float(credit), ans)
            center, lower, upper = wilson_score_interval(float(credit), ans)
            g_key = r["source_kind"]
            g_name = r["source_kind"].replace("_", " ").title()
            items.append({
                "key": g_key,
                "label": g_name,
                "group_key": g_key,
                "group_name": g_name,
                "answered": ans,
                "correct": cor,
                "accuracy": acc,
                "accuracy_pct": round(acc * 100.0, 1),
                "shrunk_accuracy_pct": round(shrunk * 100.0, 1),
                "wilson_low_pct": round(lower * 100.0, 1),
                "wilson_high_pct": round(upper * 100.0, 1),
                "study_seconds": 0,
                "avg_pace_ratio": None,
            })
        return items

    # Default group by chapter
    rows = qs.values("chapter_id", "chapter_key", "subject_key").annotate(
        ans=Sum("answered"),
        cor=Sum("correct"),
        credit=Sum("credit_sum"),
        time_ms=Sum("time_ms_sum"),
        time_n=Sum("time_n"),
    ).order_by("-ans")

    ch_seconds = tracking_adapter.get_seconds_by_chapter(user_id, start_date, end_date)

    result = []
    for r in rows:
        cid = r["chapter_id"]
        ans = r["ans"] or 0
        cor = r["cor"] or 0
        credit = r["credit"] or Decimal("0.000")
        acc = round(float(credit) / float(ans), 3) if ans > 0 else 0.0
        shrunk = beta_shrinkage(float(credit), ans)
        center, lower, upper = wilson_score_interval(float(credit), ans)

        # Chapter name
        ch_info = syllabus_adapter.get_chapter_by_id(cid) or syllabus_adapter.get_subject_by_key_or_id(cid)
        ch_name = ch_info.get("name") if ch_info else r["chapter_key"] or "Chapter"
        study_sec = ch_seconds.get(cid, 0)

        # Diagnostic classification
        diag = diagnose_time_vs_score(
            study_seconds=study_sec,
            accuracy=acc,
            time_threshold_seconds=1800,  # 30 mins
            accuracy_threshold=0.70,
            answered_count=ans,
        )

        time_ms = r.get("time_ms") or 0
        time_n = r.get("time_n") or 0
        avg_pace = round((time_ms / (time_n * 1000)) / 60.0, 2) if time_n > 0 else None

        result.append({
            "key": str(cid),
            "label": ch_name,
            "chapter_id": str(cid),
            "chapter_key": r["chapter_key"],
            "chapter_name": ch_name,
            "subject_key": r["subject_key"],
            "answered": ans,
            "correct": cor,
            "accuracy": acc,
            "accuracy_pct": round(acc * 100.0, 1),
            "shrunk_accuracy_pct": round(shrunk * 100.0, 1),
            "wilson_low_pct": round(lower * 100.0, 1),
            "wilson_high_pct": round(upper * 100.0, 1),
            "confidence_lower": round(lower, 3),
            "confidence_upper": round(upper, 3),
            "study_seconds": study_sec,
            "avg_pace_ratio": avg_pace,
            "diagnosis": diag.value,
        })

    return result


def get_trends(
    user_id: uuid.UUID,
    *,
    range_key: str = "30d",
    interval: str = "day",
) -> list[dict[str, Any]]:
    """Calculates temporal trends of question volume, accuracy, and study time."""
    start_date, end_date = resolve_date_range(range_key)

    facts = (
        ChapterFact.objects.filter(
            user_id=user_id,
            local_date__gte=start_date,
            local_date__lte=end_date,
        )
        .values("local_date")
        .annotate(
            ans=Sum("answered"),
            cor=Sum("correct"),
            credit=Sum("credit_sum"),
            time_ms=Sum("time_ms_sum"),
        )
        .order_by("local_date")
    )

    facts_by_date = {f["local_date"]: f for f in facts}

    trends = []
    curr = start_date
    history_acc = []
    while curr <= end_date:
        f = facts_by_date.get(curr)
        ans = f["ans"] if f else 0
        cor = f["cor"] if f else 0
        credit = f["credit"] if f else Decimal("0.000")
        acc = round(float(credit) / float(ans), 3) if ans > 0 else None
        acc_pct = round(acc * 100.0, 1) if acc is not None else 0.0

        if acc is not None:
            history_acc.append(acc_pct)
        recent_acc = history_acc[-7:] if history_acc else [0.0]
        moving_avg = round(sum(recent_acc) / len(recent_acc), 1)

        trends.append({
            "date": curr.isoformat(),
            "answered": ans,
            "correct": cor,
            "accuracy": acc,
            "accuracy_pct": acc_pct,
            "moving_avg_accuracy_pct": moving_avg,
        })
        curr += timedelta(days=1)

    return trends


def get_weak_topics(
    user_id: uuid.UUID,
    *,
    subject_key: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Ranks struggling topics using empirical Bayes Beta shrinkage.
    Pulls topics with low mastery to the top for the 'Fix this' action.
    """
    start_date, end_date = resolve_date_range("90d")  # 90-day lookback for topics
    qs = TopicFact.objects.filter(
        user_id=user_id,
        local_date__gte=start_date,
        local_date__lte=end_date,
    )
    if subject_key:
        qs = qs.filter(subject_key=subject_key)

    topic_rows = (
        qs.values("topic_id", "chapter_id", "subject_key")
        .annotate(
            ans=Sum("answered"),
            cor=Sum("correct"),
            credit=Sum("credit_sum"),
        )
        .filter(ans__gte=MIN_ANSWERS_TOPIC)
    )

    ranked_topics = []
    for r in topic_rows:
        ans = r["ans"]
        credit = float(r["credit"])
        shrunk_mu = beta_shrinkage(credit, ans, prior_mean=0.50, prior_strength=2.0)
        topic_name = syllabus_adapter.get_topic_name(r["topic_id"])
        ch_info = syllabus_adapter.get_chapter_by_id(r["chapter_id"]) or syllabus_adapter.get_subject_by_key_or_id(r["chapter_id"])
        ch_name = ch_info.get("name") if ch_info else "Chapter"
        acc_pct = round((credit / ans) * 100.0, 1) if ans > 0 else 0.0
        shrunk_pct = round(shrunk_mu * 100.0, 1)
        mistakes_cnt = MistakeTag.objects.filter(user_id=user_id, topic_id=r["topic_id"]).count()

        ranked_topics.append({
            "topic_id": str(r["topic_id"]),
            "topic_name": topic_name,
            "chapter_id": str(r["chapter_id"]),
            "chapter_name": ch_name,
            "subject_key": r["subject_key"],
            "answered": ans,
            "correct": r["cor"],
            "accuracy": round(credit / ans, 3),
            "accuracy_pct": acc_pct,
            "shrunk_accuracy_pct": shrunk_pct,
            "mistakes_count": mistakes_cnt,
            "mastery_score": shrunk_pct,
            "fix_ready": True,
        })

    # Sort ascending by mastery_score so weakest topics appear first
    ranked_topics.sort(key=lambda x: (x["mastery_score"], -x["answered"]))
    return ranked_topics[:limit]


def get_speed(
    user_id: uuid.UUID,
    *,
    subject_key: str | None = None,
    range_key: str = "30d",
) -> dict[str, Any]:
    """Analyzes speed and pace compliance across questions."""
    start_date, end_date = resolve_date_range(range_key)
    qs = ChapterFact.objects.filter(
        user_id=user_id,
        local_date__gte=start_date,
        local_date__lte=end_date,
    )
    if subject_key:
        qs = qs.filter(subject_key=subject_key)

    agg = qs.aggregate(
        total_timed=Sum("time_n"),
        total_time_ms=Sum("time_ms_sum"),
        total_sugg=Sum("sugg_n"),
        total_sugg_ms=Sum("sugg_ms_sum"),
    )

    total_timed = agg["total_timed"] or 0
    total_time_ms = agg["total_time_ms"] or 0
    total_sugg_ms = agg["total_sugg_ms"] or 0

    avg_sec = round(float(total_time_ms) / float(total_timed * 1000), 1) if total_timed > 0 else 0.0
    sugg_sec = round(float(total_sugg_ms) / float(total_timed * 1000), 1) if total_timed > 0 and total_sugg_ms > 0 else None
    pace_ratio = round(avg_sec / sugg_sec, 2) if sugg_sec and sugg_sec > 0 else 1.0

    fast_and_wrong = 0
    slow_and_right = 0
    on_target = 0
    slow_and_wrong = 0

    for row in qs:
        t_n = row.time_n
        s_n = row.sugg_n
        if t_n > 0 and s_n > 0 and row.sugg_ms_sum > 0:
            avg_t = float(row.time_ms_sum) / float(t_n)
            avg_s = float(row.sugg_ms_sum) / float(s_n)
            ratio = avg_t / avg_s if avg_s > 0 else 1.0
            if ratio < 0.85:
                fast_and_wrong += row.incorrect
                on_target += row.correct
            elif ratio > 1.15:
                slow_and_right += row.correct
                slow_and_wrong += row.incorrect
            else:
                on_target += row.correct
                slow_and_wrong += row.incorrect

    quad_total = fast_and_wrong + slow_and_right + on_target + slow_and_wrong
    if quad_total == 0 and total_timed > 0:
        on_target = total_timed
        quad_total = total_timed

    def _pct(c: int) -> int:
        return round(float(c) / float(quad_total) * 100.0) if quad_total > 0 else 0

    return {
        "timed_answers_count": total_timed,
        "avg_time_per_question_seconds": avg_sec,
        "suggested_time_seconds": sugg_sec,
        "pace_ratio": pace_ratio,
        "overall_pace_ratio": pace_ratio if total_timed > 0 else None,
        "status": "on_target" if 0.85 <= pace_ratio <= 1.15 else ("fast" if pace_ratio < 0.85 else "slow"),
        "quadrants": {
            "on_target": {"count": on_target, "pct": _pct(on_target)},
            "slow_and_right": {"count": slow_and_right, "pct": _pct(slow_and_right)},
            "fast_and_wrong": {"count": fast_and_wrong, "pct": _pct(fast_and_wrong)},
            "slow_and_wrong": {"count": slow_and_wrong, "pct": _pct(slow_and_wrong)},
        },
    }


def get_mistakes(
    user_id: uuid.UUID,
    *,
    subject_key: str | None = None,
    range_key: str = "30d",
) -> list[dict[str, Any]]:
    """Mistake reason breakdown."""
    start_date, end_date = resolve_date_range(range_key)
    qs = MistakeTag.objects.filter(
        user_id=user_id,
        local_date__gte=start_date,
        local_date__lte=end_date,
    )
    if subject_key:
        qs = qs.filter(subject_key=subject_key)

    reasons = qs.values("reason").annotate(count=Count("id")).order_by("-count")
    total_tagged = sum(r["count"] for r in reasons)

    return [
        {
            "reason": r["reason"],
            "label": r["reason"].replace("_", " ").title(),
            "reason_label": r["reason"].replace("_", " ").title(),
            "count": r["count"],
            "percentage": round(float(r["count"]) / float(total_tagged) * 100.0, 1) if total_tagged > 0 else 0.0,
            "share_pct": round(float(r["count"]) / float(total_tagged) * 100.0, 1) if total_tagged > 0 else 0.0,
        }
        for r in reasons
    ]


def get_readiness_data(
    user_id: uuid.UUID,
    *,
    subject_key: str | None = None,
) -> ReadinessResult:
    """Computes real-time subject or overall readiness."""
    start_date = timezone.localdate() - timedelta(days=180)
    qs = ChapterFact.objects.filter(user_id=user_id, local_date__gte=start_date)
    if subject_key:
        qs = qs.filter(subject_key=subject_key)

    ch_summary = (
        qs.values("chapter_id", "chapter_key")
        .annotate(
            ans=Sum("answered"),
            credit=Sum("credit_sum"),
            latest_date=Max("local_date"),
        )
    )

    total_graded = sum(c["ans"] for c in ch_summary)
    distinct_days = qs.values("local_date").distinct().count()
    latest_local_date = qs.aggregate(m=Max("local_date"))["m"]

    today = timezone.localdate()
    days_since_last = (today - latest_local_date).days if latest_local_date else 999

    # Build chapter evidence
    chapter_evidence = []
    for c in ch_summary:
        cid = c["chapter_id"]
        c_ans = c["ans"]
        c_credit = float(c["credit"] or 0)
        c_date = c["latest_date"]
        days_ago = (today - c_date).days if c_date else 0
        ch_info = syllabus_adapter.get_chapter_by_id(cid)
        ch_name = ch_info.get("name") if ch_info else c["chapter_key"] or "Chapter"
        weight = ch_info.get("weight", 5.0) if ch_info else 5.0

        chapter_evidence.append({
            "chapter_id": cid,
            "chapter_name": ch_name,
            "answered": c_ans,
            "credit_sum": c_credit,
            "days_ago": days_ago,
            "weight": weight,
        })

    # Coverage fraction
    cov_fractions = coverage_adapter.get_subject_coverage_fractions(user_id)
    cov_val = None
    if subject_key:
        subj_info = syllabus_adapter.get_subject_by_key_or_id(subject_key)
        if subj_info and subj_info.get("id"):
            cov_val = cov_fractions.get(subj_info["id"], 0.0)
    else:
        cov_val = sum(cov_fractions.values()) / max(1, len(cov_fractions)) if cov_fractions else 0.0

    return compute_readiness(
        total_graded=total_graded,
        distinct_days=distinct_days,
        days_since_last_answer=days_since_last,
        chapter_evidence=chapter_evidence,
        total_chapters_count=max(len(chapter_evidence), 10),
        coverage_fraction=cov_val,
        retention_fraction=0.75,
        speed_fraction=0.85,
    )
