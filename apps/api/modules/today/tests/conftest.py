import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from core import feature_flags
from modules.coverage import services as coverage_services
from modules.syllabus.tests.helpers import make_scheme
from modules.today import registry, runner


@pytest.fixture(autouse=True)
def _real_providers():
    """`test_registry` empties the process-wide registry; every other test starts with what the apps register in `ready()`."""
    from modules.coverage import today_providers
    from modules.today import legacy_bridge, planner_provider

    registry.clear()
    today_providers.register()
    legacy_bridge.register()
    planner_provider.register()
    yield


@pytest.fixture(autouse=True)
def _inline_providers_and_fresh_config(settings):
    """Providers run inside the test's database transaction (a pool thread would not see it), and operator config is re-read."""
    settings.TODAY_PROVIDER_PARALLEL = False
    runner.clear_config_cache()
    yield
    runner.clear_config_cache()


# ---- API fixtures -----------------------------------------------------------------------------------------------------------

USER = "3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11"
OTHER = "9a1e7c52-1a5b-4d6e-8c3f-2b7d4e5f6a70"


class Api:
    """Tiny JSON client bound to one student."""

    def __init__(self, token: str):
        self.c = Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _send(self, method, path, body=None, **headers):
        res = getattr(self.c, method)(
            f"/api/v1{path}",
            data=json.dumps(body) if body is not None else None,
            content_type="application/json",
            **headers,
        )
        res.json_body = res.json() if res.content else None
        return res

    def get(self, path, **headers):
        return self._send("get", path, **headers)

    def post(self, path, body=None):
        return self._send("post", path, body or {})

    def put(self, path, body=None):
        return self._send("put", path, body or {})

    def patch(self, path, body=None):
        return self._send("patch", path, body or {})

    def delete(self, path, body=None):
        return self._send("delete", path, body)


@pytest.fixture(autouse=True)
def _fresh_throttle_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def flag(settings, monkeypatch):
    """`today_plan` (and `today_planner`, unless given) on or off for everyone, through the same PostHog client seam the other modules' tests use."""

    def _set(on: bool, planner: bool | None = None):
        planner = on if planner is None else planner

        class Client_:
            def get_feature_flag(self, key, distinct_id, **kwargs):
                return {"today_plan": on, "today_planner": planner}.get(key)

        settings.POSTHOG_API_KEY = "phc_test"
        monkeypatch.setattr(feature_flags, "_client", Client_())
        feature_flags.clear_flag_cache()

    _set(True)
    yield _set
    feature_flags.clear_flag_cache()


@pytest.fixture
def api(make_token, flag, db):
    return Api(make_token(sub=USER))


@pytest.fixture
def other_api(make_token, flag, db):
    return Api(make_token(sub=OTHER))


@pytest.fixture
def scheme(db):
    return make_scheme()


@pytest.fixture
def enrolled(scheme):
    """USER is enrolled in the test scheme; the exam is eight weeks away, so the phase is `consolidate`."""
    coverage_services.create_enrollment(
        USER, scheme_id=scheme.id, exam_date=(timezone.now() + timedelta(days=56)).date(), daily_minutes=180
    )
    return scheme
