"""The fatigue rule (W3.7, FR-N34): five unclicked pushes in a row, over three local days, at most once per 30 days."""

from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications.domain.digest import DigestFacts, digest_lines, worth_sending
from modules.notifications.domain.fatigue import PushFact, should_offer

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
TZ = "Asia/Kolkata"


def pushes(*days_ago: float, clicked: tuple[int, ...] = ()) -> list[PushFact]:
    """Newest first; `clicked` names positions in that order."""
    return [PushFact(NOW - timedelta(days=d), i in clicked) for i, d in enumerate(days_ago)]


def offer(recent, *, offered_at=None, digest_on=False, now=NOW, tz=TZ):
    return should_offer(recent, offered_at=offered_at, digest_on=digest_on, now=now, tz=tz)


def test_five_unclicked_over_three_days_offers():
    assert offer(pushes(0, 0.5, 1, 1.5, 2))


def test_four_are_not_enough():
    assert not offer(pushes(0, 1, 2, 3))


def test_only_the_last_five_count_so_an_old_click_does_not_matter():
    assert offer(pushes(0, 1, 2, 3, 4, 5, clicked=(5,)))


@pytest.mark.parametrize("position", range(5))
def test_a_click_on_any_of_the_five_resets_the_run(position):
    assert not offer(pushes(0, 1, 2, 3, 4, clicked=(position,)))


def test_two_days_are_not_enough_three_are():
    assert not offer(pushes(0, 0.1, 0.2, 1, 1.1))
    assert offer(pushes(0, 0.1, 1, 1.1, 2))


def test_days_are_the_students_local_days():
    # 18:00 and 19:00 UTC on 5 Oct are 23:30 on 5 Oct and 00:30 on 6 Oct in India: two local days, one UTC day.
    base = datetime(2026, 10, 5, 18, 0, tzinfo=UTC)
    recent = [
        PushFact(base + timedelta(days=1, hours=1), False),  # 7 Oct 00:30 local
        PushFact(base + timedelta(days=1), False),  # 6 Oct 23:30 local
        PushFact(base + timedelta(hours=1, minutes=30), False),  # 6 Oct 01:00 local
        PushFact(base + timedelta(hours=1), False),  # 6 Oct 00:30 local
        PushFact(base, False),  # 5 Oct 23:30 local
    ]
    now = base + timedelta(days=2)
    assert offer(recent, now=now, tz=TZ)  # 5, 6 and 7 October in India
    assert not offer(recent, now=now, tz="UTC")  # only 5 and 6 October in UTC


def test_a_day_with_a_daylight_saving_change_is_still_one_day():
    # Europe/London leaves summer time on 25 Oct 2026 at 01:00 UTC.
    recent = [
        PushFact(datetime(2026, 10, 27, 9, 0, tzinfo=UTC), False),
        PushFact(datetime(2026, 10, 25, 23, 30, tzinfo=UTC), False),  # 25 Oct 23:30 GMT
        PushFact(datetime(2026, 10, 25, 0, 30, tzinfo=UTC), False),  # 25 Oct 01:30 BST
        PushFact(datetime(2026, 10, 24, 22, 30, tzinfo=UTC), False),  # 24 Oct 23:30 BST
        PushFact(datetime(2026, 10, 24, 12, 0, tzinfo=UTC), False),
    ]
    now = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
    assert offer(recent, now=now, tz="Europe/London")  # 24, 25 and 27 October
    assert not offer(recent[1:4] + recent[1:3], now=now, tz="Europe/London")  # only 24 and 25


def test_once_per_30_days():
    recent = pushes(0, 1, 2, 3, 4)
    assert not offer(recent, offered_at=NOW - timedelta(days=29, hours=23))
    assert offer(recent, offered_at=NOW - timedelta(days=30))


def test_never_while_on_the_digest():
    assert not offer(pushes(0, 1, 2, 3, 4), digest_on=True)


@pytest.mark.parametrize(
    "facts, lines, link",
    [
        (DigestFacts(3, 0, None), ["3 updates in your inbox."], "/app/notifications"),
        (DigestFacts(1, 2, None), ["2 chapters due for revision.", "1 update in your inbox."], "/app/notifications"),
        (DigestFacts(0, 1, 7), ["7 days to your exam.", "1 chapter due for revision."], "/app/revision"),
        (DigestFacts(0, 0, 1), ["Your exam is tomorrow."], "/app"),
    ],
)
def test_digest_words_and_link(facts, lines, link):
    context = {"unread": facts.unread, "due_count": facts.due_count, "milestone": facts.milestone}
    assert digest_lines(context) == (lines, link)
    assert worth_sending(facts)


def test_a_day_with_nothing_sends_no_digest():
    assert not worth_sending(DigestFacts(0, 0, None))
