"""Scheme switch: topics carry over on matching names, and the summary lists what carried, is new and is gone."""

from copy import deepcopy

import pytest

from modules.coverage.models import Enrollment
from modules.syllabus.models import Chapter, ChapterMap, Scheme
from modules.syllabus.services import build_default_chapter_map, publish_scheme
from modules.syllabus.tests.helpers import SPEC, make_scheme

pytestmark = pytest.mark.django_db


def second_scheme(mutate) -> Scheme:
    spec = deepcopy(SPEC)
    mutate(spec)
    new = make_scheme(publish=False, code="2025", spec=spec, from_term="2027-09")
    return new


def switch(api, new: Scheme):
    old = Enrollment.objects.get()
    scheme_old = old.scheme
    scheme_old.to_term = scheme_old.level.terms.get(code="2027-05")
    scheme_old.save()
    publish_scheme(new)
    res = api.patch(f"/coverage/enrollments/{old.id}/", {"scheme": str(new.id)})
    assert res.status_code == 200, res.json_body
    return res.json_body


def test_topics_carry_over_when_only_the_name_matches(api, ids, enrolled):
    def mutate(spec):
        gst = spec["subjects"][0]["chapters"][0]
        # same four topics, re-keyed, re-worded a little and reordered
        gst["topics"] = [
            {"key": "t-reversal", "name": "Reversal of Credit"},
            {"key": "t-eligibility", "name": "1. Eligibility"},
            {"key": "t-apportion", "name": "Apportionment of credit"},
            {"key": "t-blocked", "name": "Blocked  credit"},
        ]

    new = second_scheme(mutate)
    build_default_chapter_map(Enrollment.objects.get().scheme, new)
    for topic_id in ids["topics"][:2]:  # Eligibility and Blocked credit
        assert api.put(f"/coverage/topics/{topic_id}/", {"done": True}).status_code == 200

    switch(api, new)

    new_gst = Chapter.objects.get(subject__scheme=new, key="gst-itc")
    done = {t["key"]: t["is_done"] for t in api.get(f"/coverage/chapters/{new_gst.id}/").json_body["topics"]}
    assert done == {"t-reversal": False, "t-eligibility": True, "t-apportion": False, "t-blocked": True}


def test_a_renamed_chapter_carries_progress_through_the_proposed_map(api, ids, enrolled):
    def mutate(spec):
        spec["subjects"][0]["chapters"][1].update(key="residency", name="Chapter 2: Residential Status")

    new = second_scheme(mutate)
    report = build_default_chapter_map(Enrollment.objects.get().scheme, new)
    assert report.created == 4 and report.needs_review == 0
    assert api.put(f"/coverage/chapters/{ids['residential']}/read/", {"done": True}).status_code == 200

    body = switch(api, new)
    assert body["switch_summary"]["carried_chapters"] == 4
    renamed = Chapter.objects.get(subject__scheme=new, key="residency")
    assert api.get(f"/coverage/chapters/{renamed.id}/").json_body["chapter"]["coverage_pct"] > 0


def test_merged_chapters_carry_all_their_done_topics_whatever_the_ratio(api, ids, enrolled):
    def mutate(spec):
        chapters = spec["subjects"][0]["chapters"]
        chapters[0]["topics"] = []  # keep the merge target's topics under our control below
        chapters[:] = [
            {
                "key": "gst-and-residency",
                "name": "GST Input Tax Credit and Residential status",
                "topics": [
                    {"key": "a", "name": "Eligibility"},
                    {"key": "b", "name": "Blocked credit"},
                    {"key": "c", "name": "Reversal of credit"},
                    {"key": "d", "name": "Apportionment"},
                ],
            }
        ]

    new = second_scheme(mutate)
    build_default_chapter_map(Enrollment.objects.get().scheme, new)
    merged = ChapterMap.objects.filter(relation="merged")
    assert merged.count() == 2 and all(str(m.carry_ratio) == "0.50" for m in merged)
    for topic_id in ids["topics"]:
        assert api.put(f"/coverage/topics/{topic_id}/", {"done": True}).status_code == 200

    switch(api, new)

    target = Chapter.objects.get(subject__scheme=new, key="gst-and-residency")
    topics = api.get(f"/coverage/chapters/{target.id}/").json_body["topics"]
    assert all(t["is_done"] for t in topics)  # ratio 0.5 does not halve topics matched by name


def test_switch_summary_lists_what_carried_what_is_new_and_what_is_gone(api, ids, enrolled):
    def mutate(spec):
        chapters = spec["subjects"][0]["chapters"]
        chapters[:] = [c for c in chapters if c["key"] != "heads-of-income"]
        chapters.append({"key": "brand-new", "name": "Brand new chapter"})
        chapters.append({"key": "another-new", "name": "Another fresh chapter"})

    new = second_scheme(mutate)
    build_default_chapter_map(Enrollment.objects.get().scheme, new)
    summary = switch(api, new)["switch_summary"]

    assert summary["carried_chapters"] == len(summary["carried"]) == 3
    assert summary["new_chapters"] == len(summary["new"]) == 2
    assert summary["removed_chapters"] == len(summary["removed"]) == 1
    assert {c["name"] for c in summary["new"]} == {"Brand new chapter", "Another fresh chapter"}
    assert summary["removed"][0]["subject"]["name"] == "Taxation"
    for ref in (*summary["carried"], *summary["new"], *summary["removed"]):
        assert {"id", "key", "name", "subject"} <= set(ref) and {"id", "key", "name"} <= set(ref["subject"])
