import pytest

from core import feature_flags
from modules.tracking.tests.conftest import (  # noqa: F401 - shared two-student JSON clients and a seeded scheme
    _fresh_throttle_counters,
    api,
    ids,
    other_api,
    scheme,
)


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    """`recall_system` fails closed, so the tests switch it on for everyone; a test that needs it off uses `flag_off`."""
    feature_flags.clear_flag_cache()
    monkeypatch.setattr(feature_flags, "_lookup", lambda name, distinct_id: True)
    yield
    feature_flags.clear_flag_cache()


@pytest.fixture
def flag_off(monkeypatch):
    monkeypatch.setattr(feature_flags, "_lookup", lambda name, distinct_id: False)
