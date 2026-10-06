import pytest

from modules.notifications.domain.deeplinks import InvalidDeepLink, is_allowed, validate_deep_link


@pytest.mark.parametrize(
    "path", ["/app", "/app/focus", "/app/focus?n=1", "/app/revision/x", "/app/settings/notifications"]
)
def test_allowed(path):
    assert validate_deep_link(path) == path


@pytest.mark.parametrize(
    "path",
    [
        "",
        "app/focus",
        "//evil.com",
        "/\\evil.com",
        "https://evil.com",
        "/app/../admin",
        "/app/%2e%2e/admin",
        "/app/focus%2f..",
        "/appx",
        "/admin",
        "/app/focus\n",
        "/app/" + "a" * 200,
    ],
)
def test_rejected(path):
    assert not is_allowed(path)
    with pytest.raises(InvalidDeepLink):
        validate_deep_link(path)
