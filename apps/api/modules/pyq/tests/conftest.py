"""
Fixtures for PYQ tests.
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.core.cache import cache
from django.test import Client

from core import feature_flags
from modules.profiles.models import Profile
from modules.syllabus.tests.helpers import make_scheme

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
EDITOR = uuid.UUID("11111111-2222-3333-4444-555555555555")


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
        res.json_body = res.json() if res.content else None
        return res

    def get(self, path, **headers):
        return self._send("get", path, **headers)

    def post(self, path, body=None):
        return self._send("post", path, body or {})


@pytest.fixture(autouse=True)
def _fresh_throttle_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def pyq_flags(settings, monkeypatch):
    """Enables both question_bank and pyq_bank feature flags."""

    def _set(on: bool):
        class Client_:
            def get_feature_flag(self, key, distinct_id, **kwargs):
                if key in ("question_bank", "pyq_bank"):
                    return on
                return None

        settings.POSTHOG_API_KEY = "phc_test"
        monkeypatch.setattr(feature_flags, "_client", Client_())
        feature_flags.clear_flag_cache()

    _set(True)
    yield _set
    feature_flags.clear_flag_cache()


@pytest.fixture
def api(make_token, pyq_flags, db):
    return Api(make_token(sub=str(USER)))


@pytest.fixture
def editor_api(make_token, pyq_flags, db):
    Profile.objects.update_or_create(
        id=EDITOR,
        defaults={"role": Profile.Role.EDITOR, "email": "editor@example.com", "full_name": "Editor"},
    )
    return Api(make_token(sub=str(EDITOR)))


@pytest.fixture
def syllabus_tree(db):
    return make_scheme()
