"""Layering rules of the recall module (CLAUDE.md rule 2, ERD 9), enforced by reading the source."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOREIGN_MODELS = re.compile(
    r"^\s*(?:from\s+modules\.(?!recall\b)\w+(?:\.\w+)*\.models\b|import\s+modules\.(?!recall\b)\w+\.models\b|from\s+modules\.(?!recall\b)\w+\s+import\s+[^#\n]*\bmodels\b)",
    re.M,
)


def sources(*, tests: bool = False):
    for path in ROOT.rglob("*.py"):
        if "migrations" in path.parts or "__pycache__" in path.parts:
            continue
        if ("tests" in path.parts) is tests:
            yield path


def test_no_recall_file_imports_the_models_of_another_module():
    offenders = [str(p.relative_to(ROOT)) for p in sources() if FOREIGN_MODELS.search(p.read_text())]
    assert offenders == []


def test_the_pattern_would_catch_a_violation():
    assert FOREIGN_MODELS.search("from modules.syllabus.models import Chapter")
    assert FOREIGN_MODELS.search("import modules.notes.models")
    assert FOREIGN_MODELS.search("from modules.notes import models")
    assert not FOREIGN_MODELS.search("from modules.syllabus import selectors")
    assert not FOREIGN_MODELS.search("from .models import RecallItem")
    assert not FOREIGN_MODELS.search("from modules.recall.models import RecallItem")


def test_views_import_no_models_and_run_no_queries():
    text = (ROOT / "views.py").read_text()
    assert not re.search(r"^\s*(?:from\s+\.models|from\s+modules\.recall\.models|import\s+.*models)", text, re.M)
    assert ".objects." not in text and "transaction" not in text


def test_only_adapters_import_other_modules_and_only_through_selectors():
    allowed = {"adapters/syllabus.py": "modules.syllabus", "adapters/coverage.py": None}
    other = re.compile(r"^\s*(?:from|import)\s+modules\.(?!recall\b)(\w+)", re.M)
    for path in sources():
        rel = str(path.relative_to(ROOT))
        found = set(other.findall(path.read_text()))
        if found:
            assert rel in allowed, f"{rel} imports {found}"
    assert "selectors" in (ROOT / "adapters/syllabus.py").read_text()
