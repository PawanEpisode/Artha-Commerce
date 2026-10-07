from types import SimpleNamespace

from core.http import request_has_secret


def _req(**headers):
    return SimpleNamespace(headers=headers)


def test_header_or_bearer_matches():
    assert request_has_secret(_req(**{"X-Tick": "s"}), "s", "X-Tick")
    assert request_has_secret(_req(Authorization="Bearer s"), "s", "X-Tick")


def test_wrong_missing_or_unset_never_matches():
    assert not request_has_secret(_req(**{"X-Tick": "x"}), "s", "X-Tick")
    assert not request_has_secret(_req(), "s", "X-Tick")
    assert not request_has_secret(_req(Authorization="Basic s"), "s", "X-Tick")
    assert not request_has_secret(_req(**{"X-Tick": ""}), "", "X-Tick")  # an unset secret refuses everyone
    assert not request_has_secret(_req(Authorization="Bearer "), "", "X-Tick")
