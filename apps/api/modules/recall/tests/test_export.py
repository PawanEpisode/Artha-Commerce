import csv
import io
import json
import uuid
from datetime import date, timedelta

import pytest
from django.utils import timezone

from modules.recall.models import RecallReviewLog
from modules.recall.selectors import export as csv_export
from modules.recall.services import erasure, subscriptions

from .factories import OTHER, USER, make_card, make_item
from .w11 import published_deck

pytestmark = pytest.mark.django_db


def many_reviews(user, n, card=None):
    now = timezone.now() - timedelta(days=30)
    card = card or make_card(make_item(user), owner=user)
    RecallReviewLog.objects.bulk_create(
        RecallReviewLog(
            user_id=user, id=uuid.uuid4(), card_id=card.id, item_id=card.item_id, item_version_id=card.item_version_id,
            rating=3, reviewed_at=now + timedelta(seconds=i), received_at=now, local_date=date(2026, 9, 9),
        )
        for i in range(n)
    )  # fmt: skip
    return card


def parse(chunks):
    text = "".join(chunks)
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[1:-1], rows[-1]


def test_twenty_thousand_reviews_are_exported_complete_in_every_form():
    many_reviews(USER, 20_000)
    many_reviews(OTHER, 5)
    header, rows, footer = parse(csv_export.reviews_csv(USER))
    assert len(rows) == 20_000 and footer == ["#complete", "20000"]
    assert len({r[0] for r in rows}) == 20_000
    assert len(erasure.export_for_user(USER)["reviews"]) == 20_000


def test_csv_pages_continue_with_the_cursor_and_lose_nothing():
    many_reviews(USER, 25)
    seen, cursor = [], None
    for _ in range(10):
        _, rows, footer = parse(csv_export.reviews_csv(USER, cursor=cursor, limit=10))
        seen += [r[0] for r in rows]
        if footer[0] == "#complete":
            break
        assert footer[0] == "#next"
        cursor = footer[1]
    assert len(seen) == 25 and len(set(seen)) == 25 and footer == ["#complete", "5"]


def test_a_bad_cursor_is_a_400(api):
    assert api.c.get("/api/v1/recall/export/reviews.csv?cursor=not-a-cursor").status_code == 400


def test_exactly_a_page_long_history_ends_complete_not_next():
    many_reviews(USER, 10)
    _, rows, footer = parse(csv_export.reviews_csv(USER, limit=10))
    assert len(rows) == 10 and footer[0] == "#complete"


def test_spreadsheet_formulas_are_neutralised():
    assert csv_export.safe_cell("=1+1") == "'=1+1"
    assert csv_export.safe_cell("@SUM(A1)") == "'@SUM(A1)"
    assert csv_export.safe_cell("-2") == "'-2"
    assert csv_export.safe_cell("plain") == "plain" and csv_export.safe_cell(None) == ""
    own = make_item(USER, text="=HYPERLINK(1)")
    make_card(own, owner=USER)
    _, rows, _ = parse(csv_export.cards_csv(USER))
    assert "'=HYPERLINK(1)" in rows[0][-1] or "HYPERLINK" in rows[0][-1]
    assert not any(cell.startswith("=") for row in rows for cell in row)


def test_platform_card_text_is_not_exported(api):
    deck, items, _ = published_deck(2)
    subscriptions.subscribe(USER, deck.id)
    _, rows, footer = parse(csv_export.cards_csv(USER))
    assert len(rows) == 2 and all(r[3] == "platform" and r[-1] == "" for r in rows)
    body = erasure.export_for_user(USER)
    assert "Answer" not in json.dumps(body)


def test_her_own_card_text_is_exported():
    make_card(make_item(USER, text="My own question"), owner=USER)
    _, rows, _ = parse(csv_export.cards_csv(USER))
    assert rows[0][3] == "own" and "My own question" in rows[0][-1]


def test_endpoints_stream_csv_and_json_and_stay_open_with_the_flag_off(api, flag_off):
    many_reviews(USER, 3)
    res = api.c.get("/api/v1/recall/export/reviews.csv")
    assert res.status_code == 200 and res["Content-Type"].startswith("text/csv")
    assert res["Content-Disposition"].startswith("attachment")
    assert b"#complete,3" in b"".join(res.streaming_content)
    assert api.c.get("/api/v1/recall/export/cards.csv").status_code == 200
    j = api.get("/recall/export/")
    assert j.status_code == 200 and j.json_body["version"] == 1 and len(j.json_body["reviews"]) == 3


def test_only_her_own_rows_are_exported():
    many_reviews(OTHER, 4)
    _, rows, footer = parse(csv_export.reviews_csv(USER))
    assert rows == [] and footer == ["#complete", "0"]


def test_export_is_throttled(api):
    codes = [api.get("/recall/export/").status_code for _ in range(8)]
    assert codes[:6] == [200] * 6 and 429 in codes[6:]
