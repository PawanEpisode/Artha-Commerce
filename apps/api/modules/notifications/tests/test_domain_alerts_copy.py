"""What the revision, exam and content notifications say (X-01.1 W3.4). Pure."""

import pytest

from modules.notifications.domain import daily_slot
from modules.notifications.domain.copy import BODY_LIMIT, TITLE_LIMIT, build_copy
from modules.notifications.domain.deeplinks import is_allowed


def test_one_chapter_due_names_it():
    copy = build_copy(
        "revision_due", {"local_date": "2026-10-07", "due_count": 1, "first_chapter": "Sale of Goods Act"}
    )
    assert (copy.title, copy.body) == ("Revision due", "Sale of Goods Act is due for revision today.")
    assert (copy.deep_link, copy.tag) == ("/app/revision", "revision:2026-10-07")


def test_several_chapters_due_say_how_many_and_where_to_start():
    copy = build_copy("revision_due", {"local_date": "2026-10-07", "due_count": 4, "first_chapter": "Partnership"})
    assert copy.body == "4 chapters are due for revision, starting with Partnership."


def test_revision_copy_without_a_chapter_name_still_reads_well():
    one = build_copy("revision_due", {"local_date": "2026-10-07", "due_count": 1})
    many = build_copy("revision_due", {"local_date": "2026-10-07", "due_count": 3})
    assert one.body == "1 chapter is due for revision today."
    assert many.body == "3 chapters are due for revision today."


def test_a_long_chapter_name_is_cut_not_the_sentence():
    copy = build_copy("revision_due", {"local_date": "2026-10-07", "due_count": 2, "first_chapter": "X" * 200})
    assert len(copy.body) <= BODY_LIMIT and copy.body.endswith("…")


@pytest.mark.parametrize("days_left", daily_slot.MILESTONES)
def test_every_milestone_has_its_own_calm_wording(days_left):
    copy = build_copy("exam_milestone", {"days_left": days_left})
    assert copy.tag == f"exam:{days_left}" and copy.deep_link == "/app"
    assert str(days_left) in copy.title or days_left == 1
    assert copy.body and "!" not in copy.body


def test_the_last_milestone_says_tomorrow_and_the_others_count_days():
    assert build_copy("exam_milestone", {"days_left": 1}).title == "Your exam is tomorrow"
    assert build_copy("exam_milestone", {"days_left": 14}).title == "14 days to your exam"


def test_milestone_bodies_are_all_different():
    bodies = {build_copy("exam_milestone", {"days_left": d}).body for d in daily_slot.MILESTONES}
    assert len(bodies) == len(daily_slot.MILESTONES)


def test_an_unlisted_day_count_still_gets_a_plain_message():
    copy = build_copy("exam_milestone", {"days_left": 21})
    assert copy.title == "21 days to your exam" and copy.body


def test_content_copy_names_the_item_and_links_to_it():
    copy = build_copy("content_published", {"item_id": "abc", "title": "May 2027 amendments", "link": "/app/syllabus"})
    assert copy.title == "New for your course"
    assert copy.body == "May 2027 amendments is now available."
    assert (copy.deep_link, copy.tag) == ("/app/syllabus", "content:abc")


def test_content_without_a_link_opens_the_workspace_home():
    assert build_copy("content_published", {"item_id": "abc", "title": "Mock test"}).deep_link == "/app"


@pytest.mark.parametrize(
    "event, context",
    [
        ("revision_due", {"local_date": "2026-10-07", "due_count": 99, "first_chapter": "Y" * 300}),
        ("exam_milestone", {"days_left": 60}),
        ("content_published", {"item_id": "abc", "title": "T" * 300}),
    ],
)
def test_every_new_alert_fits_a_lock_screen_and_links_inside_the_allow_list(event, context):
    copy = build_copy(event, context)
    assert len(copy.title) <= TITLE_LIMIT and len(copy.body) <= BODY_LIMIT
    assert is_allowed(copy.deep_link) and all(ord(c) < 0x2000 or c == "…" for c in copy.title + copy.body)
