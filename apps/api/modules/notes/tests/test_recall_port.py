"""The recall port (slice 19): absent state, a registered provider, idempotency, ownership, and the pure card rules."""

import uuid

import pytest

from core import recall_port
from core.recall_port import CardRef, NullRecallProvider, SourceRef
from modules.notes.domain import recall_card
from modules.notes.domain.legend import DEFAULT_LEGEND
from modules.notes.models import Annotation

from .marks_support import USER, create, new_document

# --- pure --------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("color", "kind"),
    [("g", "formula"), ("b", "rule"), ("p", "doubt"), ("o", "example"), ("y", "fact"), (None, "fact"), ("i1", "fact")],
)
def test_the_kind_follows_the_colours_default_meaning(color, kind):
    assert recall_card.card_kind_for_color(color, DEFAULT_LEGEND) == kind


def test_a_renamed_legend_is_read_by_name_first_then_by_colour():
    legend = {**DEFAULT_LEGEND, "y": "  formula ", "g": "Key idea", "p": "section OR rule"}
    assert (
        recall_card.card_kind_for_color("y", legend) == "formula"
    )  # the student's name wins over the colour's default
    assert recall_card.card_kind_for_color("g", legend) == "formula"  # an unknown name falls back to the colour
    assert recall_card.card_kind_for_color("p", legend) == "rule"
    assert recall_card.card_kind_for_color("o", None) == "example"


def test_front_and_back_of_a_card():
    assert recall_card.front_prompt("formula", chapter_name="GST: Input Tax Credit", page=12) == (
        "State the formula from GST: Input Tax Credit (page 12)."
    )
    assert recall_card.front_prompt("fact", chapter_name=None, page=1) == "Recall this point from your PDF (page 1)."
    assert recall_card.back_text(" quote ", "comment") == "quote\n\ncomment"
    assert recall_card.back_text(None, " only comment ") == "only comment" and recall_card.back_text("", "") == ""


# --- the port ----------------------------------------------------------------------------------------------------------------


class FakeRecall:
    """What F-15 will be: idempotent on (student, source id, kind), and on the client id."""

    def __init__(self):
        self.cards: dict[tuple, uuid.UUID] = {}
        self.calls: list[dict] = []

    def create_card_from_source(
        self, user_id, *, kind, front_md, back_md, chapter_id=None, topic_id=None, source, client_id
    ):
        self.calls.append(
            {"user": user_id, "kind": kind, "front": front_md, "back": back_md, "chapter": chapter_id, "source": source}
        )
        key = (str(user_id), source.ref_id, kind)
        if key in self.cards:
            return CardRef(self.cards[key], True)
        self.cards[key] = uuid.uuid4()
        return CardRef(self.cards[key], False)

    def cards_for_source(self, user_id, ref_ids):
        return {r: CardRef(c) for (u, r, _), c in self.cards.items() if r in ref_ids and u == str(user_id)}


@pytest.fixture(autouse=True)
def _no_provider():
    recall_port.register_recall_provider(None)
    yield
    recall_port.register_recall_provider(None)


@pytest.fixture
def provider():
    fake = FakeRecall()
    recall_port.register_recall_provider(fake)
    return fake


def test_the_registry_is_absent_until_a_provider_registers():
    assert recall_port.get_recall_provider() is None
    recall_port.register_recall_provider(NullRecallProvider())
    assert recall_port.get_recall_provider() is None  # the explicit null state counts as absent
    fake = FakeRecall()
    recall_port.register_recall_provider(fake)
    assert recall_port.get_recall_provider() is fake and isinstance(fake, recall_port.RecallProvider)


@pytest.mark.django_db
def test_without_a_provider_the_card_is_503_and_the_capability_is_off(api):
    mark = create(api, new_document(), quote_exact="the rule", comment="why")
    res = api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4())})
    assert res.status_code == 503 and res.json_body["error"]["code"] == "recall_unavailable"
    settings = api.get("/notes/settings/").json_body
    assert settings["capabilities"] == {"recall": False, "ocr_hindi": True, "ai_ocr": False}
    assert (
        api.get(f"/notes/documents/{mark['document_id']}/annotations/").json_body["items"][0]["recall_card_id"] is None
    )
    assert api.post(f"/notes/annotations/{mark['id']}/card/", {}).status_code == 400  # client_id is required


@pytest.mark.django_db
def test_with_a_provider_a_card_is_made_once_and_cached_on_the_mark(api, other_api, provider, scheme):
    from modules.notes.services import links
    from modules.syllabus.models import Chapter

    gst = Chapter.objects.get(key="gst-itc")
    doc = new_document(**links.link_columns(gst.id))
    mark = create(api, doc, color="g", quote_exact="ITC = output tax less input tax", comment="Section 16")
    assert api.get("/notes/settings/").json_body["capabilities"]["recall"] is True

    first = api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4())})
    assert first.status_code == 200 and first.json_body["existing"] is False
    card_id = first.json_body["card_id"]
    call = provider.calls[0]
    assert call["kind"] == "formula" and call["back"] == "ITC = output tax less input tax\n\nSection 16"
    assert call["front"] == "State the formula from GST: Input Tax Credit (page 1)." and call["chapter"] == gst.id
    assert call["source"] == SourceRef("notes", "annotation", uuid.UUID(mark["id"]))
    assert str(call["user"]) == str(USER)

    second = api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4())})
    assert (
        second.json_body == {"card_id": card_id, "existing": True} and len(provider.calls) == 1
    )  # served from the cached id
    assert str(Annotation.objects.get(pk=mark["id"]).recall_card_id) == card_id
    synced = api.get(f"/notes/documents/{doc.id}/annotations/").json_body["items"][0]
    assert (
        synced["recall_card_id"] == card_id and synced["seq"] == 2 and synced["rev"] == 1
    )  # other devices see it, no new rev

    other_kind = api.post(
        f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4()), "kind": "definition"}
    )
    assert other_kind.json_body["existing"] is False and other_kind.json_body["card_id"] != card_id
    again = api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4()), "kind": "definition"})
    assert again.json_body["existing"] is True and again.json_body["card_id"] == other_kind.json_body["card_id"]
    assert str(Annotation.objects.get(pk=mark["id"]).recall_card_id) == card_id  # the first card stays the cached one

    # a mark that is another student's is a 404, never a card
    assert other_api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4())}).status_code == 404
    assert len(provider.calls) == 3


@pytest.mark.django_db
def test_a_mark_without_text_is_422_and_a_deleted_mark_is_404(api, provider):
    from .marks_support import remove

    bare = create(api, new_document(), kind="area")
    res = api.post(f"/notes/annotations/{bare['id']}/card/", {"client_id": str(uuid.uuid4())})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "no_text" and provider.calls == []
    comment_only = create(api, new_document(), kind="sticky", comment="remember this", color="p")
    ok = api.post(f"/notes/annotations/{comment_only['id']}/card/", {"client_id": str(uuid.uuid4())})
    assert ok.status_code == 200 and provider.calls[0]["kind"] == "doubt"
    remove(api, comment_only["id"], base_rev=1)
    assert (
        api.post(f"/notes/annotations/{comment_only['id']}/card/", {"client_id": str(uuid.uuid4())}).status_code == 404
    )
