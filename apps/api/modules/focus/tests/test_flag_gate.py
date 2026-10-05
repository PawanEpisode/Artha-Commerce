"""The whole focus API sits behind the `focus_timer` flag; the student's own data stays reachable."""

import uuid

import pytest
from core import feature_flags
from django.urls import reverse

from modules.focus import urls as focus_urls

pytestmark = pytest.mark.django_db

OPEN_ENDPOINTS = {"focus-data"}


@pytest.fixture
def flag_off(settings, monkeypatch):
    class Off:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return False if key == "focus_timer" else None

    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", Off())
    feature_flags.clear_flag_cache()
    yield
    feature_flags.clear_flag_cache()


def _requests():
    from modules.focus.views import FocusView

    for pattern in focus_urls.urlpatterns:
        if pattern.name in OPEN_ENDPOINTS:
            continue
        kwargs = {name: uuid.uuid4() for name in pattern.pattern.converters}
        view_class = pattern.callback.view_class
        assert issubclass(view_class, FocusView), f"{pattern.name} must extend FocusView"
        for method in ("get", "post", "put", "patch", "delete"):
            if hasattr(view_class, method):
                yield method, reverse(pattern.name, kwargs=kwargs), pattern.name


def test_every_focus_endpoint_answers_403_feature_disabled_when_the_flag_is_off(api, flag_off):
    seen = list(_requests())
    assert len(seen) >= 14
    for method, path, name in seen:
        res = api._send(method, path.removeprefix("/api/v1"), {} if method != "get" else None)
        assert res.status_code == 403, f"{method.upper()} {name}"
        assert res.json_body["error"]["code"] == "feature_disabled", f"{method.upper()} {name}"


def test_the_students_own_data_stays_reachable(api, flag_off):
    assert api.get("/focus/data/").status_code == 200
    assert api.delete("/focus/data/").status_code == 204
