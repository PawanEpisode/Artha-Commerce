"""Elective papers: the student picks one option per slot and coverage counts only the chosen one."""

from copy import deepcopy

import pytest

from modules.coverage.models import ChapterProgress, CoverageEvent, EnrollmentElective
from modules.syllabus import selectors as syllabus
from modules.syllabus.models import Subject
from modules.syllabus.tests.helpers import SPEC, make_scheme

ELECTIVE_KEYS = ["elective-a", "elective-b", "elective-c"]


def _spec(version_keys=None):
    spec = deepcopy(SPEC)
    spec["groups"].append({"key": "electives", "name": "Elective Papers (choose one)"})
    for number, key in enumerate(version_keys or ELECTIVE_KEYS):
        spec["subjects"].append(
            {
                "key": key,
                "paper_number": 20,
                "name": f"Elective {number}",
                "group": "electives",
                "total_marks": 100,
                "kind": "elective",
                "is_optional": True,
                "chapters": [
                    {"key": f"{key}-one", "name": "One", "marks_max": 10},
                    {"key": f"{key}-two", "name": "Two", "marks_max": 10},
                ],
            }
        )
    return spec


@pytest.fixture
def elective_scheme(db):
    return make_scheme(spec=_spec())


def subject_id(key):
    return str(Subject.objects.get(key=key).id)


def test_slots_are_derived_from_optional_subjects(elective_scheme):
    slots = syllabus.elective_slots(elective_scheme)
    assert [s.key for s in slots] == ["electives:20"]
    assert [o.key for o in slots[0].options] == ELECTIVE_KEYS


def test_a_single_optional_subject_is_not_a_slot(db):
    scheme = make_scheme(spec=_spec(["only-one"]))
    assert syllabus.elective_slots(scheme) == []


def test_public_level_payload_lists_slots(elective_scheme, client):
    body = client.get("/api/v1/syllabus/courses/ca/levels/intermediate/").json()
    assert [s["key"] for s in body["elective_slots"]] == ["electives:20"]
    assert {o["key"] for o in body["elective_slots"][0]["options"]} == set(ELECTIVE_KEYS)


def test_schemes_without_electives_have_no_slots(scheme, client):
    assert client.get("/api/v1/syllabus/courses/ca/levels/intermediate/").json()["elective_slots"] == []


def _enrol(api, scheme, **extra):
    res = api.post("/coverage/enrollments/", {"scheme": str(scheme.id), **extra})
    assert res.status_code == 201, res.content
    return res.json_body


def _overview(api):
    return api.get("/coverage/overview/").json_body


def _excluded(api):
    return {s["key"]: s["excluded_chapters"] for s in _overview(api)["subjects"]}


def test_enrolling_without_a_choice_excludes_every_option(api, elective_scheme):
    enrollment = _enrol(api, elective_scheme)
    assert enrollment["electives_pending"] == 1
    assert all(_excluded(api)[k] == 2 for k in ELECTIVE_KEYS)
    assert _excluded(api)["taxation"] == 0
    assert _overview(api)["electives"][0]["chosen"] is None


def test_enrolling_with_a_choice_counts_only_that_paper(api, elective_scheme):
    enrollment = _enrol(api, elective_scheme, electives={"electives:20": subject_id("elective-b")})
    assert enrollment["electives_pending"] == 0
    excluded = _excluded(api)
    assert excluded["elective-b"] == 0
    assert excluded["elective-a"] == 2 and excluded["elective-c"] == 2
    assert _overview(api)["electives"][0]["chosen"] == subject_id("elective-b")


def test_changing_the_choice_moves_the_exclusions(api, elective_scheme):
    enrollment = _enrol(api, elective_scheme, electives={"electives:20": subject_id("elective-a")})
    res = api.put(
        f"/coverage/enrollments/{enrollment['id']}/electives/",
        {"choices": {"electives:20": subject_id("elective-c")}},
    )
    assert res.status_code == 200, res.content
    excluded = _excluded(api)
    assert excluded["elective-c"] == 0 and excluded["elective-a"] == 2 and excluded["elective-b"] == 2
    assert res.json_body["electives"][0]["chosen"] == subject_id("elective-c")
    assert EnrollmentElective.objects.filter(enrollment_id=enrollment["id"]).count() == 1


def test_progress_survives_a_change_of_choice(api, elective_scheme):
    enrollment = _enrol(api, elective_scheme, electives={"electives:20": subject_id("elective-a")})
    chapter_id = str(ChapterProgress.objects.get(chapter__key="elective-a-one").chapter_id)
    api.post("/coverage/events/", {"chapter_id": chapter_id, "type": "practice_done"})
    api.put(
        f"/coverage/enrollments/{enrollment['id']}/electives/",
        {"choices": {"electives:20": subject_id("elective-b")}},
    )
    api.put(
        f"/coverage/enrollments/{enrollment['id']}/electives/",
        {"choices": {"electives:20": subject_id("elective-a")}},
    )
    progress = ChapterProgress.objects.get(chapter__key="elective-a-one")
    assert progress.is_excluded is False
    assert progress.practice_count == 1
    types = list(
        CoverageEvent.objects.filter(chapter__key="elective-a-one")
        .order_by("occurred_at")
        .values_list("type", flat=True)
    )
    assert types[-2:] == ["excluded", "included"]


def test_clearing_a_choice_makes_it_pending_again(api, elective_scheme):
    enrollment = _enrol(api, elective_scheme, electives={"electives:20": subject_id("elective-a")})
    res = api.put(f"/coverage/enrollments/{enrollment['id']}/electives/", {"choices": {"electives:20": None}})
    assert res.status_code == 200
    assert all(_excluded(api)[k] == 2 for k in ELECTIVE_KEYS)
    assert api.get("/coverage/enrollments/").json_body["results"][0]["electives_pending"] == 1


def test_percentages_ignore_unchosen_electives(api, elective_scheme):
    _enrol(api, elective_scheme, electives={"electives:20": subject_id("elective-a")})
    overview = _overview(api)
    assert overview["level"]["chapters_total"] == 4 + 2  # taxation 3 + laws 1 core, plus the chosen elective's 2


def test_invalid_choices_are_rejected(api, elective_scheme):
    enrollment = _enrol(api, elective_scheme)
    url = f"/coverage/enrollments/{enrollment['id']}/electives/"
    assert api.put(url, {"choices": {"nope:1": subject_id("elective-a")}}).status_code == 400
    assert api.put(url, {"choices": {"electives:20": subject_id("taxation")}}).status_code == 400
    assert api.put(url, {"choices": {"electives:20": "not-a-uuid"}}).status_code == 400


def test_electives_of_another_student_are_not_reachable(api, other_api, elective_scheme):
    enrollment = _enrol(api, elective_scheme)
    res = other_api.put(
        f"/coverage/enrollments/{enrollment['id']}/electives/",
        {"choices": {"electives:20": subject_id("elective-a")}},
    )
    assert res.status_code == 404


def test_elective_papers_cannot_be_excluded_by_hand(api, elective_scheme):
    _enrol(api, elective_scheme, electives={"electives:20": subject_id("elective-a")})
    assert api.put(f"/coverage/subjects/{subject_id('elective-a')}/exclusion/", {"excluded": True}).status_code == 400
    chapter_id = str(ChapterProgress.objects.get(chapter__key="elective-b-one").chapter_id)
    assert api.put(f"/coverage/chapters/{chapter_id}/exclusion/", {"excluded": False}).status_code == 400


def test_core_papers_can_still_be_excluded(api, elective_scheme):
    _enrol(api, elective_scheme)
    res = api.put(f"/coverage/subjects/{subject_id('taxation')}/exclusion/", {"excluded": True})
    assert res.status_code == 200


def test_rebuild_from_the_ledger_keeps_the_choice(api, elective_scheme):
    from modules.coverage import services
    from modules.coverage.models import Enrollment

    enrollment = _enrol(api, elective_scheme, electives={"electives:20": subject_id("elective-b")})
    services.rebuild_enrollment(Enrollment.objects.get(pk=enrollment["id"]))
    excluded = _excluded(api)
    assert excluded["elective-b"] == 0 and excluded["elective-a"] == 2


def test_switching_scheme_carries_the_choice(api, elective_scheme):
    enrollment = _enrol(api, elective_scheme, electives={"electives:20": subject_id("elective-b")})
    spec = _spec()
    old = elective_scheme
    old.to_term = old.level.terms.get(code="2027-05")
    old.save()
    spec["scheme"]["from_term"] = "2027-09"
    newer = make_scheme(code="2027", spec=spec, from_term="2027-09")
    res = api.patch(f"/coverage/enrollments/{enrollment['id']}/", {"scheme": str(newer.id)})
    assert res.status_code == 200, res.content
    assert res.json_body["electives_pending"] == 0
    overview = _overview(api)
    chosen = overview["electives"][0]["chosen"]
    assert Subject.objects.get(pk=chosen).key == "elective-b"
    assert Subject.objects.get(pk=chosen).scheme_id == newer.id
    excluded = _excluded(api)
    assert excluded["elective-b"] == 0 and excluded["elective-a"] == 2


def test_export_and_delete_cover_the_choice(api, elective_scheme):
    _enrol(api, elective_scheme, electives={"electives:20": subject_id("elective-a")})
    export = api.get("/coverage/export/").json_body
    assert export["enrollments"][0]["electives"] == {"electives:20": "elective-a"}
    assert api.delete("/coverage/").status_code == 204
    assert EnrollmentElective.objects.count() == 0
