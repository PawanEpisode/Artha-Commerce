import pytest

from modules.notifications.domain.push_hosts import EndpointRejected, is_allowed_endpoint, validate_endpoint

ALLOWED = [
    "https://fcm.googleapis.com/fcm/send/abc",
    "https://updates.push.services.mozilla.com/wpush/v2/abc",
    "https://web.push.apple.com/QGx0",
    "https://17.push.apple.com/3/device/abc",
    "https://wns2-par02p.notify.windows.com/w/?token=abc",
    "https://FCM.GoogleAPIs.com/fcm/send/abc",  # host names are case-insensitive
    "https://fcm.googleapis.com:443/fcm/send/abc",
]

REJECTED = [
    # scheme
    "http://fcm.googleapis.com/fcm/send/abc",
    "ftp://fcm.googleapis.com/x",
    "//fcm.googleapis.com/x",
    "fcm.googleapis.com/x",
    "javascript:alert(1)",
    "file:///etc/passwd",
    # lookalike hosts
    "https://fcm.googleapis.com.evil.example/x",
    "https://evilfcm.googleapis.com/x",
    "https://fcm-googleapis.com/x",
    "https://notfcm.googleapis.com.evil.com/x",
    "https://push.apple.com/x",  # the wildcard needs a label in front
    "https://.push.apple.com/x",
    "https://evilpush.apple.com/x",
    "https://evil.com/.push.apple.com",
    "https://evil.com/?h=fcm.googleapis.com",
    "https://evil.com#@fcm.googleapis.com",
    "https://updates.push.services.mozilla.com.evil.com/x",
    "https://notify.windows.com/x",
    "https://windows.com/x",
    "https://fcm.googleapis.com./x",  # trailing dot: a different name for the resolver and our comparison
    # userinfo tricks
    "https://fcm.googleapis.com@evil.example/x",
    "https://user:pass@fcm.googleapis.com/x",
    "https://fcm.googleapis.com:443@evil.example/x",
    "https://evil.example\\@fcm.googleapis.com/x",
    "https://fcm.googleapis.com\\.evil.example/x",
    # ports
    "https://fcm.googleapis.com:8443/x",
    "https://fcm.googleapis.com:80/x",
    "https://fcm.googleapis.com:99999/x",
    "https://fcm.googleapis.com:abc/x",
    # IP literals and internal names
    "https://127.0.0.1/x",
    "https://169.254.169.254/latest/meta-data",
    "https://[::1]/x",
    "https://[::ffff:127.0.0.1]/x",
    "https://2130706433/x",
    "https://localhost/x",
    "https://metadata.google.internal/x",
    # unicode and control characters
    "https://fcm.googleapis.com。evil.com/x",
    "https://ｆcm.googleapis.com/x",
    "https://fcm.googleapis.com/x y",
    "https://fcm.googleapis.com/x\n",
    "https://fcm.googleapis.com/\x00",
    " https://fcm.googleapis.com/x",
    # shape
    "",
    "https://",
    "https:///x",
    None,
    123,
    ["https://fcm.googleapis.com/x"],
    "https://fcm.googleapis.com/" + "a" * 2100,
]


@pytest.mark.parametrize("url", ALLOWED)
def test_allowed(url):
    assert validate_endpoint(url) == url
    assert is_allowed_endpoint(url)


@pytest.mark.parametrize("url", REJECTED)
def test_rejected(url):
    with pytest.raises(EndpointRejected):
        validate_endpoint(url)
    assert not is_allowed_endpoint(url)
