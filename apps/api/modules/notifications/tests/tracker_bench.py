"""A student's stopwatch and study time on a movable clock, driven through the real `tracking` services (no HTTP)."""

import uuid
from datetime import UTC, date, datetime, timedelta

from modules.tracking import services
from modules.tracking.models import ActiveStopwatch, DailyRollup, TrackerSettings

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
OTHER = uuid.UUID("7a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d")
# Monday 5 Oct 2026, 10:00 in India. A stopwatch started now reaches three hours at 07:30 UTC (13:00 in India).
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
THREE_HOURS = timedelta(hours=3)


class Tracker:
    def __init__(self, monkeypatch, capture_on_commit, user=USER, now=NOW):
        self.user = user
        self.now = now
        self._capture = capture_on_commit
        monkeypatch.setattr(services, "_now", lambda: self.now)

    # The clock ------------------------------------------------------------------------------------------------
    def set(self, now: datetime) -> datetime:
        self.now = now
        return now

    def advance(self, **delta) -> datetime:
        self.now += timedelta(**delta)
        return self.now

    # Actions: each runs, then lets the after-commit announcements run, like a request would ------------------------
    def _do(self, fn, *args, **kwargs):
        with self._capture(execute=True):
            return fn(self.user, *args, **kwargs)

    def start(self, **kwargs) -> ActiveStopwatch:
        sw, _ = self._do(services.start_stopwatch, client_id=kwargs.pop("client_id", uuid.uuid4()), **kwargs)
        return sw

    def pause(self, **kw):
        return self._do(services.pause_stopwatch, **kw)

    def resume(self, **kw):
        return self._do(services.resume_stopwatch, **kw)

    def retag(self, **changes):
        return self._do(services.change_stopwatch_context, version=self.stopwatch.version, changes=changes)

    def stop(self, **kw):
        return self._do(services.stop_stopwatch, **kw)

    def sync(self, **kw):
        return self._do(services.sync_stopwatch, **kw)

    def erase(self):
        return self._do(services.delete_all_for_user)

    def study(self, minutes: int, *, ended_ago: timedelta = timedelta(0), client_id=None):
        """A finished manual session of `minutes` that ended `ended_ago` before now."""
        end = self.now - ended_ago
        return self._do(
            services.add_manual,
            client_id=client_id or uuid.uuid4(),
            started_at=end - timedelta(minutes=minutes),
            ended_at=end,
        )

    @property
    def stopwatch(self) -> ActiveStopwatch | None:
        return ActiveStopwatch.objects.filter(pk=self.user).first()


def rollup(user, day: date, minutes: int, *, tz: str = "Asia/Kolkata") -> None:
    """Counted time for a past day, written straight into the roll-up (what reports and streaks read)."""
    TrackerSettings.objects.get_or_create(pk=user, defaults={"tz": tz})
    DailyRollup.objects.create(
        user_id=user, study_date=day, activity_type="reading", source="manual", seconds=minutes * 60, sessions=1
    )
