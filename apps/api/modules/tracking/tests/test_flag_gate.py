"""FR-33: the whole tracker API sits behind the `time_tracker` flag; the student's own data stays reachable."""

import uuid

import pytest
from django.urls import reverse

from core import feature_flags
from modules.tracking import urls as tracking_urls

pytestmark = pytest.mark.django_db

OPEN_ENDPOINTS = {"tracking-data"}  # export and delete of one's own data are never gated


@pytest.fixture
def flag_off(settings, monkeypatch):
    class Off:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return False if key == "time_tracker" else None

    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", Off())
    feature_flags.clear_flag_cache()
    yield
    feature_flags.clear_flag_cache()


def _requests():
    from modules.tracking.views import TrackingView

    for pattern in tracking_urls.urlpatterns:
        if pattern.name in OPEN_ENDPOINTS:
            continue
        kwargs = {name: uuid.uuid4() for name in pattern.pattern.converters}
        view_class = pattern.callback.view_class
        assert issubclass(view_class, TrackingView), f"{pattern.name} must extend TrackingView"
        for method in ("get", "post", "put", "patch", "delete"):
            if hasattr(view_class, method):
                yield method, reverse(pattern.name, kwargs=kwargs), pattern.name


def test_every_tracking_endpoint_answers_403_feature_disabled_when_the_flag_is_off(api, flag_off):
    seen = list(_requests())
    assert len(seen) >= 30  # guards against the discovery silently finding nothing
    for method, path, name in seen:
        res = api._send(method, path.removeprefix("/api/v1"), {} if method != "get" else None)
        assert res.status_code == 403, f"{method.upper()} {name}"
        assert res.json_body["error"]["code"] == "feature_disabled", f"{method.upper()} {name}"


def test_the_students_own_data_stays_reachable_with_the_flag_off(api, flag_off):
    assert api.get("/tracking/data/").status_code == 200
    assert api.delete("/tracking/data/").status_code == 204


def test_nothing_is_reachable_without_signing_in(client):
    for method, path, name in _requests():
        res = getattr(client, method)(path, content_type="application/json")
        assert res.status_code in (401, 403), f"{method.upper()} {name}"
    assert client.get(reverse("tracking-data")).status_code in (401, 403)


def test_the_flag_is_on_without_a_posthog_key(api):
    assert api.get("/tracking/stopwatch/").status_code == 200
