"""
Pure time maths for the tracker. No Django, no database: everything takes and returns plain values so it can be tested
exhaustively. The web mirrors the limits in `modules/tracker/lib/limits.ts` (a parity test pins both).

The server is the clock for live capture. All elapsed time derives from timestamps and the stored pause total, never from
counting ticks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# --- Limits (PRD 5.4, ERD 4). Mirrored in apps/web/src/modules/tracker/lib/limits.ts ---------------------------
MIN_SESSION_SECONDS = 60  # shorter sessions are discarded, never stored
MAX_SESSION_SECONDS = 12 * 3600  # stopwatch cap and per-row sanity cap
MAX_MANUAL_SPAN_SECONDS = 24 * 3600
CONFIRM_OLDER_THAN_DAYS = 60  # older manual entries need a confirmation tick
REJECT_OLDER_THAN_DAYS = 365
CLOCK_SKEW_SECONDS = 300
UNDO_SECONDS = 10
IDLE_ANSWER_SECONDS = 120
MERGE_MAX_GAP_SECONDS = 30 * 60
OFFLINE_START_MAX_AGE_SECONDS = 12 * 3600  # a queued offline action may be at most this old
IDLE_MINUTES_MIN, IDLE_MINUTES_MAX, IDLE_MINUTES_DEFAULT = 5, 60, 10
GOAL_DAILY_MIN, GOAL_DAILY_MAX = 15, 1440
GOAL_WEEKLY_MIN, GOAL_WEEKLY_MAX = 30, 10080
NOTE_MAX_CHARS = 500

SOURCES = ("pomodoro", "stopwatch", "manual", "auto")
ACTIVITY_TYPES = ("reading", "practice", "revision", "notes", "mock_test", "other")


class DurationError(ValueError):
    """A rule of the time maths was broken. `code` is machine readable, `str(error)` is student readable."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def whole_seconds(moment: datetime) -> datetime:
    """Sessions are stored at one-second precision so `focus = span - pauses` is exact."""
    return moment.replace(microsecond=0)


def span_seconds(started_at: datetime, ended_at: datetime) -> int:
    return int((ended_at - started_at).total_seconds())


# --- Live stopwatch -------------------------------------------------------------------------------------------
def elapsed_seconds(
    started_at: datetime, now: datetime, paused_at: datetime | None = None, paused_total: int = 0
) -> int:
    """Counted time: wall time up to now (or the pause), minus finished pauses. Never negative."""
    end = min(now, paused_at) if paused_at else now
    return max(0, span_seconds(started_at, end) - paused_total)


def clamp_client_time(at: datetime | None, now: datetime, max_age: int = OFFLINE_START_MAX_AGE_SECONDS) -> datetime:
    """A queued offline action carries the moment of the tap. Never in the future, never older than `max_age`."""
    if at is None or at > now:
        return now
    return max(at, now - timedelta(seconds=max_age))


def idle_due(now: datetime, last_active_at: datetime, idle_minutes: int) -> bool:
    return idle_minutes > 0 and (now - last_active_at).total_seconds() >= idle_minutes * 60


def idle_expired(now: datetime, idle_prompted_at: datetime | None) -> bool:
    """The prompt was shown and not answered within two minutes: the stopwatch pauses at the last active moment."""
    return idle_prompted_at is not None and (now - idle_prompted_at).total_seconds() >= IDLE_ANSWER_SECONDS


@dataclass(frozen=True)
class StopOutcome:
    ended_at: datetime
    focus_seconds: int
    idle_trimmed: bool


def stop_outcome(
    started_at: datetime,
    now: datetime,
    *,
    paused_at: datetime | None,
    paused_total: int,
    last_active_at: datetime,
    requested_end: datetime | None = None,
) -> StopOutcome:
    """
    Where a stopwatch session ends and how much of it counts. Counting stops at a pause. Over 12 hours is trimmed back to
    the last active moment (PRD 5.4); if even that is over 12 hours the counted time is capped at 12 hours.
    """
    end = min(requested_end or now, now)
    if paused_at:
        end = min(end, paused_at)
    end = max(end, started_at)
    focus = span_seconds(started_at, end) - paused_total
    trimmed = False
    if focus > MAX_SESSION_SECONDS:
        trimmed = True
        candidate = max(started_at, min(last_active_at, end))
        end = candidate
        focus = span_seconds(started_at, end) - paused_total
        if focus > MAX_SESSION_SECONDS:
            focus = MAX_SESSION_SECONDS
            end = started_at + timedelta(seconds=MAX_SESSION_SECONDS + paused_total)
    return StopOutcome(end, max(0, focus), trimmed)


# --- Manual entry ---------------------------------------------------------------------------------------------
def validate_manual_window(started_at: datetime, ended_at: datetime, now: datetime) -> bool:
    """
    Checks a manual entry (PRD FR-9). Returns True when the student must tick "yes, this is right" (older than 60 days).
    Raises DurationError for anything that is simply not allowed.
    """
    if ended_at > now + timedelta(seconds=CLOCK_SKEW_SECONDS) or started_at > now + timedelta(
        seconds=CLOCK_SKEW_SECONDS
    ):
        raise DurationError("future", "Study time cannot be in the future.")
    if ended_at <= started_at:
        raise DurationError("end_before_start", "The end must be after the start.")
    span = span_seconds(started_at, ended_at)
    if span < MIN_SESSION_SECONDS:
        raise DurationError("too_short", "Sessions shorter than one minute are not saved.")
    if span > MAX_MANUAL_SPAN_SECONDS:
        raise DurationError("too_long", "One entry can be at most 24 hours. Split it into more than one.")
    age = now - started_at
    if age > timedelta(days=REJECT_OLDER_THAN_DAYS):
        raise DurationError("too_old", "Entries older than 365 days cannot be added.")
    return age > timedelta(days=CONFIRM_OLDER_THAN_DAYS)


# --- Overlaps -------------------------------------------------------------------------------------------------
Interval = tuple[datetime, datetime]


def overlaps(a: Interval, b: Interval) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def free_segments(window: Interval, busy: list[Interval]) -> list[Interval]:
    """`window` minus the busy intervals, in time order. Used to trim a manual entry that overlaps others."""
    segments: list[Interval] = []
    cursor = window[0]
    for start, end in sorted(busy):
        if end <= cursor:
            continue
        if start >= window[1]:
            break
        if start > cursor:
            segments.append((cursor, min(start, window[1])))
        cursor = max(cursor, end)
        if cursor >= window[1]:
            break
    if cursor < window[1]:
        segments.append((cursor, window[1]))
    return segments


def longest_segment(segments: list[Interval], minimum: int = MIN_SESSION_SECONDS) -> Interval | None:
    usable = [s for s in segments if span_seconds(*s) >= minimum]
    return max(usable, key=lambda s: span_seconds(*s)) if usable else None


# --- Local day and hour buckets -------------------------------------------------------------------------------
def local_date(moment: datetime, tz: str) -> date:
    return moment.astimezone(ZoneInfo(tz)).date()


def _allocate(total: int, weights: list[int]) -> list[int]:
    """Largest-remainder split of `total` in proportion to `weights`; the parts always add up to `total` exactly."""
    weight_sum = sum(weights)
    if total <= 0 or weight_sum <= 0:
        return [0] * len(weights)
    exact = [total * w / weight_sum for w in weights]
    parts = [int(x) for x in exact]
    order = sorted(range(len(weights)), key=lambda i: exact[i] - parts[i], reverse=True)
    for i in order[: total - sum(parts)]:
        parts[i] += 1
    return parts


def split_by_local_hour(
    started_at: datetime, ended_at: datetime, tz: str, paused_total_seconds: int = 0
) -> list[tuple[date, int, int]]:
    """
    Spreads a session over the local (date, hour) cells it touches. Wall time per cell is exact; the counted time
    (span minus pauses) is spread in proportion, because pause intervals are not stored per hour. That is why hour
    patterns are "approximate" for sessions that had pauses. The cells add up to the counted time exactly, so a
    midnight-crossing session lands in both days and daily totals stay equal to the sum of sessions.
    """
    zone = ZoneInfo(tz)
    counted = max(0, span_seconds(started_at, ended_at) - paused_total_seconds)
    cells: list[tuple[date, int, int]] = []
    cursor = started_at
    while cursor < ended_at:
        local = cursor.astimezone(zone)
        into_hour = local.minute * 60 + local.second
        boundary = cursor + timedelta(seconds=3600 - into_hour)
        chunk_end = min(boundary, ended_at)
        cells.append((local.date(), local.hour, span_seconds(cursor, chunk_end)))
        cursor = chunk_end
    shares = _allocate(counted, [c[2] for c in cells])
    merged: dict[tuple[date, int], int] = {}
    for (d, h, _), share in zip(cells, shares, strict=True):
        if share:
            merged[(d, h)] = merged.get((d, h), 0) + share
    return [(d, h, s) for (d, h), s in sorted(merged.items())]


def day_seconds(cells: list[tuple[date, int, int]]) -> dict[date, int]:
    out: dict[date, int] = {}
    for d, _, s in cells:
        out[d] = out.get(d, 0) + s
    return out


# --- Merge and split ------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Piece:
    started_at: datetime
    ended_at: datetime
    focus_seconds: int
    paused_total_seconds: int = 0
    pause_count: int = 0


def merge_pieces(pieces: list[Piece]) -> Piece:
    """One row from adjacent rows: summed counted time (never more than the span), gaps count as pauses."""
    if len(pieces) < 2:
        raise DurationError("too_few", "Pick at least two sessions to merge.")
    ordered = sorted(pieces, key=lambda p: p.started_at)
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        gap = span_seconds(earlier.ended_at, later.started_at)
        if gap > MERGE_MAX_GAP_SECONDS:
            raise DurationError("too_far_apart", "Only sessions less than 30 minutes apart can be merged.")
    started = ordered[0].started_at
    ended = max(p.ended_at for p in ordered)
    span = span_seconds(started, ended)
    focus = min(sum(p.focus_seconds for p in ordered), span)
    return Piece(started, ended, focus, span - focus, sum(p.pause_count for p in ordered))


def split_piece(piece: Piece, at: datetime) -> tuple[Piece, Piece]:
    """Two rows at `at`, each at least a minute. Pauses are attributed to the first part (PRD 5.4)."""
    if not (piece.started_at < at < piece.ended_at):
        raise DurationError("outside", "Pick a time inside the session.")
    first_span = span_seconds(piece.started_at, at)
    second_span = span_seconds(at, piece.ended_at)
    paused = max(0, span_seconds(piece.started_at, piece.ended_at) - piece.focus_seconds)
    first_focus = first_span - paused
    if first_focus < MIN_SESSION_SECONDS or second_span < MIN_SESSION_SECONDS:
        raise DurationError("too_short", "Each part must be at least one minute of counted time.")
    return (
        Piece(piece.started_at, at, first_focus, paused, piece.pause_count),
        Piece(at, piece.ended_at, second_span, 0, 0),
    )
