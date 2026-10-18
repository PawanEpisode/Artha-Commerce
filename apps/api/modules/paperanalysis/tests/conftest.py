"""
Fixtures and helpers for Paper Analysis tests.
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.core.cache import cache
from django.test import Client

from modules.profiles.models import Profile
from modules.syllabus.tests.helpers import make_scheme

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
EDITOR = uuid.UUID("11111111-2222-3333-4444-555555555555")
ADMIN = uuid.UUID("99999999-8888-7777-6666-555555555555")


class Api:
    def __init__(self, token: str):
        self.c = Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _send(self, method, path, body=None, **headers):
        res = getattr(self.c, method)(
            f"/api/v1{path}",
            data=json.dumps(body) if body is not None else None,
            content_type="application/json",
            **headers,
        )
        res.json_body = res.json() if res.content and res.headers.get("Content-Type", "").startswith("application/json") else None
        return res

    def get(self, path, **headers):
        return self._send("get", path, **headers)

    def post(self, path, body=None, **headers):
        return self._send("post", path, body or {}, **headers)

    def put(self, path, body=None, **headers):
        return self._send("put", path, body or {}, **headers)

    def patch(self, path, body=None, **headers):
        return self._send("patch", path, body or {}, **headers)

    def delete(self, path, **headers):
        return self._send("delete", path, **headers)


@pytest.fixture(autouse=True)
def _fresh_throttle_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def pa_flags(monkeypatch):
    """Enables paper_analysis and paper_analysis_planner feature flags."""
    flags = {
        "paper_analysis": True,
        "paper_analysis_planner": True,
        "paper_analysis_public": True,
    }

    def _set(on: bool):
        flags["paper_analysis"] = on
        flags["paper_analysis_planner"] = on
        flags["paper_analysis_public"] = on

    def mock_flag_enabled(name, distinct_id, *, strict=False):
        if name in flags:
            return flags[name]
        return not strict

    monkeypatch.setattr("core.permissions.flag_enabled", mock_flag_enabled)
    monkeypatch.setattr("core.feature_flags.flag_enabled", mock_flag_enabled)
    return _set


@pytest.fixture
def syllabus_tree(db):
    return make_scheme()


@pytest.fixture
def student_api(db, pa_flags, make_token):
    Profile.objects.update_or_create(
        id=USER,
        defaults={"email": "student@artha.test", "role": "student", "full_name": "Test Student"},
    )
    return Api(make_token(sub=str(USER)))


@pytest.fixture
def editor_api(db, pa_flags, make_token):
    Profile.objects.update_or_create(
        id=EDITOR,
        defaults={"email": "editor@artha.test", "role": "editor", "full_name": "Test Editor"},
    )
    return Api(make_token(sub=str(EDITOR)))


@pytest.fixture
def admin_api(db, pa_flags, make_token):
    Profile.objects.update_or_create(
        id=ADMIN,
        defaults={"email": "admin@artha.test", "role": "admin", "full_name": "Test Admin"},
    )
    return Api(make_token(sub=str(ADMIN)))
