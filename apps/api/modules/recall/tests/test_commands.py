"""The three management commands."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from modules.recall.models import RecallCard, RecallDailyRollup
from modules.recall.services import reviews

from .w5 import ME, card, days, ev, folded, memory_of_row, minutes, rollup_snapshot

pytestmark = pytest.mark.django_db


def run(name, *args):
    out = StringIO()
    call_command(name, *args, stdout=out)
    return out.getvalue()


def test_recall_replay_repairs_drifted_cards_and_is_quiet_on_good_ones():
    c = card()
    for i in range(3):
        reviews.submit_review(ME, ev(c, 3, minutes(i * 60)), now=days(1))
    good = memory_of_row(c)
    assert "1 changed" not in run("recall_replay", "--user", str(ME))
    RecallCard.objects.filter(pk=c.pk).update(stability=50.0, reps=9)
    assert "replayed 1 cards, 1 changed" in run("recall_replay", "--user", str(ME), "--card", str(c.id))
    assert memory_of_row(c) == good == folded(c)
    assert "0 changed" in run("recall_replay", "--all")


def test_recall_replay_needs_a_target():
    with pytest.raises(CommandError):
        call_command("recall_replay")
    with pytest.raises(CommandError):
        call_command("recall_replay", "--card", "x")


def test_recall_rebuild_rollups_repairs_the_counters():
    c = card()
    for i in range(3):
        reviews.submit_review(ME, ev(c, 3, minutes(i * 60)), now=days(1))
    good = rollup_snapshot()
    RecallDailyRollup.objects.filter(user_id=ME).update(good=99, new_cards=0)
    run("recall_rebuild_rollups", "--user", str(ME))
    assert rollup_snapshot() == good
    run("recall_rebuild_rollups", "--user", str(ME), "--from", "2026-10-01")
    assert rollup_snapshot() == good
    with pytest.raises(CommandError):
        call_command("recall_rebuild_rollups", "--user", str(ME), "--from", "soon")


def test_recall_check_vectors_passes_on_the_committed_vectors_and_fails_on_a_changed_domain(monkeypatch):
    assert "vectors match" in run("recall_check_vectors")
    from modules.recall.domain import fsrs6

    monkeypatch.setattr(fsrs6, "fuzz_unit", lambda card_id, reps: 0.123)
    with pytest.raises(CommandError):
        call_command("recall_check_vectors")
