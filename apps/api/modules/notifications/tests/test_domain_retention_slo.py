"""The pure rules of W2.7: how long rows live (FR-N24) and when delivery counts as unhealthy (FR-N23)."""

from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications.domain import retention, slo

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def test_cutoffs_follow_the_prd_table():
    c = retention.cutoffs(NOW)
    assert c.deliveries == NOW - timedelta(days=90)
    assert c.notifications == NOW - timedelta(days=180)
    assert c.jobs == NOW - timedelta(days=30)
    assert c.revoked_devices == NOW - timedelta(days=30)
    assert retention.BATCH_SIZE == 1000


@pytest.mark.parametrize(
    "values, expected",
    [
        ([], None),
        ([7], 7),
        (list(range(1, 101)), 95),
        ([100, 1, 2, 3, 4, 5, 6, 7, 8, 9], 100),
        (list(range(1, 21)), 19),
    ],
)
def test_p95_is_nearest_rank(values, expected):
    assert slo.p95(values) == expected


def test_a_healthy_window_is_not_a_breach():
    v = slo.evaluate(accepted=98, failed=2, lateness_ms=[1200] * 98)
    assert v.accepted_ratio == 0.98 and v.p95_ms == 1200 and not v.breached


def test_too_many_failures_breach_the_acceptance_target():
    v = slo.evaluate(accepted=9, failed=1, lateness_ms=[900] * 9)
    assert v.ratio_breached and not v.lateness_breached and v.breached and v.accepted_ratio == 0.9


def test_slow_delivery_breaches_the_lateness_target():
    v = slo.evaluate(accepted=20, failed=0, lateness_ms=[1000] * 18 + [6000, 7000])
    assert v.p95_ms == 6000 and v.lateness_breached and not v.ratio_breached


def test_exactly_five_seconds_is_still_within_target():
    assert not slo.evaluate(accepted=10, failed=0, lateness_ms=[5000] * 10).breached


def test_a_tiny_window_is_noise_not_an_outage():
    v = slo.evaluate(accepted=1, failed=3, lateness_ms=[9000])
    assert v.attempts == 4 and not v.breached
    assert slo.evaluate(accepted=0, failed=5, lateness_ms=[]).breached


def test_no_attempts_means_no_verdict():
    v = slo.evaluate(accepted=0, failed=0, lateness_ms=[])
    assert v.accepted_ratio is None and v.p95_ms is None and not v.breached
