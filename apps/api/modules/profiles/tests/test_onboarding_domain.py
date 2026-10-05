"""The onboarding state machine as pure logic: facts over flags, versions, modes and optional steps."""

from types import SimpleNamespace

import pytest

from modules.profiles.domain import onboarding as flow
from modules.profiles.domain.onboarding import Facts, Status, StepState, Stored

SPECS = list(flow.BUILT_IN_STEPS)


def facts(*, name="", enrollment=False, minutes=None, confirmed=False, avatar="initials", stored=None, flags=True):
    return Facts(
        user_id="u",
        profile=SimpleNamespace(full_name=name, avatar_kind=avatar),
        enrollment=SimpleNamespace(planned_minutes=minutes) if enrollment else None,
        settings=SimpleNamespace(targets_confirmed_at="now" if confirmed else None),
        stored=stored or Stored(),
        flag=lambda _n: flags,
    )


def complete_facts(**extra):
    return facts(name="Aarav", enrollment=True, minutes=180, confirmed=True, **extra)


def test_a_brand_new_student_is_not_started_and_sees_the_first_mandatory_step():
    r = flow.resolve(SPECS, facts())
    assert (r.status, r.mode, r.next_step) == (Status.NOT_STARTED, "full", "profile")
    assert r.missing == ["profile", "course", "hours", "targets"]


def test_resume_goes_to_the_first_unsatisfied_mandatory_step_from_the_facts():
    r = flow.resolve(SPECS, facts(name="Aarav", enrollment=True, stored=Stored(started=True)))
    assert (r.status, r.next_step, r.missing) == (Status.IN_PROGRESS, "hours", ["hours", "targets"])


def test_hours_need_an_enrolment_and_minutes():
    assert flow.resolve(SPECS, facts(name="A", enrollment=True, minutes=None)).missing == ["hours", "targets"]
    assert "hours" not in flow.resolve(SPECS, facts(name="A", enrollment=True, minutes=90)).missing


def test_after_the_mandatory_steps_a_new_student_is_walked_through_unseen_optional_steps():
    r = flow.resolve(SPECS, complete_facts(stored=Stored(started=True)))
    assert r.missing == [] and r.next_step == "catchup" and r.status is Status.IN_PROGRESS
    seen = Stored(started=True, items={"catchup": {"state": "done"}})
    assert flow.resolve(SPECS, complete_facts(stored=seen)).next_step == "avatar"
    skipped = Stored(started=True, items={"catchup": {"state": "done"}, "avatar": {"state": "skipped"}})
    r = flow.resolve(SPECS, complete_facts(stored=skipped))
    assert r.next_step is None and r.missing == []  # nothing to show: the web calls complete


def test_a_chosen_avatar_satisfies_that_step_from_the_profile():
    r = flow.resolve(SPECS, complete_facts(avatar="preset", stored=Stored(started=True)))
    assert {s.key: s.state for s in r.steps}["avatar"] is StepState.DONE


def test_completed_only_when_the_facts_hold_and_the_version_matches():
    done = Stored(completed_version=2, started=True)
    assert flow.resolve(SPECS, complete_facts(stored=done)).status is Status.COMPLETED
    # Facts beat the flag: a completed student whose targets confirmation vanished must redo that step.
    gone = facts(name="A", enrollment=True, minutes=60, confirmed=False, stored=done)
    r = flow.resolve(SPECS, gone)
    assert r.status is Status.IN_PROGRESS and r.missing == ["targets"]


def test_a_backfilled_student_sees_only_what_is_missing_in_update_mode():
    stored = Stored(completed_version=1)
    r = flow.resolve(SPECS, facts(name="", enrollment=True, minutes=None, confirmed=False, stored=stored))
    assert r.mode == "update" and r.missing == ["profile", "hours", "targets"] and r.next_step == "profile"
    # No optional step is offered in update mode.
    r = flow.resolve(SPECS, complete_facts(stored=stored))
    assert r.next_step is None and r.missing == [] and r.status is Status.IN_PROGRESS


def test_a_version_bump_that_adds_a_mandatory_step_reprompts_only_that_step():
    new_step = flow.StepSpec("consent", 80, True, 3, lambda f: f.stored.state("consent") == "done")
    done = Stored(completed_version=2, started=True)
    r = flow.resolve([*SPECS, new_step], complete_facts(stored=done), required_version=3)
    assert r.status is Status.IN_PROGRESS and r.missing == ["consent"] and r.mode == "update"
    # At the old version the new step does not apply.
    assert flow.resolve([*SPECS, new_step], complete_facts(stored=done), required_version=2).status is Status.COMPLETED


def test_an_unavailable_step_is_hidden_and_never_blocks():
    r = flow.resolve(SPECS, facts(name="A", enrollment=True, minutes=60, flags=False))
    states = {s.key: s.state for s in r.steps}
    assert states["targets"] is StepState.UNAVAILABLE and "targets" not in r.missing


def test_skipped_state_is_reported_but_a_fact_wins_over_it():
    stored = Stored(started=True, items={"avatar": {"state": "skipped"}})
    assert {s.key: s.state for s in flow.resolve(SPECS, complete_facts(stored=stored)).steps}[
        "avatar"
    ] is StepState.SKIPPED
    both = complete_facts(avatar="upload", stored=stored)
    assert {s.key: s.state for s in flow.resolve(SPECS, both).steps}["avatar"] is StepState.DONE


@pytest.mark.parametrize("key", ["profile", "course", "hours", "targets"])
def test_mandatory_steps_are_marked_mandatory(key):
    assert next(s for s in SPECS if s.key == key).mandatory is True
