"""Counters, the day-completed rule, week dots, and the deep-link allow-list."""

import pytest

from modules.today.domain import deeplinks, week

# ---- counters and the day-completed rule ------------------------------------------------------------------------------------


def test_recount_matches_the_erd_definitions():
    rows = [
        ("done", 10, True),
        ("done", 5, True),
        ("skipped", 8, True),
        ("suggested", 20, True),
        ("accepted", 6, True),
        ("snoozed", 12, True),  # moved away: not planned, not open
        ("expired", 7, True),
        ("suggested", 15, False),  # a bonus task: counts nowhere
    ]
    got = week.recount(rows)
    assert got == week.Counters(
        planned_count=5,
        done_count=2,
        skipped_count=1,
        open_count=2,
        snoozed_count=1,
        planned_minutes=49,
        open_minutes=26,
    )


def test_recount_of_nothing_is_zero():
    assert week.recount([]) == week.Counters()


@pytest.mark.parametrize(
    ("open_", "done", "skipped", "expected"),
    [
        (0, 6, 0, True),
        (0, 5, 1, True),
        (0, 3, 3, True),  # exactly half is enough
        (0, 2, 3, False),
        (0, 1, 5, False),
        (1, 5, 0, False),  # something is still open
        (0, 0, 0, False),  # an empty plan is not a completed day
    ],
)
def test_day_completed(open_, done, skipped, expected):
    assert week.day_completed(open_count=open_, done_count=done, skipped_count=skipped) is expected


def test_closing_message_celebrates_a_real_day_and_stays_calm_otherwise():
    assert week.day_closing(open_count=0, done_count=5, skipped_count=1) == "celebrate"
    assert week.day_closing(open_count=0, done_count=1, skipped_count=5) == "calm"  # "You did 1 and skipped 5"
    assert week.day_closing(open_count=2, done_count=1, skipped_count=0) is None
    assert week.day_closing(open_count=0, done_count=0, skipped_count=0) is None


def test_week_dots():
    assert week.day_outcome(planned_count=0, done_count=0, completed=False) == "no_plan"
    assert week.day_outcome(planned_count=6, done_count=6, completed=True) == "all"
    assert week.day_outcome(planned_count=6, done_count=2, completed=False) == "some"
    assert week.day_outcome(planned_count=6, done_count=0, completed=False) == "none"


# ---- deep links -------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/app/revision",
        "/app/recall/review",
        "/app/syllabus/chapters/3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11",
        "/app/notes/pdf/abc",
        "/app/settings/today",
    ],
)
def test_allowed_paths(path):
    assert deeplinks.valid_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/",
        "/app",
        "/app/",
        "https://evil.example/app/revision",
        "//evil.example",
        "/app/revision?x=1",
        "/app/revision#top",
        "/app/../admin",
        "/app/revisionx",  # a prefix is not a path
        "/app/unknown",
        "/api/v1/today/open",
        "app/revision",
        "/app/revision/ spaced",
        "javascript:alert(1)",
        "/app/" + "a" * 300,
    ],
)
def test_rejected_paths(path):
    assert not deeplinks.valid_path(path)


def test_search_objects_are_flat_scalars_with_short_values():
    assert deeplinks.valid_search({"chapter": "abc", "n": 5, "mode": "quiz"})
    assert deeplinks.valid_search({})
    assert not deeplinks.valid_search({"from": "x"})  # reserved: Today sets it
    assert not deeplinks.valid_search({"task": "x"})
    assert not deeplinks.valid_search({"nested": {"a": 1}})
    assert not deeplinks.valid_search({"flag": True})
    assert not deeplinks.valid_search({"Bad-Key": "x"})
    assert not deeplinks.valid_search({"long": "x" * 201})
    assert not deeplinks.valid_search({f"k{n}": n for n in range(9)})
    assert not deeplinks.valid_search(["a"])


def test_with_origin_adds_from_and_task():
    assert deeplinks.with_origin({"chapter": "abc"}, "t-1") == {"chapter": "abc", "from": "today", "task": "t-1"}
