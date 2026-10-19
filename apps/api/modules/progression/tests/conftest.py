import json
from copy import deepcopy

import pytest
from django.core.cache import cache
from django.test import Client

from modules.coverage.services import create_enrollment
from modules.syllabus.models import ExamTerm, Level
from modules.syllabus.services import load_scheme_from_dict, publish_scheme
from modules.syllabus.tests.helpers import make_scheme

USER = "3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11"
OTHER = "9a1e7c52-1a5b-4d6e-8c3f-2b7d4e5f6a70"

FINAL_SPEC = {
    "course": "ca",
    "level": "final",
    "scheme": {"code": "2024", "name": "2024 Final Scheme", "source_url": "https://example.org/final"},
    "groups": [{"key": "group-3", "name": "Group I (Final)"}, {"key": "group-4", "name": "Group II (Final)"}],
    "subjects": [
        {
            "key": "financial-reporting",
            "paper_number": 1,
            "name": "Financial Reporting",
            "group": "group-3",
            "total_marks": 100,
            "chapters": [{"key": "ind-as-115", "name": "Revenue from Contracts", "marks_min": 10, "marks_max": 15}],
        },
        {
            "key": "advanced-financial-management",
            "paper_number": 2,
            "name": "Advanced Financial Management",
            "group": "group-3",
            "total_marks": 100,
            "chapters": [{"key": "portfolio-management", "name": "Portfolio Management", "marks_min": 15, "marks_max": 20}],
        },
        {
            "key": "advanced-auditing",
            "paper_number": 3,
            "name": "Advanced Auditing and Professional Ethics",
            "group": "group-4",
            "total_marks": 100,
            "chapters": [{"key": "standards-on-auditing", "name": "Standards on Auditing", "marks_min": 20, "marks_max": 25}],
        },
        {
            "key": "direct-tax-laws",
            "paper_number": 4,
            "name": "Direct Tax Laws and International Taxation",
            "group": "group-4",
            "total_marks": 100,
            "chapters": [{"key": "transfer-pricing", "name": "Transfer Pricing", "marks_min": 15, "marks_max": 20}],
        },
    ],
}


class Api:
    """Tiny JSON client bound to one student."""

    def __init__(self, token: str):
        self.c = Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _send(self, method, path, body=None):
        res = getattr(self.c, method)(
            f"/api/v1/progression{path}",
            data=json.dumps(body) if body is not None else None,
            content_type="application/json",
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
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def scheme(db):
    return make_scheme()


@pytest.fixture
def final_scheme(db, scheme):
    # Ensure Final level exists in CA
    ca_course = scheme.level.course
    final_level, _ = Level.objects.get_or_create(
        course=ca_course,
        code="final",
        defaults={"name": "Final", "sort_order": 2, "is_active": True},
    )
    # Ensure exam term for Final
    ExamTerm.objects.get_or_create(
        course=ca_course,
        level=final_level,
        code="2027-05",
        defaults={"name": "May 2027", "is_open": True},
    )
    spec = deepcopy(FINAL_SPEC)
    final_s = load_scheme_from_dict(spec)
    publish_scheme(final_s)
    return final_s


@pytest.fixture
def enrolled(db, scheme):
    term = ExamTerm.objects.filter(level=scheme.level).first()
    return create_enrollment(
        user_id=USER,
        scheme_id=scheme.id,
        target_term_id=term.id if term else None,
        daily_minutes=360,
    )


@pytest.fixture
def api(make_token, db):
    return Api(make_token(sub=USER))


@pytest.fixture
def other_api(make_token, db):
    return Api(make_token(sub=OTHER))
