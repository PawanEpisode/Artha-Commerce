"""FR-30: the whole coverage API sits behind the `syllabus_coverage` flag; the student's own data stays reachable."""

import uuid

import pytest
from core import feature_flags
from django.urls import reverse

from modules.coverage import urls as coverage_urls

pytestmark = pytest.mark.django_db

OPEN_ENDPOINTS = {"coverage-data", "coverage-export"}  # export and delete of one's own data (FR-29) are never gated


@pytest.fixture
def flag_off(settings, monkeypatch):
    class Off:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return False if key == "syllabus_coverage" else None

    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", Off())
    feature_flags.clear_flag_cache()
    yield
    feature_flags.clear_flag_cache()


def _requests():
    """Every (method, path) the coverage API offers, built from its URL patterns so new endpoints are covered too."""
    from modules.coverage.views import CoverageView

    for pattern in coverage_urls.urlpatterns:
        if pattern.name in OPEN_ENDPOINTS:
            continue
        kwargs = {name: uuid.uuid4() for name in pattern.pattern.converters}
        view_class = pattern.callback.view_class
        assert issubclass(view_class, CoverageView), f"{pattern.name} must extend CoverageView"
        for method in ("get", "post", "put", "patch", "delete"):
            if hasattr(view_class, method):
                yield method, reverse(pattern.name, kwargs=kwargs), pattern.name


def test_every_coverage_endpoint_answers_403_feature_disabled_when_the_flag_is_off(api, flag_off):
    seen = list(_requests())
    assert len(seen) >= 15  # guards against the discovery silently finding nothing
    for method, path, name in seen:
        res = api._send(method, path.removeprefix("/api/v1"), {} if method != "get" else None)
        assert res.status_code == 403, f"{method.upper()} {name}"
        assert res.json_body["error"]["code"] == "feature_disabled", f"{method.upper()} {name}"
        assert "not available" in res.json_body["error"]["message"]


def test_a_student_can_still_export_and_delete_their_data_when_the_flag_is_off(api, flag_off):
    assert api.get("/coverage/export/").status_code == 200
    assert api.delete("/coverage/").status_code == 204


def test_the_flag_is_checked_after_sign_in(client, flag_off):
    res = client.get("/api/v1/coverage/overview/")
    assert res.status_code in (401, 403) and res.json()["error"]["code"] != "feature_disabled"


def test_public_syllabus_pages_are_not_behind_the_flag(client, flag_off, scheme):
    assert client.get("/api/v1/syllabus/courses/").status_code == 200
    assert client.get("/api/v1/syllabus/courses/ca/levels/intermediate/").status_code == 200


def test_the_api_works_as_before_when_the_flag_is_on_or_unknown(api, ids, enrolled):
    assert api.get("/coverage/overview/").status_code == 200  # no PostHog key in tests: every flag is on
