import pytest

from core import today_port


class _Result:
    def __init__(self, key, tasks):
        self.key, self.tasks = key, tasks


@pytest.fixture(autouse=True)
def _reset():
    saved = dict(today_port._providers)
    today_port.clear()
    yield
    today_port.clear()
    today_port._providers.update(saved)


def test_with_no_provider_there_is_nothing():
    assert today_port.collect("u", now=None) == []


def test_a_provider_answers_in_key_order_and_can_be_removed():
    today_port.register_task_provider("b", lambda u, *, now: _Result("b", [1]))
    today_port.register_task_provider("a", lambda u, *, now: _Result("a", [1, 2]))
    assert [r.key for r in today_port.collect("u", now=None)] == ["a", "b"]
    today_port.register_task_provider("a", None)
    assert today_port.registered_keys() == ["b"]


def test_empty_and_null_providers_are_left_out():
    today_port.register_task_provider("null", today_port.NullTaskProvider)
    today_port.register_task_provider("empty", lambda u, *, now: _Result("empty", []))
    assert today_port.collect("u", now=None) == []


def test_a_failing_provider_never_breaks_the_others():
    def boom(u, *, now):
        raise RuntimeError("down")

    today_port.register_task_provider("a", boom)
    today_port.register_task_provider("b", lambda u, *, now: _Result("b", [1]))
    assert [r.key for r in today_port.collect("u", now=None)] == ["b"]
