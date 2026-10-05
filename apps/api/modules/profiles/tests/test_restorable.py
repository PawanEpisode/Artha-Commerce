import json
from pathlib import Path

import pytest

from modules.profiles.domain.restorable import clean_visit

_CASES = json.loads((Path(__file__).parent / "fixtures" / "restorable_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _CASES, ids=[c["name"] for c in _CASES])
def test_shared_restorable_cases(case):
    expected = case["expected"]
    result = clean_visit(case["path"], case["search"])
    assert result == (None if expected is None else (expected["path"], expected["search"]))


def test_search_is_bounded():
    assert clean_visit("/app/syllabus", "view=simple&" + "x=1&" * 80) == ("/app/syllabus", "")
