"""The API's event schema and the web's copy are the same file (audit AUD-011: no drift between the two)."""

from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1] / "domain" / "event_schema.json"
WEB = Path(__file__).resolve().parents[4] / "web" / "src" / "modules" / "today" / "lib" / "event-schema.json"


def test_the_web_copy_is_byte_identical():
    if not WEB.exists():
        pytest.skip("the web app is not in this checkout")
    assert WEB.read_bytes() == API.read_bytes(), (
        "event_schema.json (api) and event-schema.json (web) drifted: copy one over the other"
    )
