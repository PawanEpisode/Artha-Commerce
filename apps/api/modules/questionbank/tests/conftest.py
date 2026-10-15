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
def qb_flag(settings, monkeypatch):
    """Enables question_bank feature flag."""

    def _set(on: bool):
        class Client_:
            def get_feature_flag(self, key, distinct_id, **kwargs):
                return on if key == "question_bank" else None

        settings.POSTHOG_API_KEY = "phc_test"
        monkeypatch.setattr(feature_flags, "_client", Client_())
        feature_flags.clear_flag_cache()

    _set(True)
    yield _set
    feature_flags.clear_flag_cache()


@pytest.fixture
def api(make_token, qb_flag, db):
    return Api(make_token(sub=str(USER)))


@pytest.fixture
def editor_api(make_token, qb_flag, db):
    Profile.objects.update_or_create(
        id=EDITOR,
        defaults={"role": Profile.Role.EDITOR, "email": "editor@example.com", "full_name": "Editor"},
    )
    return Api(make_token(sub=str(EDITOR)))


@pytest.fixture
def syllabus_tree(db):
    return make_scheme()


@pytest.fixture
def events():
    emitted = []

    def _handler(name):
        return lambda **kw: emitted.append({"name": name, **kw})

    from core import events as core_events

    core_events.clear()
    for ev in ("question_version_live", "contribution_decided", "question_flagged", "question_taken_down"):
        core_events.subscribe(ev, _handler(ev))
    yield emitted
    core_events.clear()
