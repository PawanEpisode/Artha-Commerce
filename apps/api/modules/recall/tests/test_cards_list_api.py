import pytest

from modules.recall.models import RecallCard

from .factories import USER, make_deck
from .support import distinct, made, new

pytestmark = pytest.mark.django_db


def listing(api, query=""):
    res = api.get(f"/recall/cards/?{query}")
    assert res.status_code == 200, res.json_body
    return res.json_body


def test_the_list_is_the_students_own_newest_first_with_server_time(api, other_api):
    cards = [made(api, f) for f in distinct(3)]
    made(other_api, distinct(1)[0])
    body = listing(api)
    assert [c["id"] for c in body["items"]] == [c["id"] for c in reversed(cards)]
    assert body["next_cursor"] is None and body["server_time"].endswith("Z")
    assert [c["id"] for c in listing(api, "sort=oldest")["items"]] == [c["id"] for c in cards]


def test_cursor_pagination_walks_every_card_once(api):
    ids = [made(api, f)["id"] for f in distinct(5)]
    seen, cursor = [], ""
    while True:
        body = listing(api, f"limit=2&cursor={cursor}")
        seen += [c["id"] for c in body["items"]]
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert seen == list(reversed(ids)) and listing(api, "limit=100")["next_cursor"] is None
    assert api.get("/recall/cards/?cursor=garbage").status_code == 400
    assert api.get("/recall/cards/?limit=0").status_code == 400


def test_filters(api, ids):
    gst = made(api, distinct(1)[0], kind="pointer", chapter_id=ids["gst"], importance="mandatory")
    cloze = new(api, {"text_md": "{{c1::x}} and {{c2::y}}"}, kind="cloze").json_body["cards"][0]
    deck = make_deck(USER)
    api.post("/recall/cards/bulk/", {"ids": [gst["id"]], "action": "add_to_deck", "deck_id": str(deck.id)})
    assert [c["id"] for c in listing(api, f"chapter_id={ids['gst']}")["items"]] == [gst["id"]]
    assert [c["id"] for c in listing(api, "subject_key=taxation")["items"]] == [gst["id"]]
    assert len(listing(api, "kind=cloze")["items"]) == 2
    assert [c["id"] for c in listing(api, "tier=mandatory")["items"]] == [gst["id"]]
    assert [c["id"] for c in listing(api, f"deck_id={deck.id}")["items"]] == [gst["id"]]
    assert listing(api, "q=question")["items"][0]["id"] == gst["id"] and listing(api, "q=zzz")["items"] == []
    assert len(listing(api, "state=new")["items"]) == 3
    assert cloze["id"]


def test_state_and_status_filters(api):
    a, b, c, d = (made(api, f) for f in distinct(4))
    api.post(f"/recall/cards/{a['id']}/suspend/")
    RecallCard.objects.filter(pk=b["id"]).update(state=1, stability=1.0, due_at="2026-10-10T00:00:00Z")
    RecallCard.objects.filter(pk=c["id"]).update(leech=True, needs_recheck=True)
    api.delete(f"/recall/cards/{d['id']}/")

    def of(query):
        return {x["id"] for x in listing(api, query)["items"]}

    assert of("state=suspended") == {a["id"]} and of("state=learning") == {b["id"]}
    assert of("state=tricky") == {c["id"]} and of("state=recheck") == {c["id"]}
    assert of("state=new") == {c["id"]}  # the suspended one is not "new"; the learning one is not either
    assert of("") == {a["id"], b["id"], c["id"]}  # deleted cards are hidden by default
    assert of("status=deleted") == {d["id"]} and of("status=active") == {b["id"], c["id"]}


def test_invalid_filters_are_400(api):
    for query in ("kind=riddle", "tier=huge", "state=odd", "sort=random", "chapter_id=x", "status=gone"):
        assert api.get(f"/recall/cards/?{query}").status_code == 400, query


def test_another_students_deck_filter_finds_nothing(api, other_api):
    mine = made(api)
    deck = make_deck(USER)
    api.post("/recall/cards/bulk/", {"ids": [mine["id"]], "action": "add_to_deck", "deck_id": str(deck.id)})
    assert listing(other_api, f"deck_id={deck.id}")["items"] == []
