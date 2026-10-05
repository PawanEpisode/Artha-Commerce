"""
Reads for study time and reports. Every function takes `user_id` and filters on it; another student's id is never found.
Reports read the derived roll-ups, not raw sessions, so they stay fast with years of data. Subjects and chapters are
grouped by their stable `key` (with course and level), so a syllabus scheme change never splits a subject's history.
"""

from __future__ import annotations

import base64
import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.db.models import Count, Max, QuerySet, Sum

from modules.coverage import selectors as coverage
from modules.syllabus import selectors as syllabus
from modules.syllabus.models import Chapter, Subject

from .domain import durations, reports
from .domain.reports import RangeError
from .models import (
    ActiveStopwatch,
    DailyRollup,
    Goal,
    HourBucket,
    SessionAudit,
    StudySession,
    TrackerSettings,
)

DEFAULT_DAILY_GOAL_MINUTES = 120  # F-01.1 default (its Q4); used until the student sets one
EXPORT_ROW_LIMIT = 10_000
UNTAGGED = "untagged"


# --- Settings, stopwatch ------------------------------------------------------------------------------------------
def get_settings(user_id) -> TrackerSettings | None:
    return TrackerSettings.objects.filter(pk=user_id).first()


def settings_or_default(user_id) -> TrackerSettings:
    return get_settings(user_id) or TrackerSettings(user_id=user_id)


def get_stopwatch(user_id) -> ActiveStopwatch | None:
    return ActiveStopwatch.objects.filter(pk=user_id).first()


def stopwatch_dict(sw: ActiveStopwatch, now: datetime, settings: TrackerSettings) -> dict:
    return {
        "status": "paused" if sw.paused_at else "running",
        "started_at": sw.started_at,
        "paused_at": sw.paused_at,
        "paused_total_seconds": sw.paused_total_seconds,
        "pause_count": sw.pause_count,
        "elapsed_seconds": durations.elapsed_seconds(sw.started_at, now, sw.paused_at, sw.paused_total_seconds),
        "last_seen_at": sw.last_seen_at,
        "last_active_at": sw.last_active_at,
        "idle_pending": sw.idle_pending,
        "idle_prompted_at": sw.idle_prompted_at,
        "idle_due": bool(
            not sw.paused_at
            and not sw.idle_pending
            and durations.idle_due(now, sw.last_active_at, settings.idle_minutes)
        ),
        "subject_id": sw.subject_id,
        "chapter_id": sw.chapter_id,
        "activity_type": sw.activity_type,
        "client_id": sw.client_id,
        "version": sw.version,
    }


# --- Sessions ------------------------------------------------------------------------------------------------------
def get_session(user_id, session_id) -> StudySession | None:
    return StudySession.objects.select_related("subject", "chapter").filter(user_id=user_id, pk=session_id).first()


def session_by_client_id(user_id, client_id) -> StudySession | None:
    return StudySession.objects.filter(user_id=user_id, client_id=client_id).first() if client_id else None


def get_audit(user_id, token) -> SessionAudit | None:
    return SessionAudit.objects.filter(user_id=user_id, pk=token).first()


def _filtered(
    user_id, *, start=None, end=None, subject_id=None, chapter_id=None, source=None
) -> QuerySet[StudySession]:
    qs = StudySession.objects.filter(user_id=user_id)
    if start:
        qs = qs.filter(study_date__gte=start)
    if end:
        qs = qs.filter(study_date__lte=end)
    if subject_id:
        qs = qs.filter(subject_id=subject_id)
    if chapter_id:
        qs = qs.filter(chapter_id=chapter_id)
    if source:
        qs = qs.filter(source=source)
    return qs


def _encode_cursor(session: StudySession) -> str:
    raw = f"{session.started_at.isoformat()}|{session.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        started, pk = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(started), pk
    except (ValueError, UnicodeError):
        raise RangeError("bad_cursor", "That page cursor is not valid.") from None


def list_sessions(
    user_id, *, cursor: str | None = None, limit: int = 50, **filters
) -> tuple[list[StudySession], str | None]:
    """Newest first, keyset paginated. Returns the rows and the cursor of the next page (None at the end)."""
    qs = _filtered(user_id, **filters).select_related("subject", "chapter").order_by("-started_at", "-id")
    if cursor:
        started, pk = _decode_cursor(cursor)
        from django.db.models import Q

        qs = qs.filter(Q(started_at__lt=started) | Q(started_at=started, id__lt=pk))
    rows = list(qs[: limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, (_encode_cursor(rows[-1]) if more and rows else None)


def export_rows(user_id, **filters) -> QuerySet[StudySession]:
    return _filtered(user_id, **filters).select_related("subject", "chapter").order_by("started_at")[:EXPORT_ROW_LIMIT]


# --- Goals ---------------------------------------------------------------------------------------------------------
def goals_in_force(user_id, day: date) -> QuerySet[Goal]:
    return (
        Goal.objects.filter(user_id=user_id, effective_from__lte=day)
        .filter(models_q_open_or_after(day))
        .select_related("subject")
        .order_by("period", "subject_key")
    )


def models_q_open_or_after(day: date):
    from django.db.models import Q

    return Q(effective_to__isnull=True) | Q(effective_to__gte=day)


def daily_goal_minutes_on(goals: list[Goal], day: date) -> int:
    for g in sorted(goals, key=lambda g: g.effective_from, reverse=True):
        if g.effective_from <= day and (g.effective_to is None or g.effective_to >= day):
            return g.target_minutes
    return DEFAULT_DAILY_GOAL_MINUTES


# --- Roll-up helpers -----------------------------------------------------------------------------------------------
def _rollups(user_id, start: date, end: date, verified_only: bool = False) -> QuerySet[DailyRollup]:
    qs = DailyRollup.objects.filter(user_id=user_id, study_date__gte=start, study_date__lte=end)
    return qs.filter(verified=True) if verified_only else qs


def day_totals(user_id, start: date, end: date, verified_only: bool = False) -> dict[date, int]:
    rows = _rollups(user_id, start, end, verified_only).values("study_date").annotate(total=Sum("seconds"))
    return {r["study_date"]: r["total"] for r in rows if r["total"]}


def subject_meta(subject_ids) -> dict:
    """id -> stable key, name and where the subject sits (course, level, group). Same key across schemes."""
    subjects = Subject.objects.filter(pk__in=[i for i in subject_ids if i]).select_related(
        "scheme__level__course", "group"
    )
    out = {}
    for s in subjects:
        level, course = s.scheme.level, s.scheme.level.course
        out[s.id] = {
            "key": f"{course.code}:{level.code}:{s.key}",
            "name": s.name,
            "subject_key": s.key,
            "level_key": f"{course.code}:{level.code}",
            "level_name": f"{course.code.upper()} {level.name}",
            "group_key": f"{course.code}:{level.code}:{s.group.key}"
            if s.group_id
            else f"{course.code}:{level.code}:none",
            "group_name": s.group.name if s.group_id else "No group",
            "scheme_current": s.scheme.status == "published",
        }
    return out


# --- Reports ---------------------------------------------------------------------------------------------------------
def summary(user_id, start: date, end: date, *, compare: bool = False, verified_only: bool = False) -> dict:
    reports.validate_range(start, end, "week")

    def block(a: date, b: date) -> dict:
        agg = _rollups(user_id, a, b, verified_only).aggregate(total=Sum("seconds"), sessions=Sum("sessions"))
        totals = day_totals(user_id, a, b, verified_only)
        total = agg["total"] or 0
        best_day = max(totals.items(), key=lambda kv: kv[1], default=None)
        sessions = StudySession.objects.filter(user_id=user_id, study_date__gte=a, study_date__lte=b)
        if verified_only:
            sessions = sessions.filter(presence_verified=True)
        longest = sessions.aggregate(m=Max("focus_seconds"))["m"] or 0
        days = len(totals)
        return {
            "from": a,
            "to": b,
            "total_seconds": total,
            "days_studied": days,
            "average_seconds_per_studied_day": round(total / days) if days else 0,
            "longest_day": {"date": best_day[0], "seconds": best_day[1]} if best_day else None,
            "sessions": agg["sessions"] or 0,
            "longest_session_seconds": longest,
        }

    out = block(start, end)
    if compare:
        prev_start, prev_end = reports.previous_range(start, end)
        previous = block(prev_start, prev_end)
        out["previous"] = previous
        out["change"] = reports.change(out["total_seconds"], previous["total_seconds"])
    return out


def _key_of(by: str, row: dict, meta: dict, chapters: dict):
    """Return (key, name) of a roll-up row under a `by` dimension."""
    if by == "activity":
        return row["activity_type"], row["activity_type"].replace("_", " ").title()
    if by == "source":
        return row["source"], row["source"].title()
    m = meta.get(row["subject_id"])
    if by == "subject":
        return (m["key"], m["name"]) if m else (UNTAGGED, "Untagged")
    if by == "group":
        return (m["group_key"], m["group_name"]) if m else (UNTAGGED, "Untagged")
    if by == "level":
        return (m["level_key"], m["level_name"]) if m else (UNTAGGED, "Untagged")
    if by == "chapter":
        c = chapters.get(row["chapter_id"])
        return (f"{m['key']}:{c['key']}", c["name"]) if (m and c) else (UNTAGGED, "Untagged")
    return "total", "Total"


def _chapter_meta(chapter_ids) -> dict:
    return {
        c.id: {"key": c.key, "name": c.name, "subject_id": c.subject_id}
        for c in Chapter.objects.filter(pk__in=[i for i in chapter_ids if i])
    }


def _grouped(user_id, start, end, verified_only):
    return list(
        _rollups(user_id, start, end, verified_only)
        .values("study_date", "subject_id", "chapter_id", "activity_type", "source")
        .annotate(total=Sum("seconds"), n=Sum("sessions"))
    )


def series(user_id, start: date, end: date, *, group: str, by: str = "total", verified_only: bool = False) -> dict:
    reports.validate_range(start, end, group)
    week_start = settings_or_default(user_id).week_start
    rows = _grouped(user_id, start, end, verified_only)
    meta = subject_meta({r["subject_id"] for r in rows})
    chapters = _chapter_meta({r["chapter_id"] for r in rows}) if by == "chapter" else {}
    buckets = reports.buckets(start, end, group, week_start)
    index = {b.start: i for i, b in enumerate(buckets)}
    data = [{"start": b.start, "end": b.end, "seconds": 0, "parts": {}} for b in buckets]
    names: dict[str, str] = {}
    for r in rows:
        i = index[reports.bucket_start(r["study_date"], group, week_start)]
        data[i]["seconds"] += r["total"]
        if by != "total":
            key, name = _key_of(by, r, meta, chapters)
            names[key] = name
            data[i]["parts"][key] = data[i]["parts"].get(key, 0) + r["total"]
    return {
        "from": start,
        "to": end,
        "group": group,
        "by": by,
        "week_start": week_start,
        "tz": settings_or_default(user_id).tz,
        "legend": [{"key": k, "name": n} for k, n in sorted(names.items(), key=lambda kv: kv[1])],
        "buckets": data,
    }


def breakdown(user_id, start: date, end: date, *, by: str, parent_id=None, verified_only: bool = False) -> dict:
    reports.validate_range(start, end, "week")
    if by not in {"level", "group", "subject", "chapter", "activity", "source"}:
        raise RangeError("bad_by", "Split by level, group, subject, chapter, activity or source.")
    rows = _grouped(user_id, start, end, verified_only)
    meta = subject_meta({r["subject_id"] for r in rows})
    chapters = _chapter_meta({r["chapter_id"] for r in rows})
    if parent_id:
        # Narrow to one parent: a subject id (for chapters), a group key or a level key (for the level below).
        parent_meta = subject_meta([parent_id]).get(parent_id) if not isinstance(parent_id, str) else None
        if parent_meta:
            rows = [r for r in rows if meta.get(r["subject_id"], {}).get("key") == parent_meta["key"]]
        else:
            rows = [
                r
                for r in rows
                if parent_id
                in (meta.get(r["subject_id"], {}).get("group_key"), meta.get(r["subject_id"], {}).get("level_key"))
            ]
    items: dict[str, dict] = {}
    for r in rows:
        key, name = _key_of(by, r, meta, chapters)
        item = items.setdefault(
            key, {"key": key, "name": name, "seconds": 0, "sessions": 0, "subject_id": None, "chapter_id": None}
        )
        item["seconds"] += r["total"]
        item["sessions"] += r["n"] or 0
        if by in {"subject", "chapter"} and r["subject_id"]:
            item["subject_id"] = item["subject_id"] or r["subject_id"]
        if by == "chapter":
            item["chapter_id"] = item["chapter_id"] or r["chapter_id"]
    total = sum(i["seconds"] for i in items.values())
    ordered = sorted(items.values(), key=lambda i: (-i["seconds"], i["name"]))
    for i in ordered:
        i["share_percent"] = round(i["seconds"] * 100 / total, 1) if total else 0
    return {"from": start, "to": end, "by": by, "total_seconds": total, "items": ordered}


def heatmap(user_id, start: date, end: date, *, verified_only: bool = False) -> dict:
    reports.validate_range(start, end, "day")
    totals = day_totals(user_id, start, end, verified_only)
    return {
        "from": start,
        "to": end,
        "days": [{"date": d, "seconds": s, "level": reports.intensity(s)} for d, s in sorted(totals.items())],
    }


def hours(user_id, start: date, end: date) -> dict:
    """Seconds per local hour (approximate for sessions that had pauses) and per weekday. Includes every source."""
    reports.validate_range(start, end, "week")
    per_hour = [0] * 24
    for r in (
        HourBucket.objects.filter(user_id=user_id, study_date__gte=start, study_date__lte=end)
        .values("hour")
        .annotate(total=Sum("seconds"))
    ):
        per_hour[r["hour"]] = r["total"]
    per_weekday = [0] * 7
    studied = [0] * 7
    for d, s in day_totals(user_id, start, end).items():
        per_weekday[d.weekday()] += s
        studied[d.weekday()] += 1
    return {
        "from": start,
        "to": end,
        "tz": settings_or_default(user_id).tz,
        "approximate": True,
        "hours": per_hour,
        "weekdays": [{"weekday": i, "seconds": per_weekday[i], "days": studied[i]} for i in range(7)],
    }


def time_vs_coverage(user_id, subject_id, start: date, end: date, *, verified_only: bool = False) -> dict | None:
    reports.validate_range(start, end, "week")
    subject = syllabus.get_subject(subject_id)
    if not subject:
        return None
    chapters = list(syllabus.list_chapters(subject))
    keys = [c.key for c in chapters]
    seconds_by_key: dict[str, int] = defaultdict(int)
    qs = (
        _rollups(user_id, start, end, verified_only)
        .filter(
            chapter__key__in=keys,
            chapter__subject__key=subject.key,
            chapter__subject__scheme__level=subject.scheme.level,
        )
        .values("chapter__key")
        .annotate(total=Sum("seconds"))
    )
    for r in qs:
        seconds_by_key[r["chapter__key"]] = r["total"]
    pct = coverage.coverage_pct_by_chapter(user_id, [c.id for c in chapters])
    timed = [seconds_by_key.get(c.key, 0) for c in chapters]
    average = sum(timed) / len(chapters) if chapters else 0
    items = [
        {
            "chapter_id": c.id,
            "key": c.key,
            "name": c.name,
            "seconds": seconds_by_key.get(c.key, 0),
            "coverage_percent": pct.get(c.id, 0),
            "flag": reports.chapter_flag(seconds_by_key.get(c.key, 0), pct.get(c.id, 0), average),
        }
        for c in chapters
    ]
    return {
        "from": start,
        "to": end,
        "subject": {"id": subject.id, "name": subject.name},
        "average_seconds": round(average),
        "chapters": items,
    }


def goals_progress(user_id, today: date) -> dict:
    settings = settings_or_default(user_id)
    week_first = reports.week_start_of(today, settings.week_start)
    goals = list(Goal.objects.filter(user_id=user_id).select_related("subject"))
    in_force = [g for g in goals if g.effective_from <= today and (g.effective_to is None or g.effective_to >= today)]
    totals = day_totals(user_id, week_first, today)
    today_seconds = totals.get(today, 0)
    week_seconds = sum(totals.values())
    daily_overall = next((g for g in in_force if g.period == "daily" and not g.subject_key), None)
    daily_minutes = daily_overall.target_minutes if daily_overall else DEFAULT_DAILY_GOAL_MINUTES
    days_before_today = (today - week_first).days

    def entry(g: Goal, done: int) -> dict:
        target = g.target_minutes * 60
        out = {
            "period": g.period,
            "subject_id": g.subject_id,
            "subject_key": g.subject_key,
            "subject_name": g.subject.name if g.subject_id else "",
            "target_minutes": g.target_minutes,
            "done_seconds": done,
            "percent": min(100, round(done * 100 / target)) if target else 0,
            "remaining_seconds": max(0, target - done),
        }
        if g.period == "weekly":
            out["pace"] = reports.pace(done, g.target_minutes, days_before_today)
        return out

    subject_seconds: dict[str, int] = defaultdict(int)
    if any(g.subject_key for g in in_force):
        rows = (
            _rollups(user_id, week_first, today)
            .exclude(subject__isnull=True)
            .values("subject_id")
            .annotate(total=Sum("seconds"))
        )
        meta = subject_meta({r["subject_id"] for r in rows})
        for r in rows:
            m = meta.get(r["subject_id"])
            if m:
                subject_seconds[m["subject_key"]] += r["total"]
    weekly_overall = next((g for g in in_force if g.period == "weekly" and not g.subject_key), None)
    daily_done = today_seconds
    return {
        "week_start": week_first,
        "daily": {
            "target_minutes": daily_minutes,
            "is_default": daily_overall is None,
            "done_seconds": daily_done,
            "percent": min(100, round(daily_done * 100 / (daily_minutes * 60))),
        },
        "weekly": entry(weekly_overall, week_seconds) if weekly_overall else None,
        "subjects": [entry(g, subject_seconds.get(g.subject_key, 0)) for g in in_force if g.subject_key],
        "streak": streak(user_id, today, goals),
    }


def streak(user_id, today: date, goals: list[Goal] | None = None) -> int:
    """Consecutive days (ending today, or yesterday while today is still open) on which the daily goal was met."""
    goals = goals if goals is not None else list(Goal.objects.filter(user_id=user_id))
    daily = [g for g in goals if g.period == "daily" and not g.subject_key]
    start = today - timedelta(days=400)
    totals = day_totals(user_id, start, today)
    met = {d for d, s in totals.items() if s >= daily_goal_minutes_on(daily, d) * 60}
    return reports.streak(met, today)


def weekly_summary(user_id, today: date, week_first: date | None = None) -> dict:
    settings = settings_or_default(user_id)
    current_first = reports.week_start_of(today, settings.week_start)
    first = week_first or current_first - timedelta(days=7)
    last = first + timedelta(days=6)
    totals = day_totals(user_id, first, last)
    total = sum(totals.values())
    best = max(totals.items(), key=lambda kv: kv[1], default=None)
    top = breakdown(user_id, first, last, by="subject")["items"]
    top_subject = next((i for i in top if i["key"] != UNTAGGED), None)
    goals = list(Goal.objects.filter(user_id=user_id, period="weekly", subject_key="").select_related("subject"))
    in_force = [g for g in goals if g.effective_from <= first and (g.effective_to is None or g.effective_to >= first)]
    if not in_force:  # a goal first set during that week applies from that week's start (PRD 5.4 note in the ERD)
        in_force = sorted([g for g in goals if first <= g.effective_from <= last], key=lambda g: g.effective_from)[:1]
    goal = in_force[0] if in_force else None
    shortfalls = []
    subject_goals = (
        Goal.objects.filter(user_id=user_id, period="weekly")
        .exclude(subject_key="")
        .filter(effective_from__lte=last)
        .filter(models_q_open_or_after(first))
    )
    if subject_goals:
        by_key = {i["key"].split(":")[-1]: i["seconds"] for i in top}
        for g in subject_goals.select_related("subject"):
            done = by_key.get(g.subject_key, 0)
            if done < g.target_minutes * 60:
                shortfalls.append(
                    {
                        "subject_id": g.subject_id,
                        "subject_name": g.subject.name if g.subject_id else g.subject_key,
                        "remaining_seconds": g.target_minutes * 60 - done,
                    }
                )
    shortfalls.sort(key=lambda s: -s["remaining_seconds"])
    return {
        "week_start": first,
        "week_end": last,
        "total_seconds": total,
        "days_tracked": len(totals),
        "best_day": {"date": best[0], "seconds": best[1]} if best else None,
        "top_subject": {"name": top_subject["name"], "seconds": top_subject["seconds"]} if top_subject else None,
        "goal": {
            "target_minutes": goal.target_minutes,
            "met": total >= goal.target_minutes * 60,
            "done_seconds": total,
        }
        if goal
        else None,
        "suggestion": {"kind": "subject_shortfall", **shortfalls[0]} if shortfalls else {"kind": "keep_going"},
    }


def report_stamp(user_id, start: date, end: date, *extra) -> str:
    """
    Cheap version stamp for ETags: changes when roll-ups in the range change (also on deletes, via count and sum),
    or when the student's settings or goals change. `extra` carries the request parameters.
    """
    roll = DailyRollup.objects.filter(user_id=user_id, study_date__gte=start, study_date__lte=end).aggregate(
        n=Count("id"), total=Sum("seconds"), latest=Max("updated_at")
    )
    hour = HourBucket.objects.filter(user_id=user_id, study_date__gte=start, study_date__lte=end).aggregate(
        total=Sum("seconds"), latest=Max("updated_at")
    )
    settings = get_settings(user_id)
    goal = Goal.objects.filter(user_id=user_id).aggregate(
        n=Count("id"), closed=Count("effective_to"), latest=Max("created_at")
    )
    raw = repr((roll, hour, settings.updated_at if settings else None, goal, extra))
    return hashlib.sha1(raw.encode()).hexdigest()  # noqa: S324 - a cache validator, not a security hash


def export_all(user_id) -> dict:
    """Everything tracking stores about the student (PRD FR-34), notes included."""
    return {
        "settings": _plain(get_settings(user_id)),
        "goals": [_plain(g) for g in Goal.objects.filter(user_id=user_id).order_by("effective_from")],
        "sessions": [_plain(s) for s in StudySession.objects.filter(user_id=user_id).order_by("started_at")],
    }


def _plain(obj) -> dict | None:
    if obj is None:
        return None
    out = {}
    for f in obj._meta.concrete_fields:
        value = getattr(obj, f.attname)
        out[f.attname] = (
            value.isoformat() if hasattr(value, "isoformat") else str(value) if hasattr(value, "hex") else value
        )
    return out
