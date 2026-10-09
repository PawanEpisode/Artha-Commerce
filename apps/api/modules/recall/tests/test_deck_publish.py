"""Publishing a platform deck version (FR-F15-44, 45, 53): atomic, rights gated, versioned, invisible until live."""

import pytest
from django.db import IntegrityError, transaction

from core import events
from modules.recall import errors
from modules.recall.models import (
    RecallAuditLog,
    RecallDeck,
    RecallDeckVersion,
    RecallDeckVersionItem,
    RecallItem,
    RecallItemVersion,
)
from modules.recall.services import decks as svc

from .w11 import EDITOR, draft_deck, platform_item, published_deck

pytestmark = pytest.mark.django_db


def test_first_publish_makes_everything_live_and_counts():
    deck, items, version = published_deck(5, importances=["mandatory", "mandatory", "important", "bullet", "bullet"])
    assert (version.state, version.version_no, version.item_count) == ("live", 1, 5)
    assert version.tier_counts == {"v": 1, "mandatory": 2, "important": 1, "bullet": 2, "cards": 5}
    assert version.diff_summary["added"] == 5 and version.diff_summary["removed"] == 0
    assert version.published_by == EDITOR and version.published_at is not None
    assert deck.live_version_id == version.id and deck.draft_version_id is None
    for item in items:
        item.refresh_from_db()
        assert item.live_version.state == "live" and item.live_version.live_at is not None
    assert set(RecallDeckVersionItem.objects.filter(deck_version=version).values_list("change_vs_prev", flat=True)) == {
        "added"
    }
    audit = RecallAuditLog.objects.get(action="deck_publish")
    assert audit.target_id == str(deck.id) and audit.detail["items"] == 5
    assert "prompt" not in str(audit.detail)  # ids and counts only, never text


def test_a_cloze_counts_one_card_per_face():
    cloze = platform_item(
        kind="cloze", fields={"text_md": "{{c1::A}} and {{c2::B}} and {{c3::C}}"}, importance="mandatory"
    )
    deck, draft = draft_deck([cloze, platform_item()])
    version = svc.publish_deck_version(EDITOR, deck.id, draft.id)
    assert version.tier_counts["cards"] == 4 and version.item_count == 2


def test_second_version_computes_change_vs_prev_and_supersedes_the_first():
    deck, items, v1 = published_deck(4)
    typo, same, dropped, _ = items
    svc.new_item_version(EDITOR, typo, {"prompt_md": "A fixed question?", "answer_md": "Answer"}, change_kind="typo")
    fresh = platform_item("Brand new")
    draft = svc.start_draft_version(EDITOR, deck)  # a copy of the live rows, newest item version each
    svc.set_draft_rows(draft, [(typo, None), (same, None), (items[3], None), (fresh, None)])
    v2 = svc.publish_deck_version(EDITOR, deck.id, draft.id, changelog_md="Fix and add.")
    by_item = dict(RecallDeckVersionItem.objects.filter(deck_version=v2).values_list("item_id", "change_vs_prev"))
    assert by_item[typo.id] == "typo" and by_item[same.id] == "unchanged" and by_item[fresh.id] == "added"
    assert v2.diff_summary["removed"] == 1 and v2.diff_summary["typo"] == 1 and v2.diff_summary["added"] == 1
    v1.refresh_from_db()
    deck.refresh_from_db()
    assert v1.state == "superseded" and v2.state == "live" and deck.live_version_id == v2.id
    typo.refresh_from_db()
    assert typo.live_version.version_no == 2
    assert RecallItemVersion.objects.get(item=typo, version_no=1).state == "superseded"
    # the dropped item keeps its live version (it may sit in another deck); only the snapshot no longer lists it
    assert RecallItemVersion.objects.get(item=dropped).state == "live"
    assert RecallDeckVersion.objects.filter(deck=deck, state="live").count() == 1


def test_a_failed_publish_leaves_the_previous_live_version_served(monkeypatch):
    deck, items, v1 = published_deck(3)
    svc.new_item_version(EDITOR, items[0], {"prompt_md": "Changed?", "answer_md": "Answer"}, change_kind="substantive")
    draft = svc.start_draft_version(EDITOR, deck)
    before = {
        "audit": RecallAuditLog.objects.count(),
        "item_versions": list(RecallItemVersion.objects.order_by("id").values_list("id", "state")),
    }

    def boom(*a, **k):
        raise RuntimeError("database went away halfway")

    monkeypatch.setattr(RecallAuditLog.objects, "create", boom)  # the LAST write of the publish
    with pytest.raises(RuntimeError):
        svc.publish_deck_version(EDITOR, deck.id, draft.id)
    deck.refresh_from_db()
    assert deck.live_version_id == v1.id and deck.draft_version_id == draft.id
    assert RecallDeckVersion.objects.get(pk=v1.id).state == "live"
    assert RecallDeckVersion.objects.get(pk=draft.id).state == "draft"
    assert list(RecallItemVersion.objects.order_by("id").values_list("id", "state")) == before["item_versions"]
    assert RecallAuditLog.objects.count() == before["audit"]
    assert not RecallDeckVersionItem.objects.filter(deck_version=draft).exclude(change_vs_prev="unchanged").exists()


def test_the_rights_gate_blocks_unknown_and_names_the_items():
    good = platform_item("ok", rights="original")
    bad = platform_item("not ok", rights="unknown", ref="needs-rights")
    deck, draft = draft_deck([good, bad])
    with pytest.raises(errors.RightsBlocked) as caught:
        svc.publish_deck_version(EDITOR, deck.id, draft.id)
    assert caught.value.extra == {"item_ids": [str(bad.id)]}
    deck.refresh_from_db()
    assert deck.live_version_id is None and RecallDeckVersion.objects.get(pk=draft.id).state == "draft"
    assert not RecallItemVersion.objects.filter(state="live").exists()
    # fixing the status lets the same draft through
    RecallItem.objects.filter(pk=bad.pk).update(rights_status="licensed")
    assert svc.publish_deck_version(EDITOR, deck.id, draft.id).state == "live"


@pytest.mark.parametrize("rights", ["original", "licensed", "institute_material", "third_party_claimed"])
def test_every_other_rights_status_may_go_live(rights):
    deck, draft = draft_deck([platform_item(rights=rights)])
    assert svc.publish_deck_version(EDITOR, deck.id, draft.id).state == "live"


def test_a_published_version_cannot_be_published_again_or_replaced_by_an_older_one():
    deck, items, v1 = published_deck(2)
    with pytest.raises(errors.VersionNotPublishable):
        svc.publish_deck_version(EDITOR, deck.id, v1.id)
    old = RecallDeckVersion.objects.create(deck=deck, version_no=0, state="draft")  # numbered below the live one
    with pytest.raises(errors.VersionNotPublishable):
        svc.publish_deck_version(EDITOR, deck.id, old.id)


def test_an_empty_version_and_a_withdrawn_item_are_refused():
    deck = RecallDeck.objects.create(kind="platform", slug="e", title="E")
    draft = svc.start_draft_version(EDITOR, deck, from_live=False)
    with pytest.raises(errors.EmptyDeckVersion):
        svc.publish_deck_version(EDITOR, deck.id, draft.id)
    item = platform_item()
    svc.set_draft_rows(draft, [(item, None)])
    RecallItem.objects.filter(pk=item.pk).update(status="withdrawn")
    with pytest.raises(errors.ItemNotPublishable) as caught:
        svc.publish_deck_version(EDITOR, deck.id, draft.id)
    assert caught.value.extra == {"item_ids": [str(item.id)]}


def test_a_version_of_another_deck_is_not_found():
    deck_a, _, _ = published_deck(1)
    deck_b, draft_b = draft_deck([platform_item()])
    with pytest.raises(errors.VersionNotPublishable):
        svc.publish_deck_version(EDITOR, deck_a.id, draft_b.id)
    with pytest.raises(errors.DeckNotFound):
        svc.publish_deck_version(EDITOR, deck_b.id.__class__("00000000-0000-0000-0000-000000000000"), draft_b.id)


def test_a_students_own_deck_cannot_be_published():
    from .factories import make_deck

    own = make_deck()
    with pytest.raises(errors.DeckNotFound):
        svc.publish_deck_version(EDITOR, own.id, own.id)


def test_there_is_only_one_live_version_per_item_and_deck_in_the_database():
    deck, items, v1 = published_deck(1)
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallDeckVersion.objects.filter(deck=deck, state="superseded").update(state="live")
        RecallDeckVersion.objects.create(deck=deck, version_no=9, state="live")

    deck, items, v1 = published_deck(1)
    item = items[0]
    item.refresh_from_db()
    item.refresh_from_db()
    item = items[0]
    live_text = item.live_version.plain_text
    draft = svc.new_item_version(
        EDITOR, item, {"prompt_md": "Rewritten?", "answer_md": "New"}, change_kind="clarify", note="why"
    )
    assert draft.state == "draft" and draft.version_no == 2 and draft.change_note == "why"
    item.refresh_from_db()
    assert item.live_version.plain_text == live_text and item.current_version_id == draft.id
    again = svc.new_item_version(EDITOR, item, {"prompt_md": "Rewritten?", "answer_md": "New"}, change_kind="clarify")
    assert again.id == draft.id  # the same text twice makes no new version
    third = svc.new_item_version(
        EDITOR, item, {"prompt_md": "Rewritten again?", "answer_md": "New"}, change_kind="typo"
    )
    assert third.id == draft.id and third.plain_text.startswith(
        "Rewritten again"
    )  # one draft at a time: editing replaces it


def test_item_text_is_validated_by_its_kind():
    with pytest.raises(errors.InvalidFields):
        platform_item(fields={"prompt_md": "", "answer_md": ""})
    with pytest.raises(errors.UnknownKind):
        platform_item(kind="nope", fields={"a": "b"})


def test_the_published_event_carries_ids_and_counts_only(django_capture_on_commit_callbacks):
    seen = []
    events.subscribe("recall_deck_published", lambda **p: seen.append(p))
    try:
        with django_capture_on_commit_callbacks(execute=True):
            deck, items, version = published_deck(2)
    finally:
        events.clear()
    assert len(seen) == 1
    payload = seen[0]
    assert payload["deck_id"] == str(deck.id) and payload["version_no"] == 1
    assert payload["diff_summary"]["added"] == 2 and payload["substantive_count"] == 0
    assert "prompt" not in str(payload)
