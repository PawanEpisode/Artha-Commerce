"""The provider runner: timeouts, failures, switches and limits never stop the plan (ERD 3.2, PRD 4.2)."""

import time
import uuid

import pytest

from modules.today import registry, runner
from modules.today.models import ProviderConfig
from modules.today.registry import EnrollmentCtx, PlanContext, ProviderResult
from modules.today.runner import run_providers

from .helpers import TODAY, candidate, register_fake

pytestmark = pytest.mark.django_db


def ctx(**over):
    fields = dict(
        user_id=uuid.uuid4(),
        local_date=TODAY,
        tz="Asia/Kolkata",
        enrollment=EnrollmentCtx(uuid.uuid4(), uuid.uuid4(), "ca", "intermediate", None, None, None),
        days_to_exam=40,
        phase="consolidate",
        papers=(),
        done_keys=frozenset(),
        suppressed_keys=frozenset(),
        budget_minutes=60,
        comeback=False,
        seed=1,
        is_preview=False,
    )
    fields.update(over)
    return PlanContext(**fields)


@pytest.fixture(autouse=True)
def _only_fakes():
    registry.clear()


def outcome(result, name):
    return next(o for o in result.outcomes if o.spec.name == name)


def test_a_provider_that_answers_is_ok_and_reported():
    register_fake("fake.one", [candidate("a"), candidate("b")])
    result = run_providers(ctx())
    assert outcome(result, "fake.one").status == "ok" and not result.partial
    assert result.status_map()["fake.one"]["n"] == 2


def test_a_provider_that_raises_makes_the_plan_partial_and_leaves_the_others_alone():
    def boom(request):
        raise RuntimeError("database is on fire")

    register_fake("fake.boom", boom)
    register_fake("fake.fine", [candidate("a")], kinds=[registry.KindSpec("fine_k", "practice", "mcq", "x", 10)])
    result = run_providers(ctx())
    assert outcome(result, "fake.boom").status == "error"
    assert outcome(result, "fake.fine").status == "ok"
    assert result.partial is True


def test_a_wrong_return_type_is_an_error_not_a_crash():
    registry.register_task_provider(
        "fake.odd",
        lambda request: ["not", "a", "result"],
        kinds=[registry.KindSpec("odd_k", "practice", "mcq", "x", 10)],
        label="Odd",
    )
    assert outcome(run_providers(ctx()), "fake.odd").status == "error"


def test_a_slow_provider_times_out_in_inline_mode_too():
    def slow(request):
        time.sleep(0.15)
        return [candidate("late")]

    register_fake("fake.slow", slow, timeout_ms=100)
    result = run_providers(ctx())
    assert outcome(result, "fake.slow").status == "timeout" and result.partial
    assert outcome(result, "fake.slow").result is None


def test_a_slow_provider_is_abandoned_in_parallel_mode(settings):
    settings.TODAY_PROVIDER_PARALLEL = True

    def slow(request):
        time.sleep(0.6)
        return [candidate("late")]

    register_fake("fake.slow", slow, timeout_ms=100)
    register_fake("fake.fast", [candidate("a")], kinds=[registry.KindSpec("fast_k", "practice", "mcq", "x", 10)])
    started = time.monotonic()
    result = run_providers(ctx())
    assert time.monotonic() - started < 0.5  # waited for the timeout, not for the slow provider
    assert outcome(result, "fake.slow").status == "timeout"
    assert outcome(result, "fake.fast").status == "ok"


def test_candidates_beyond_max_candidates_are_cut():
    register_fake("fake.many", [candidate(f"k{n}") for n in range(10)], max_candidates=3)
    assert len(outcome(run_providers(ctx()), "fake.many").result.candidates) == 3


def test_the_request_carries_the_limit_and_deadline():
    calls = register_fake("fake.one", [], max_candidates=7, timeout_ms=250)
    run_providers(ctx())
    assert (calls[0].limit, calls[0].deadline_ms) == (7, 250)


def test_operator_config_disables_reweights_and_overrides_limits():
    calls = register_fake("fake.one", [candidate("a")], max_candidates=7, timeout_ms=250)
    ProviderConfig.objects.create(provider="fake.one", weight_pct=150, max_candidates=2, timeout_ms=900)
    runner.clear_config_cache()
    result = run_providers(ctx())
    assert (calls[0].limit, calls[0].deadline_ms) == (2, 900)
    assert outcome(result, "fake.one").weight_pct == 150

    ProviderConfig.objects.filter(provider="fake.one").update(enabled=False)
    runner.clear_config_cache()
    off = run_providers(ctx())
    assert outcome(off, "fake.one").status == "disabled" and len(calls) == 1 and not off.partial


def test_config_is_cached_for_a_minute(django_assert_num_queries):
    register_fake("fake.one", [])
    runner.clear_config_cache()
    run_providers(ctx())
    with django_assert_num_queries(0):
        run_providers(ctx())


def test_a_provider_behind_a_flag_is_off_when_the_flag_is_off(monkeypatch):
    calls = register_fake("fake.flagged", [candidate("a")], flag="some_flag")
    monkeypatch.setattr(runner, "flag_enabled", lambda name, user_id, **kw: False)
    result = run_providers(ctx())
    assert outcome(result, "fake.flagged").status == "off" and not calls and not result.partial


def test_enabled_for_can_skip_a_student_and_a_broken_check_is_an_error():
    register_fake("fake.skip", [candidate("a")], enabled_for=lambda user_id: False)
    assert outcome(run_providers(ctx()), "fake.skip").status == "skipped"

    def broken(user_id):
        raise ValueError("nope")

    register_fake(
        "fake.broken",
        [candidate("a")],
        enabled_for=broken,
        kinds=[registry.KindSpec("b_k", "practice", "mcq", "x", 10)],
    )
    result = run_providers(ctx())
    assert outcome(result, "fake.broken").status == "error" and result.partial


def test_outcomes_come_in_provider_name_order():
    register_fake("fake.zeta", [], kinds=[registry.KindSpec("z_k", "practice", "mcq", "x", 10)])
    register_fake("fake.alpha", [], kinds=[registry.KindSpec("a_k", "practice", "mcq", "x", 10)])
    assert [o.spec.name for o in run_providers(ctx()).outcomes] == ["fake.alpha", "fake.zeta"]


def test_a_backlog_is_kept_in_the_status_map():
    register_fake(
        "fake.backlog",
        ProviderResult(
            candidates=[candidate("a")],
            backlog_count=35,
            backlog_label="revisions are overdue",
            backlog_link=registry.DeepLink("/app/revision"),
        ),
    )
    entry = run_providers(ctx()).status_map()["fake.backlog"]
    assert entry["backlog"] == {
        "count": 35,
        "label": "revisions are overdue",
        "link": {"path": "/app/revision", "search": {}},
    }
