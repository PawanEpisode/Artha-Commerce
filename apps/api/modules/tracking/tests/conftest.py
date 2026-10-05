from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache

from modules.coverage.tests.conftest import OTHER, USER, Api  # noqa: F401 - shared JSON client and student ids
from modules.syllabus.models import Chapter, Subject
from modules.syllabus.tests.helpers import make_scheme
from modules.tracking import services

# Monday 5 Oct 2026, 10:00 in India (04:30 UTC): a fixed "now" so every test is deterministic.
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)


class Clock:
    def __init__(self, now):
        self.now = now

    def set(self, now):
        self.now = now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)
        return self.now

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def _fresh_throttle_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    c = Clock(NOW)
    monkeypatch.setattr(services, "_now", c)
    return c


@pytest.fixture
def scheme(db):
    return make_scheme()


@pytest.fixture
def api(make_token, db):
    return Api(make_token(sub=USER))


@pytest.fixture
def other_api(make_token, db):
    return Api(make_token(sub=OTHER))


@pytest.fixture
def ids(scheme):
    return {
        "taxation": str(Subject.objects.get(key="taxation").id),
        "laws": str(Subject.objects.get(key="corporate-laws").id),
        "gst": str(Chapter.objects.get(key="gst-itc").id),
        "residential": str(Chapter.objects.get(key="residential-status").id),
        "companies": str(Chapter.objects.get(key="companies-act").id),
    }


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def ist(day: int, hour: int, minute: int = 0, month: int = 10, year: int = 2026):
    """A moment given in India time, as a UTC datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=UTC) - timedelta(hours=5, minutes=30)


def manual(api, start, end=None, minutes=None, **extra):
    import uuid

    body = {"client_id": str(uuid.uuid4()), "started_at": iso(start), **extra}
    if end is not None:
        body["ended_at"] = iso(end)
    if minutes is not None:
        body["duration_seconds"] = minutes * 60
    return api.post("/tracking/sessions/", body)
