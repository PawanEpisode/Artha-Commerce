"""Small builders shared by the syllabus and coverage tests. They go through the real seed loader."""

from copy import deepcopy

from modules.syllabus.models import Scheme
from modules.syllabus.services import load_scheme_from_dict

SPEC = {
    "course": "ca",
    "level": "intermediate",
    "scheme": {"code": "2023", "name": "2023 Scheme", "source_url": "https://example.org/syllabus"},
    "groups": [{"key": "group-1", "name": "Group I"}, {"key": "group-2", "name": "Group II"}],
    "subjects": [
        {
            "key": "taxation",
            "paper_number": 3,
            "name": "Taxation",
            "group": "group-1",
            "total_marks": 100,
            "chapters": [
                {
                    "key": "gst-itc",
                    "name": "GST: Input Tax Credit",
                    "marks_min": 10,
                    "marks_max": 20,
                    "weight_source": "analysis",
                    "target_practice_sets": 2,
                    "topics": [
                        {"key": "eligibility", "name": "Eligibility", "kind": "rule"},
                        {"key": "blocked-credit", "name": "Blocked credit", "kind": "section"},
                        {"key": "reversal", "name": "Reversal of credit"},
                        {"key": "apportionment", "name": "Apportionment"},
                    ],
                },
                {"key": "residential-status", "name": "Residential status", "marks_min": 5, "marks_max": 5},
                {"key": "heads-of-income", "name": "Heads of income"},
            ],
        },
        {
            "key": "corporate-laws",
            "paper_number": 2,
            "name": "Corporate and Other Laws",
            "group": "group-2",
            "total_marks": 100,
            "chapters": [{"key": "companies-act", "name": "Companies Act", "marks_max": 10}],
        },
    ],
}


def make_scheme(*, publish: bool = True, code: str = "2023", spec: dict | None = None, **scheme_overrides) -> Scheme:
    data = deepcopy(spec or SPEC)
    data["scheme"] = {**data["scheme"], "code": code, **scheme_overrides}
    scheme = load_scheme_from_dict(data)
    if publish:
        from modules.syllabus.services import publish_scheme

        publish_scheme(scheme)
    return scheme
