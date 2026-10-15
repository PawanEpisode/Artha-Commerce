"""Lite mode (FR-F13-40): `open/` and `plan/` can answer the small payload, which stays under 12 KB gzipped."""

import gzip
import json

import pytest

from .helpers import register_many, register_practice

pytestmark = pytest.mark.django_db


@pytest.fixture
def opened(api, enrolled):
    register_practice()
    register_many()
    api.put("/today/settings/", {"minutes_per_day": 240})


def test_open_with_lite_drops_signals_and_week(api, opened):
    full = api.post("/today/open/").json_body
    lite = api.post("/today/open/", {"lite": True}).json_body
    assert "week" in full and "week" not in lite
    assert all("signals" in t["why"] for t in full["tasks"])
    assert all("signals" not in t["why"] for t in lite["tasks"])
    assert [t["id"] for t in full["tasks"]] == [t["id"] for t in lite["tasks"]]


def test_the_lite_setting_alone_gives_the_lite_payload(api, opened):
    api.put("/today/settings/", {"lite_mode": "on"})
    assert "week" not in api.post("/today/open/").json_body


def test_a_full_lite_plan_is_under_12_kb_gzipped(api, opened):
    body = api.post("/today/open/", {"lite": True}).json_body
    size = len(gzip.compress(json.dumps(body).encode()))
    assert size < 12 * 1024, size
