"""R2-W3 F: paste and CSV import (`POST /recall/cards/import/`): preview, atomic quota, replay, row cap, privacy."""

from __future__ import annotations

import logging
import uuid

import pytest

from modules.coverage.models import Enrollment
from modules.recall.models import RecallCard, RecallItem, RecallQuotaPlan

from .factories import USER
from .support import distinct, made, used

pytestmark = pytest.mark.django_db
URL = "/recall/cards/import/"


def send(api, *, text=None, rows=None, dry_run=False, client_id=None, **extra):
    body = {"client_id": str(client_id or uuid.uuid4()), "dry_run": dry_run, **extra}
    if text is not None:
        body["text"] = text
    if rows is not None:
        body["rows"] = rows
    return api.post(URL, body)


def lines(n, prefix="Import question"):
    return "\n".join(f"{prefix} {i}? :: answer {i}" for i in range(n))


def test_a_pasted_block_makes_one_pointer_per_line(api):
    res = send(api, text=lines(3))
    body = res.json_body
    assert res.status_code == 201 and (body["total"], body["created"], body["invalid"]) == (3, 3, 0)
    assert [r["status"] for r in body["rows"]] == ["created"] * 3 and all(r["card_id"] for r in body["rows"])
    card = RecallCard.objects.get(pk=body["rows"][0]["card_id"])
    assert card.item.origin == "import_csv" and card.item.shareable is False and card.state == 0
    assert used(USER) == 3


def test_the_preview_writes_nothing_and_says_what_is_wrong_per_row(api):
    text = "Good one? :: yes\nno back here\n" + lines(1, "Good one")
    res = send(api, text=text, dry_run=True)
    body = res.json_body
    assert res.status_code == 200 and body["dry_run"] is True
    assert [(r["line"], r["status"]) for r in body["rows"]] == [(1, "ok"), (2, "error"), (3, "ok")]
    assert body["rows"][1]["issues"][0]["code"] == "missing_back"
    assert (body["valid"], body["invalid"], body["created"]) == (2, 1, 0)
    assert RecallItem.objects.count() == 0 and used(USER) == 0


def test_the_real_call_creates_only_the_valid_rows(api):
    res = send(api, text="A1? :: a\nbroken line\nA2? :: b")
    body = res.json_body
    assert res.status_code == 201 and (body["created"], body["invalid"]) == (2, 1)
    assert [r["status"] for r in body["rows"]] == ["created", "error", "created"] and used(USER) == 2


def test_columns_with_kinds_and_rows_as_a_list(api):
    text = "kind,front,back,chapter\nformula,Gross total income,Sum of heads,\ndefinition,Assessee,A person liable to tax,\n"
    cols = send(api, text=text).json_body
    assert cols["created"] == 2
    listed = send(api, rows=[{"kind": "cloze", "front": "The {{c1::Act}} of 2013"}]).json_body
    assert listed["created"] == 1 and used(USER) == 3  # a one-deletion cloze is one face


def test_unknown_kinds_and_kinds_that_need_the_form_are_row_errors(api):
    res = send(api, rows=[{"kind": "poem", "front": "x", "back": "y"}, {"kind": "section", "front": "x", "back": "y"}])
    codes = [r["issues"][0]["code"] for r in res.json_body["rows"]]
    assert codes == ["unknown_kind", "kind_needs_form"] and res.json_body["created"] == 0


def test_a_one_field_kind_refuses_a_back(api):
    res = send(api, rows=[{"kind": "cloze", "front": "The {{c1::x}} thing", "back": "extra"}], dry_run=True)
    assert res.json_body["rows"][0]["issues"][0]["code"] == "back_not_used"


def test_text_that_breaks_a_field_rule_is_a_row_error_with_the_field_named(api):
    res = send(api, rows=[{"front": "Fine?", "back": "x" * 4001}, {"front": "Also fine?", "back": "ok"}])
    rows = res.json_body["rows"]
    assert rows[0]["status"] == "error" and rows[0]["issues"][0]["field"] == "answer_md"
    assert rows[0]["issues"][0]["code"] == "too_long" and rows[1]["status"] == "created"


def test_a_card_she_already_has_and_a_repeated_row_are_errors_not_duplicates(api):
    made(api, {"prompt_md": "Already mine?", "answer_md": "yes"})
    res = send(api, text="Already mine? :: yes\nTwice? :: a\nTwice? :: a")
    rows = res.json_body["rows"]
    assert [r["issues"][0]["code"] if r["issues"] else None for r in rows] == [
        "duplicate_card",
        None,
        "duplicate_in_import",
    ]
    assert res.json_body["created"] == 1


def test_the_whole_batch_is_one_quota_check_and_a_full_plan_creates_nothing(api):
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=4)
    made(api, distinct(1)[0])
    res = send(api, text=lines(4))  # 1 + 4 > 4
    assert res.status_code == 429 and res.json_body["error"]["code"] == "quota_exceeded"
    assert RecallCard.objects.count() == 1 and used(USER) == 1
    fits = send(api, text=lines(3))
    assert fits.status_code == 201 and used(USER) == 4  # the last slot is usable


def test_the_preview_reports_whether_the_valid_rows_fit(api):
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=2)
    quota = send(api, text=lines(3), dry_run=True).json_body["quota"]
    assert quota == {"room": 2, "needed": 3, "fits": False}


def test_a_replay_of_the_same_batch_creates_and_reserves_nothing_twice(api):
    batch = uuid.uuid4()
    first = send(api, text=lines(3), client_id=batch)
    again = send(api, text=lines(3), client_id=batch)
    assert first.json_body["created"] == 3
    assert again.status_code == 200 and (again.json_body["created"], again.json_body["existing"]) == (0, 3)
    assert RecallItem.objects.count() == 3 and used(USER) == 3


def test_the_row_limit_is_200_for_text_and_for_rows(api):
    ok = send(api, text=lines(200), dry_run=True)
    assert ok.status_code == 200 and ok.json_body["total"] == 200
    over = send(api, text=lines(201), dry_run=True)
    assert over.status_code == 422 and over.json_body["error"]["code"] == "import_too_large"
    rows = send(api, rows=[{"front": f"q{i}", "back": "a"} for i in range(201)], dry_run=True)
    assert rows.status_code == 422 and rows.json_body["error"]["code"] == "import_too_large"


def test_send_rows_or_text_never_both_or_neither(api):
    assert send(api).status_code == 400
    assert send(api, text="a :: b", rows=[{"front": "a", "back": "b"}]).status_code == 400


def test_chapters_by_id_key_and_default(api, ids, scheme):
    Enrollment.objects.create(user_id=USER, scheme=scheme, level=scheme.level)
    text = (
        "kind,front,back,chapter\n"
        f"pointer,By id?,a,{ids['gst']}\n"
        "pointer,By key?,a,taxation/gst-itc\n"
        "pointer,Unknown?,a,nope\n"
        "pointer,Default?,a,\n"
    )
    res = send(api, text=text, chapter_id=ids["gst"])
    rows = res.json_body["rows"]
    assert [r["status"] for r in rows] == ["created", "created", "error", "created"]
    assert rows[2]["issues"][0]["code"] == "unknown_chapter"
    chapters = {str(RecallCard.objects.get(pk=r["card_id"]).chapter_id) for r in rows if r["card_id"]}
    assert chapters == {ids["gst"]}


def test_an_unknown_default_chapter_is_a_422(api):
    res = send(api, text="a :: b", chapter_id=str(uuid.uuid4()))
    assert res.status_code == 422 and res.json_body["error"]["code"] == "unknown_chapter"


def test_another_students_import_is_not_a_duplicate_of_mine(api, other_api):
    send(other_api, text="Shared words? :: yes")
    assert send(api, text="Shared words? :: yes").json_body["created"] == 1


def test_card_text_never_reaches_the_logs(api, caplog):
    secret = "ZZ-secret-phrase-123"
    with caplog.at_level(logging.DEBUG):
        send(api, text=f"{secret}? :: {secret} answer")
        send(api, text="bad line " + secret)
    assert secret not in caplog.text


def test_rows_carry_short_one_line_excerpts_for_the_preview_table(api):
    long = "word " * 100
    res = send(api, rows=[{"front": "Line one\nline two", "back": long}], dry_run=True)
    row = res.json_body["rows"][0]
    assert row["front"] == "Line one line two" and len(row["back"]) == 120 and row["back"].endswith("…")
