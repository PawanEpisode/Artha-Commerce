import json
import logging

import pytest

from core.privacy import MaskRecallIds
from core.sentry import before_send, before_send_transaction


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


def test_the_notification_button_body_is_dropped():
    out = before_send(event("https://api.example.com/api/v1/notifications/actions/"))
    assert "data" not in out["request"] and "cookies" not in out["request"]


def test_a_key_named_token_is_filtered_anywhere_in_the_body_and_in_frame_variables():
    out = before_send(
        {
            "request": {"url": "https://api.example.com/api/v1/other/", "data": {"a": {"token": "s3cret"}, "b": [1]}},
            "exception": {"values": [{"stacktrace": {"frames": [{"vars": {"token": "s3cret", "action": "pause"}}]}}]},
        }
    )
    assert out["request"]["data"] == {"a": {"token": "[Filtered]"}, "b": [1]}
    assert out["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"] == {
        "token": "[Filtered]",
        "action": "pause",
    }
    assert "s3cret" not in str(out)


# --- recall (F-15): nothing a recall request carries reaches Sentry -------------------------------------------------------
CARD = "6f1c2a9e-3b4d-4c5e-8f60-7a8b9c0d1e2f"
TEXT = "What is the exact wording of section 17(5)? my private note"


def recall_event(url=f"https://api.example.com/api/v1/recall/cards/{CARD}/?q={TEXT}", **extra):
    return {
        "request": {
            "url": url,
            "query_string": f"q={TEXT}",
            "data": {"fields": {"prompt_md": TEXT}, "card_id": CARD, "events": [{"id": CARD, "rating": 3}]},
            "cookies": {"a": "b"},
            "headers": {"Authorization": "Bearer x", "User-Agent": "ua"},
        },
        "transaction": f"/api/v1/recall/cards/{CARD}/",
        "message": f"card {CARD} failed",
        "breadcrumbs": {"values": [{"category": "query", "message": TEXT}]},
        "extra": {"fields": TEXT},
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": f"bad card {CARD}",
                    "stacktrace": {"frames": [{"module": "modules.recall.services.cards", "vars": {"fields": TEXT}}]},
                }
            ]
        },
        **extra,
    }


@pytest.mark.parametrize(
    "path",
    [
        "cards/",
        f"cards/{CARD}/",
        f"cards/{CARD}/reviews/",
        "cards/from-selection/",
        "cards/bulk/",
        "reviews/",
        "reviews/batch/",
        "reviews/undo/",
        "queue/",
        "pack/",
        "forgotten/",
        "stats/summary/",
        "settings/",
        "decks/library/",
        f"decks/{CARD}/subscribe/",
        f"items/{CARD}/report/",
        "export/",
        "export/cards.csv",
        "erase/",
        "internal/tick/",
    ],
)
def test_no_recall_route_sends_text_ids_or_bodies(path):
    out = before_send(recall_event(f"https://api.example.com/api/v1/recall/{path}?q={TEXT}"))
    dump = json.dumps(out)
    assert TEXT not in dump and CARD not in dump
    request = out["request"]
    assert "data" not in request and "cookies" not in request and "query_string" not in request
    assert "?" not in request["url"] and request["url"].startswith("https://api.example.com/api/v1/recall/")
    assert request["headers"] == {"User-Agent": "ua"}
    assert "breadcrumbs" not in out and "extra" not in out
    assert out["exception"]["values"][0]["stacktrace"]["frames"][0].get("vars") is None


def test_a_recall_event_without_a_url_is_found_by_its_route_or_its_code():
    """Under the Django test client (and some servers) the request has no URL: the route and the frames still identify recall."""
    by_route = recall_event()
    del by_route["request"]["url"]
    by_code = recall_event()
    del by_code["request"]["url"]
    by_code["transaction"] = "unrelated"
    for event in (by_route, by_code):
        dump = json.dumps(before_send(event))
        assert TEXT not in dump and CARD not in dump


def test_performance_events_are_scrubbed_the_same_way():
    event = recall_event(spans=[{"description": f"SELECT {CARD}", "data": {"x": TEXT}}])
    dump = json.dumps(before_send_transaction(event))
    assert TEXT not in dump and CARD not in dump


def test_other_routes_keep_their_context():
    event = {
        "request": {"url": "https://api.example.com/api/v1/me/", "data": {"a": 1}},
        "breadcrumbs": {"values": [1]},
        "extra": {"b": 2},
    }
    out = before_send(event)
    assert out["request"]["data"] == {"a": 1} and out["breadcrumbs"] == {"values": [1]} and out["extra"] == {"b": 2}


def test_an_error_raised_in_recall_code_drops_every_frame_variable_whatever_started_it():
    event = {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {"module": "modules.recall.worker", "vars": {"fields": TEXT}},
                            {"module": "x", "vars": {"a": 1}},
                        ]
                    }
                }
            ]
        }
    }
    frames = before_send(event)["exception"]["values"][0]["stacktrace"]["frames"]
    assert all("vars" not in frame for frame in frames)


def test_the_request_log_line_of_a_recall_path_carries_no_card_id():
    record = logging.LogRecord(
        "django.request", logging.WARNING, "x", 1, "Conflict: %s", (f"/api/v1/recall/cards/{CARD}/",), None
    )
    record.request = object()
    assert MaskRecallIds().filter(record)
    assert record.getMessage() == "Conflict: /api/v1/recall/cards/{id}/" and record.request is None
    other = logging.LogRecord(
        "django.request", logging.WARNING, "x", 1, "Conflict: %s", (f"/api/v1/notes/{CARD}/",), None
    )
    MaskRecallIds().filter(other)
    assert CARD in other.getMessage()
