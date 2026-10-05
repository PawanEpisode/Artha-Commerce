"""
The seed files are the syllabus content (F-02 ERD section 7). These tests pin their shape against the official
documents so a bad regeneration or a hand edit that drops a paper, a section or a chapter is caught in CI.
"""

import json
from pathlib import Path

import pytest
from django.core.management import call_command

from modules.syllabus.management.commands.load_syllabus_seed import SEED_DIR
from modules.syllabus.models import Chapter, Course, Level, Scheme, Subject, Topic

pytestmark = pytest.mark.django_db

# course/level -> (papers, papers that are electives). Source: ICAI NSET pages, ICSI Syllabus 2022, CMA Syllabus 2022.
EXPECTED_PAPERS = {
    ("ca", "foundation"): (4, 0),
    ("ca", "intermediate"): (6, 0),
    ("ca", "final"): (6, 0),
    ("ca", "spom"): (16, 0),  # Set A, Set B, Set C (10 papers), Set D (4 papers)
    ("cs", "foundation"): (4, 0),  # CSEET parts
    ("cs", "executive"): (7, 0),
    ("cs", "professional"): (16, 11),  # papers 1, 2, 3, 5, 6 + 6 electives (4.1-4.6) + 5 electives (7.1-7.5)
    ("cma", "foundation"): (4, 0),
    ("cma", "intermediate"): (8, 0),
    ("cma", "final"): (10, 3),  # papers 13-19 + elective 20A/20B/20C
}
# Every level now loads chapters and topics from the official document (CA from the 36 ICAI paper PDFs).
CURATED = set(EXPECTED_PAPERS)
# Chapters per CA level, counted from the PDFs (Intermediate Taxation = 7 + 9, Final Indirect Tax = 12 + 2, SPOM Set A = 10 + 4 + 3, ...).
CA_CHAPTERS = {"foundation": 46, "intermediate": 50, "final": 66, "spom": 142}


def seed_files():
    return sorted(SEED_DIR.rglob("*.json"))


def load(path: Path):
    return json.loads(path.read_text())


def test_there_is_one_seed_file_per_level_and_nothing_else():
    keys = {(load(f)["course"], load(f)["level"]) for f in seed_files()}
    assert keys == set(EXPECTED_PAPERS)
    assert len(seed_files()) == len(EXPECTED_PAPERS)


@pytest.mark.parametrize("path", seed_files(), ids=lambda p: f"{p.parent.parent.name}/{p.parent.name}")
def test_seed_file_shape(path):
    data = load(path)
    key = (data["course"], data["level"])
    papers, electives = EXPECTED_PAPERS[key]
    subjects = data["subjects"]
    assert len(subjects) == papers
    assert sum(1 for s in subjects if s.get("kind") == "elective") == electives
    assert len({s["key"] for s in subjects}) == papers  # stable keys are unique inside a scheme
    group_keys = {g["key"] for g in data["groups"]}
    for s in subjects:
        assert len(s["key"]) <= 80 and len(s["name"]) <= 200
        assert s.get("group") in group_keys | {None}
        if group_keys:
            assert s.get("group"), f"{s['name']} must belong to a group"
        assert len({c["key"] for c in s["chapters"]}) == len(s["chapters"])
        for c in s["chapters"]:
            assert len(c["key"]) <= 100 and len(c["name"]) <= 240 and len(c.get("section", "")) <= 200
            assert len({t["key"] for t in c.get("topics", [])}) == len(c.get("topics", []))
            for t in c.get("topics", []):
                assert len(t["key"]) <= 120 and len(t["name"]) <= 240
            lo, hi = c.get("marks_min"), c.get("marks_max")
            assert lo is None or hi is None or hi >= lo
    if key in CURATED:
        assert all(s["chapters"] for s in subjects), "every curated paper has chapters"
        assert data["scheme"]["source_url"].startswith("https://")
    if data["course"] == "ca":
        assert all(
            s["source_url"].startswith("https://resource.cdn.icai.org/")
            or s["source_url"].startswith("https://www.icai.org/")
            for s in subjects
        )
        assert sum(len(s["chapters"]) for s in subjects) == CA_CHAPTERS[data["level"]]
        assert all(s["total_marks"] == 100 for s in subjects)


def test_cma_chapter_marks_add_up_to_the_section_weight():
    for level in ("foundation", "intermediate", "final"):
        for s in load(SEED_DIR / "cma" / level / "2022.json")["subjects"]:
            by_section: dict[str, float] = {}
            for c in s["chapters"]:
                if c.get("marks_min") is not None:
                    by_section[c["section"]] = by_section.get(c["section"], 0) + c["marks_min"]
            for section, total in by_section.items():
                # "Section A: Commercial Laws (30%)": chapter marks (official plus the indicative split) fill the section weight
                weight = float(section.rsplit("(", 1)[1].rstrip("%)"))
                assert abs(total - weight) <= 0.5, f"{s['name']} / {section}"


def test_loaded_hierarchy_matches_the_files():
    call_command("load_syllabus_seed")
    for course, level in EXPECTED_PAPERS:
        scheme = Scheme.objects.get(level__course__code=course, level__code=level)
        papers, _ = EXPECTED_PAPERS[(course, level)]
        assert scheme.subjects.filter(is_active=True).count() == papers
    assert Level.objects.filter(course__code="ca", code="spom").exists()
    assert Course.objects.filter(code="cma").exists()
    assert Chapter.objects.filter(is_active=True).count() > 500
    assert Topic.objects.filter(is_active=True).count() > 3000
    spom = Subject.objects.filter(scheme__level__code="spom", key="psychology-and-philosophy").get()
    assert (
        spom.source_url == "https://www.icai.org/post/syllabus-nset-spom"
    )  # two PDFs (sections A and B): link to the page
    risk = Subject.objects.get(scheme__level__code="spom", key="risk-management")
    assert risk.source_url.endswith("92196bos-aps5090-set-c-p1.pdf")
    section = Chapter.objects.filter(
        subject__scheme__level__course__code="cma", subject__key="direct-and-indirect-taxation"
    )
    assert set(section.values_list("section", flat=True)) == {
        "Section A: Direct Taxation (50%)",
        "Section B: Indirect Taxation (50%)",
    }


def test_export_round_trips_section_and_source_url():
    from modules.syllabus import services

    call_command("load_syllabus_seed")
    scheme = Scheme.objects.get(level__course__code="cma", level__code="intermediate")
    exported = services.scheme_to_dict(scheme)
    taxation = next(s for s in exported["subjects"] if s["key"] == "direct-and-indirect-taxation")
    assert taxation["chapters"][0]["section"] == "Section A: Direct Taxation (50%)"
    before = (Chapter.objects.count(), Topic.objects.count())
    services.load_scheme_from_dict(exported)
    assert (Chapter.objects.count(), Topic.objects.count()) == before
    risk = services.scheme_to_dict(Scheme.objects.get(level__code="spom"))
    assert any(s.get("source_url", "").endswith("set-c-p1.pdf") for s in risk["subjects"])
