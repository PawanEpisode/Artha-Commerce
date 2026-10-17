"""
DB tests for the question-bank seed loader: idempotence, drafts never go live, marks cannot diverge, duplicates merge.
The loader reads its seeds from `seed_loader.SEED_ROOT`, which each test points at a temporary folder.
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.management import call_command

from modules.pyq.models import PaperQuestion, PyqPaper
from modules.questionbank import seed_loader
from modules.questionbank.domain.pdf_ingest import pyq as pyq_ingest
from modules.questionbank.models import DuplicateLink, Question, QuestionVersion

API = Path(__file__).resolve().parents[3]
SYLLABUS = API / "modules" / "syllabus" / "seed" / "cma" / "final" / "2022.json"
REAL_MCQ_SEED = Path(seed_loader.SEED_ROOT) / "mcq" / "p13.json"

pytestmark = pytest.mark.django_db


@pytest.fixture
def cma_final():
    call_command("load_syllabus_seed", str(SYLLABUS), "--publish")


@pytest.fixture
def seed_root(tmp_path, monkeypatch):
    monkeypatch.setattr(seed_loader, "SEED_ROOT", tmp_path)
    return tmp_path


def _real_items(n: int) -> list[dict]:
    seed = json.loads(REAL_MCQ_SEED.read_text(encoding="utf-8"))
    return [i for i in seed["items"] if i["status"] == "ok"][:n]


def _write(root: Path, kind: str, name: str, body: dict) -> Path:
    folder = root / kind
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _mcq_seed(items: list[dict]) -> dict:
    return {"schema": "artha.qbseed.v1", "kind": "mcq", "paper": "13", "items": items}


def test_item_load_is_idempotent(cma_final, seed_root):
    path = _write(seed_root, "mcq", "p13", _mcq_seed(_real_items(5)))
    first = seed_loader.load_item_seed(path, publish=False)
    second = seed_loader.load_item_seed(path, publish=False)
    assert (first.parsed, first.created, first.skipped) == (5, 5, [])
    assert (second.created, second.updated, second.unchanged) == (0, 0, 5)
    assert Question.objects.filter(origin_module="mcq").count() == 5


def test_nothing_goes_live_without_publish_and_drafts_never_do(cma_final, seed_root):
    items = _real_items(4)
    items[3]["status"] = "needs_review"
    items[3]["review_reasons"] = ["answer key not confirmed"]
    path = _write(seed_root, "mcq", "p13", _mcq_seed(items))

    seed_loader.load_item_seed(path, publish=False)
    assert Question.objects.filter(live_version__isnull=False).count() == 0

    report = seed_loader.load_item_seed(path, publish=True)
    live = set(Question.objects.filter(live_version__isnull=False).values_list("external_ref", flat=True))
    assert live == {i["external_ref"] for i in items[:3]}
    assert report.published == 3 and report.drafts == 1


def test_item_that_cannot_be_a_valid_draft_is_skipped_with_reason(cma_final, seed_root):
    items = _real_items(3)
    for o in items[1]["payload"]["options"]:
        o["is_correct"] = False  # key not found
    items[1]["status"] = "needs_review"
    report = seed_loader.load_item_seed(_write(seed_root, "mcq", "p13", _mcq_seed(items)), publish=True)
    assert report.created == 2
    assert len(report.skipped) == 1 and items[1]["external_ref"] in report.skipped[0]
    assert "exactly 1 correct option" in report.skipped[0]


def test_marks_follow_the_version_and_cannot_diverge(cma_final, seed_root):
    seed_loader.load_item_seed(_write(seed_root, "mcq", "p13", _mcq_seed(_real_items(3))), publish=True)
    for q in Question.objects.all():
        version = q.live_version or q.current_version
        assert q.marks == version.marks == Decimal("2")

    q = Question.objects.first()
    version = q.live_version
    version.marks = Decimal("5")
    version.save()
    q.refresh_from_db()
    assert q.marks == Decimal("5")  # the version is the source of truth

    q.marks = Decimal("9")
    q.save()
    q.refresh_from_db()
    assert q.marks == Decimal("5")  # a stray write to the denormalised column is corrected on save


def test_changed_item_makes_a_new_version_that_keeps_everything(cma_final, seed_root):
    item = _real_items(1)[0]
    path = _write(seed_root, "mcq", "p13", _mcq_seed([item]))
    seed_loader.load_item_seed(path, publish=False)

    changed = copy.deepcopy(item)
    changed["payload"]["stem_md"] += " (revised)"
    changed["payload"]["marks"] = "3"
    report = seed_loader.load_item_seed(_write(seed_root, "mcq", "p13", _mcq_seed([changed])), publish=False)
    assert report.updated == 1 and report.created == 0

    q = Question.objects.get(external_ref=item["external_ref"])
    version = q.current_version
    assert version.version_no == 2 and q.marks == version.marks == Decimal("3")
    assert version.options.count() == 4 and version.options.filter(is_correct=True).count() == 1
    assert q.difficulty is not None
    assert q.versions.filter(state=QuestionVersion.State.DRAFT).count() == 1


def test_dry_run_changes_nothing(cma_final, seed_root, capsys):
    _write(seed_root, "mcq", "p13", _mcq_seed(_real_items(3)))
    call_command("load_question_bank_seed", "--kind", "mcq", "--dry-run")
    out = capsys.readouterr().out
    assert "created=3" in out and "rolled back" in out
    assert Question.objects.count() == 0


def test_exact_copy_from_another_source_is_merged_not_duplicated(cma_final, seed_root):
    items = _real_items(1)
    twin = copy.deepcopy(items[0])
    twin["external_ref"] = "mcq:cma-final:p13:q900"
    report = seed_loader.load_item_seed(_write(seed_root, "mcq", "p13", _mcq_seed([*items, twin])), publish=False)
    assert report.created == 1 and report.merged == 1
    assert DuplicateLink.objects.count() == 1


# --- previous year papers ------------------------------------------------------------------------------------------------


def _transcription(term: str, *, doubt: bool = False) -> dict:
    mcq = {
        "label": "(i)",
        "kind": "mcq_single",
        "marks": 2,
        "stem_md": "Which of the following is a capital budgeting technique?",
        "options": [
            {"key": "A", "body_md": "Net present value"},
            {"key": "B", "body_md": "Trial balance"},
            {"key": "C", "body_md": "Bank reconciliation"},
        ],
        "correct": "A",
        "answer_md": "",
        "confidence": "high",
        "review": ["option C is cut off in the scan"] if doubt else [],
    }
    descriptive = {
        "label": "",
        "kind": "long_form",
        "marks": 14,
        "stem_md": "A project costs ₹ 10,00,000 and returns ₹ 3,00,000 a year for five years. Compute the pay-back period.",
        "answer_md": "Pay-back period = 10,00,000 / 3,00,000 = 3.33 years.",
        "confidence": "high",
        "review": [],
    }
    return {
        "schema": "artha.pyq-transcription.v1",
        "paper": "p14",
        "term_code": term,
        "total_marks": 16,
        "duration_minutes": 180,
        "answers_source": "suggested_answer_pdf",
        "sections": [
            {
                "label": "A",
                "choice": {"rule": "compulsory"},
                "questions": [{"number": "1", "marks": 2, "parts": [mcq]}],
            },
            {
                "label": "B",
                "choice": {"rule": "compulsory"},
                "questions": [{"number": "2", "marks": 14, "parts": [descriptive]}],
            },
        ],
    }


def _pyq_seed(t: dict) -> dict:
    subject = next(s for s in json.loads(SYLLABUS.read_text(encoding="utf-8"))["subjects"] if s["paper_number"] == 14)
    built = pyq_ingest.build_paper(t, subject=subject)
    return {
        "schema": "artha.qbseed.v1",
        "kind": "pyq",
        "paper": "14",
        "paper_review": [],
        "payload": built["payload"],
        "review": built["report"],
        "counts": built["counts"],
    }


def test_pyq_load_is_idempotent_and_marks_agree_everywhere(cma_final, seed_root):
    path = _write(seed_root, "pyq", "p14-2024-06", _pyq_seed(_transcription("2024-06")))
    first = seed_loader.load_pyq_seed(path, publish=False)
    second = seed_loader.load_pyq_seed(path, publish=False)
    assert first.skipped == [] and first.created == 2 and first.merged == 0
    assert first.created + first.updated + first.unchanged + first.merged == first.parsed
    assert (second.created, second.updated, second.unchanged) == (0, 0, 2)
    assert PyqPaper.objects.count() == 1

    for pq in PaperQuestion.objects.filter(is_leaf=True, question__isnull=False).select_related("question"):
        q = pq.question
        version = q.live_version or q.current_version
        assert pq.marks == q.marks == version.marks


def test_pyq_publish_goes_live_only_when_nothing_is_in_doubt(cma_final, seed_root):
    clean = _write(seed_root, "pyq", "p14-2024-06", _pyq_seed(_transcription("2024-06")))
    doubtful = _write(seed_root, "pyq", "p14-2024-12", _pyq_seed(_transcription("2024-12", doubt=True)))

    seed_loader.load_pyq_seed(doubtful, publish=True)
    paper = PyqPaper.objects.get(term_code="2024-12")
    assert paper.status != PyqPaper.Status.PUBLISHED
    doubtful_mcq = PaperQuestion.objects.get(paper=paper, number_label="1(i)").question
    assert doubtful_mcq.live_version_id is None

    report = seed_loader.load_pyq_seed(clean, publish=True)
    assert report.published == 2, report.notes
    assert PyqPaper.objects.get(term_code="2024-06").status == PyqPaper.Status.PUBLISHED


def test_paper_level_layout_notes_do_not_block_publishing(cma_final, seed_root):
    seed = _pyq_seed(_transcription("2024-06"))
    seed["paper_review"] = ["Page 8 of the PDF is blank."]
    path = _write(seed_root, "pyq", "p14-2024-06", seed)
    report = seed_loader.load_pyq_seed(path, publish=True)
    assert report.published == 2, report.notes
    assert PyqPaper.objects.get(term_code="2024-06").status == PyqPaper.Status.PUBLISHED


def test_an_empty_legacy_paper_shell_is_adopted_and_keeps_its_links(cma_final, seed_root):
    from modules.pyq.models import PaperLink

    seed = _pyq_seed(_transcription("2024-06"))
    payload = seed["payload"]
    course_level = {"course": payload["course_code"], "level": payload["level_code"]}
    from modules.syllabus.models import Course, Level

    course = Course.objects.get(code=course_level["course"])
    level = Level.objects.get(course=course, code=course_level["level"])
    shell = PyqPaper.objects.create(
        course=course,
        level=level,
        subject_key=payload["subject_key"],
        term_code="2024-06",
        external_ref="pyq:cma:final:legacy-shell",
        title="legacy",
        status=PyqPaper.Status.PUBLISHED,
        total_marks=100,
    )
    PaperLink.objects.create(paper=shell, link_kind="paper", label="ICMAI", url="https://icmai.in/x", host="icmai.in")

    report = seed_loader.load_pyq_seed(_write(seed_root, "pyq", "p14-2024-06", seed), publish=False)
    assert (
        report.skipped == [] and report.created + report.merged + report.unchanged == 2
    )  # questions are keyed by the seed's own refs, so they are reused
    shell.refresh_from_db()
    assert shell.external_ref == payload["external_ref"] and shell.status == PyqPaper.Status.DRAFT
    assert list(shell.links.values_list("url", flat=True)) == ["https://icmai.in/x"]
    assert PyqPaper.objects.count() == 1


def test_a_paper_with_questions_under_another_ref_is_left_alone(cma_final, seed_root):
    seed = _pyq_seed(_transcription("2024-06"))
    seed_loader.load_pyq_seed(_write(seed_root, "pyq", "p14-2024-06", seed), publish=False)
    other = copy.deepcopy(seed)
    other["payload"]["external_ref"] = "pyq:other:ref"
    report = seed_loader.load_pyq_seed(_write(seed_root, "pyq", "p14-other", other), publish=False)
    assert len(report.skipped) == 1 and "already holds this term" in report.skipped[0]
    assert PyqPaper.objects.count() == 1


def test_replace_legacy_withdraws_the_earlier_paper_and_loads_the_seeded_one(cma_final, seed_root):
    seed = _pyq_seed(_transcription("2024-06"))
    seed_loader.load_pyq_seed(_write(seed_root, "pyq", "p14-2024-06", seed), publish=False)
    PyqPaper.objects.update(external_ref="pyq:cma:final:legacy")  # pretend it was made by the early seeder
    path = _write(seed_root, "pyq", "p14-2024-06", seed)

    left = seed_loader.load_pyq_seed(path, publish=False)
    assert len(left.skipped) == 1 and "--replace-legacy" in left.skipped[0]

    report = seed_loader.load_pyq_seed(path, publish=False, replace_legacy=True)
    assert (
        report.skipped == [] and report.created + report.merged + report.unchanged == 2
    )  # questions are keyed by the seed's own refs, so they are reused
    old = PyqPaper.objects.get(external_ref="pyq:cma:final:legacy")
    assert old.status == PyqPaper.Status.WITHDRAWN and old.variant == "legacy-seed"
    assert PyqPaper.objects.get(external_ref=seed["payload"]["external_ref"]).variant == ""
