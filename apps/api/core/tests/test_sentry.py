from core.sentry import before_send


def event(url: str):
    return {
        "request": {
            "url": url,
            "data": {"t": "secret.jwt.token", "path": "/app"},
            "cookies": {"a": "b"},
            "headers": {"Authorization": "Bearer x", "User-Agent": "ua"},
        }
    }


def test_the_last_visit_body_and_credentials_are_dropped():
    out = before_send(event("https://api.example.com/api/v1/me/last-visit/?x=1"))
    assert "data" not in out["request"] and "cookies" not in out["request"]
    assert out["request"]["headers"] == {"User-Agent": "ua"}


def test_other_requests_are_left_alone():
    out = before_send(event("https://api.example.com/api/v1/me/"))
    assert out["request"]["data"]["path"] == "/app"


def test_events_without_a_request_pass_through():
    assert before_send({"message": "hi"}) == {"message": "hi"}
