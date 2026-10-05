import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from modules.syllabus.models import Chapter, ExamTerm, Subject, Topic
from modules.syllabus.tests.helpers import make_scheme

USER = "3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11"
OTHER = "9a1e7c52-1a5b-4d6e-8c3f-2b7d4e5f6a70"


class Api:
    """Tiny JSON client bound to one student."""

    def __init__(self, token: str):
        self.c = Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _send(self, method, path, body=None):
        res = getattr(self.c, method)(
            f"/api/v1{path}", data=json.dumps(body) if body is not None else None, content_type="application/json"
        )
        res.json_body = res.json() if res.content else None
        return res

    def get(self, path):
        return self._send("get", path)

    def post(self, path, body=None):
        return self._send("post", path, body or {})

    def put(self, path, body=None):
        return self._send("put", path, body or {})

    def patch(self, path, body=None):
        return self._send("patch", path, body or {})

    def delete(self, path):
        return self._send("delete", path)


@pytest.fixture(autouse=True)
def _fresh_throttle_counters():
    """DRF counts writes per student in the process-wide cache; without this, a long run starts answering 429."""
    cache.clear()
    yield
    cache.clear()


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
    """Frequently used ids as strings."""
    gst = Chapter.objects.get(key="gst-itc")
    return {
        "scheme": str(scheme.id),
        "taxation": str(Subject.objects.get(key="taxation").id),
        "laws": str(Subject.objects.get(key="corporate-laws").id),
        "gst": str(gst.id),
        "residential": str(Chapter.objects.get(key="residential-status").id),
        "heads": str(Chapter.objects.get(key="heads-of-income").id),
        "companies": str(Chapter.objects.get(key="companies-act").id),
        "topics": [str(t.id) for t in Topic.objects.filter(chapter=gst).order_by("sort_order")],
        "term": str(ExamTerm.objects.get(level__course__code="ca", level__code="intermediate", code="2027-05").id),
        "foundation_term": str(
            ExamTerm.objects.get(level__course__code="ca", level__code="foundation", code="2027-01").id
        ),
        "cs_term": str(ExamTerm.objects.get(level__course__code="cs", level__code="executive", code="2027-06").id),
    }


def set_targets(api, practice_sets=2, revisions=2, mocks=1):
    res = api.put(
        "/coverage/settings/", {"targets": {"practice_sets": practice_sets, "revisions": revisions, "mocks": mocks}}
    )
    assert res.status_code == 200, res.json_body
    return res.json_body


@pytest.fixture
def enrolled(api, ids):
    """Enrolled student with targets practice 2, revisions 2, mocks 1 (what the syllabus table used to say for GST)."""
    res = api.post("/coverage/enrollments/", {"scheme": ids["scheme"], "target_term": ids["term"]})
    assert res.status_code == 201, res.json_body
    set_targets(api)
    return res.json_body


def days_from_now(n: int):
    return (timezone.now() + timedelta(days=n)).date().isoformat()
