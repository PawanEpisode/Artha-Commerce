"""The pure judgement behind the long-stopwatch alert: it works from the row's columns and the clock alone."""

import uuid
from datetime import UTC, datetime, timedelta

from modules.tracking.domain.judgement import EARLY_TOLERANCE, RunState, StopwatchFacts, judge_running, reaches_at

T0 = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
CID = uuid.uuid4()
THREE_H = 3 * 3600


def facts(**kw) -> StopwatchFacts:
    base = dict(
        client_id=CID,
        version=1,
        started_at=T0,
        paused_at=None,
        paused_total_seconds=0,
        idle_pending=False,
        idle_prompted_at=None,
    )
    return StopwatchFacts(**{**base, **kw})


def judge(f, now, *, version=1, client_id=CID, after=THREE_H):
    return judge_running(f, client_id=client_id, expected_version=version, now=now, after_seconds=after)


def test_reaches_at_is_start_plus_pauses_plus_the_mark():
    assert reaches_at(T0, 0, THREE_H) == T0 + timedelta(hours=3)
    assert reaches_at(T0, 600, THREE_H) == T0 + timedelta(hours=3, minutes=10)


def test_a_running_stopwatch_at_the_mark_is_due_and_reports_its_counted_time():
    result = judge(facts(), T0 + timedelta(hours=3))
    assert result.state is RunState.DUE and result.elapsed_seconds == THREE_H


def test_finished_pauses_do_not_count():
    f = facts(paused_total_seconds=1200)
    assert judge(f, T0 + timedelta(hours=3)).state is RunState.NOT_DUE
    assert judge(f, T0 + timedelta(hours=3, minutes=20)).state is RunState.DUE


def test_a_moment_before_the_mark_is_forgiven_but_not_much_more():
    mark = T0 + timedelta(hours=3)
    assert judge(facts(), mark - EARLY_TOLERANCE).state is RunState.DUE
    assert judge(facts(), mark - EARLY_TOLERANCE - timedelta(seconds=1)).state is RunState.NOT_DUE


def test_no_stopwatch_is_gone():
    assert judge(None, T0).state is RunState.GONE


def test_another_stopwatch_or_version_is_changed():
    assert judge(facts(client_id=uuid.uuid4()), T0).state is RunState.CHANGED
    assert judge(facts(version=2), T0).state is RunState.CHANGED
    assert judge(facts(version=1), T0, version=3).state is RunState.CHANGED


def test_a_paused_stopwatch_is_paused_even_at_the_same_version():
    assert judge(facts(paused_at=T0 + timedelta(hours=1)), T0 + timedelta(hours=4)).state is RunState.PAUSED


def test_an_unanswered_idle_prompt_that_has_lapsed_counts_as_paused():
    prompted = T0 + timedelta(hours=2)
    f = facts(idle_pending=True, idle_prompted_at=prompted)
    assert (
        judge(f, prompted + timedelta(minutes=1)).state is RunState.NOT_DUE
    )  # still inside the two-minute answer time
    assert (
        judge(f, T0 + timedelta(hours=3)).state is RunState.PAUSED
    )  # an hour later the lazy settle would have paused it


def test_the_client_id_is_compared_as_text():
    assert judge(facts(client_id=str(CID)), T0 + timedelta(hours=3), client_id=CID).state is RunState.DUE
