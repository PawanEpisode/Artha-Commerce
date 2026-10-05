import uuid

import pytest

# The tracking fixtures (pinned clock, two students, a scheme with subjects and chapters, a JSON client) are shared.
from modules.tracking.tests.conftest import (  # noqa: F401
    NOW,
    Clock,
    _fresh_throttle_counters,
    api,
    clock,
    ids,
    iso,
    other_api,
    scheme,
)


def start(c, **extra):
    body = {"client_id": str(uuid.uuid4()), **extra}
    return c.post("/focus/timer/start/", body), body["client_id"]


def timer(c):
    return c.get("/focus/timer/").json_body


def beat(c):
    return c.post("/focus/timer/heartbeat/")


@pytest.fixture
def running(request):
    student = request.getfixturevalue("api")
    res, cid = start(student)
    assert res.status_code == 201
    return res.json_body["timer"], cid
