"""A student's Pomodoro timer on a movable clock, driven through the real `focus` services (no HTTP)."""

import uuid
from datetime import UTC, datetime, timedelta

from modules.focus import services
from modules.focus.models import ActiveTimer
from modules.tracking import services as tracking

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
# Monday 5 Oct 2026, 10:00 in India. A classic focus round started now ends at 04:55 UTC.
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
FOCUS_END = NOW + timedelta(minutes=25)


class Bench:
    def __init__(self, monkeypatch, capture_on_commit, user=USER):
        self.user = user
        self.now = NOW
        self._capture = capture_on_commit
        monkeypatch.setattr(tracking, "_now", lambda: self.now)

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

    def start(self, *, overtime: bool = False, **kwargs) -> ActiveTimer:
        services.update_settings(self.user, {"overtime_enabled": overtime})
        timer, _ = self._do(services.start, client_id=kwargs.pop("client_id", uuid.uuid4()), **kwargs)
        return timer

    def pause(self, **kw):
        return self._do(services.pause, **kw)

    def resume(self, **kw):
        return self._do(services.resume, **kw)

    def extend(self, **kw):
        return self._do(services.extend, **kw)

    def complete(self, **kw):
        return self._do(services.complete, **kw)

    def skip_break(self, **kw):
        return self._do(services.skip_break, **kw)

    def end(self, **kw):
        return self._do(services.end, **kw)

    def claim(self, **kw):
        return self._do(services.claim, **kw)

    def change_context(self, **kw):
        return self._do(services.change_context, **kw)

    def sync(self, **kw):
        return self._do(services.sync, **kw)

    def heartbeat(self):
        return self._do(services.sync, alive=True)

    def erase(self):
        return self._do(services.delete_all_for_user)

    @property
    def timer(self) -> ActiveTimer | None:
        return ActiveTimer.objects.filter(pk=self.user).first()
