import uuid

import pytest

from core import feature_flags, recall_port
from core.recall_port import CARD_KINDS, CardRef, RecallUnavailable, SourceRef
from modules.recall import provider as provider_module
from modules.recall.models import RecallCard, RecallItem
from modules.recall.provider import RecallProviderImpl, fields_for_port_kind

from .factories import OTHER, USER
from .support import row

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def provider():
    """The real provider (Notes tests reset the registry, so the test installs it explicitly)."""
    previous = recall_port.get_recall_provider()
    impl = RecallProviderImpl()
    recall_port.register_recall_provider(impl)
    yield impl
    recall_port.register_recall_provider(previous)


def make(
    provider, kind="fact", ref=None, user=USER, front="Why does ITC lapse?", back="Because of section 17(5).", **extra
):
    return provider.create_card_from_source(
        user,
        kind=kind,
        front_md=front,
        back_md=back,
        source=SourceRef("notes", "annotation", ref or uuid.uuid4()),
        client_id=uuid.uuid4(),
        **extra,
    )


# --- D2 mapping (pure) -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("port_kind", "card_kind"),
    [
        ("formula", "formula"),
        ("definition", "definition"),
        ("rule", "pointer"),
        ("example", "pointer"),
        ("doubt", "pointer"),
        ("fact", "pointer"),
    ],
)
def test_the_port_kind_maps_to_a_card_kind(port_kind, card_kind):
    kind, fields = fields_for_port_kind(port_kind, "State the formula from GST (page 3).\nmore", "A = B")
    assert kind == card_kind
    assert set(provider_module.CARD_KIND_OF) == set(CARD_KINDS)
    if card_kind == "formula":
        assert fields == {"name": "State the formula from GST (page 3)", "expression_md": "A = B"}
    elif card_kind == "definition":
        assert fields["term"] == "State the formula from GST (page 3)" and fields["definition_md"] == "A = B"
    else:
        assert fields["answer_md"] == "A = B" and fields["prompt_md"].startswith("State the formula")


def test_the_mapping_trims_long_text_and_never_returns_an_empty_required_field():
    kind, fields = fields_for_port_kind("formula", "T" * 500, "x" * 5000)
    assert len(fields["name"]) <= 120 and len(fields["expression_md"]) == 4000
    assert fields_for_port_kind("definition", "", "body")[1]["term"] == "Definition"
    assert fields_for_port_kind("fact", "  ", "body")[1]["prompt_md"] == "Recall this point."


# --- the provider ------------------------------------------------------------------------------------------------------
def test_a_card_is_created_from_a_source_with_the_port_kind_kept(provider):
    ref = uuid.uuid4()
    card = make(provider, "formula", ref, front="Break-even point", back="$F / c$")
    assert isinstance(card, CardRef) and card.existing is False
    db = row(card.id)
    item = db.item
    assert item.kind == "formula" and item.origin == "selection" and item.shareable is False
    assert (item.origin_module, item.origin_ref, item.origin_kind) == ("notes", str(ref), "formula")
    assert item.origin_locator == {"v": 1, "ref_type": "annotation"} and item.rights_status == "original"
    assert item.live_version.fields["name"] == "Break-even point"
    assert (db.state, db.stability, db.due_at) == (0, None, None)


def test_it_is_idempotent_on_user_source_and_port_kind_even_with_a_new_client_id(provider):
    ref = uuid.uuid4()
    first = make(provider, "rule", ref)
    second = make(provider, "rule", ref)
    assert second.existing is True and second.id == first.id and RecallCard.objects.count() == 1
    other_kind = make(provider, "example", ref)
    assert other_kind.existing is False and other_kind.id != first.id  # same source, another port kind
    other_student = make(provider, "rule", ref, user=OTHER)
    assert other_student.existing is False and RecallCard.objects.count() == 3


def test_a_replay_of_the_same_client_id_returns_the_same_card(provider):
    client_id, ref = uuid.uuid4(), uuid.uuid4()
    args = {
        "kind": "fact",
        "front_md": "Q?",
        "back_md": "A",
        "source": SourceRef("notes", "note", ref),
        "client_id": client_id,
    }
    first = provider.create_card_from_source(USER, **args)
    again = provider.create_card_from_source(USER, **args)
    assert again.existing is True and again.id == first.id and RecallItem.objects.count() == 1


def test_two_marks_with_the_same_words_are_two_cards(provider):
    assert make(provider).id != make(provider).id


def test_a_deleted_source_card_does_not_block_a_new_one(provider):
    from modules.recall.services import cards as services

    ref = uuid.uuid4()
    first = make(provider, "fact", ref)
    services.set_card_status(USER, first.id, "delete")
    again = make(provider, "fact", ref)
    assert again.existing is False and again.id != first.id


def test_markdown_the_card_profile_refuses_falls_back_to_plain_text(provider):
    card = make(provider, "fact", front="## A heading\nbody", back="![img](https://x/y.png) and ---\n\n---\n\ntext")
    assert row(card.id).item.live_version.fields["prompt_md"]


def test_a_quote_quota_failure_is_the_usual_429(provider):
    from modules.recall.errors import QuotaExceeded
    from modules.recall.models import RecallQuotaPlan

    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=1)
    make(provider)
    with pytest.raises(QuotaExceeded):
        make(provider)


def test_an_unsupported_module_or_kind_is_a_programming_error(provider):
    with pytest.raises(ValueError):
        provider.create_card_from_source(
            USER,
            kind="fact",
            front_md="Q",
            back_md="A",
            source=SourceRef("elsewhere", "x", uuid.uuid4()),
            client_id=uuid.uuid4(),
        )
    with pytest.raises(ValueError):
        make(provider, "riddle")


def test_cards_for_source_maps_ids_to_the_first_card(provider):
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    first_a = make(provider, "fact", a)
    make(provider, "formula", a)
    only_b = make(provider, "rule", b)
    found = provider.cards_for_source(USER, [a, b, c])
    assert found == {a: CardRef(first_a.id), b: CardRef(only_b.id)}
    assert provider.cards_for_source(OTHER, [a, b]) == {} and provider.cards_for_source(USER, []) == {}


def test_cards_for_source_skips_deleted_cards(provider):
    from modules.recall.services import cards as services

    ref = uuid.uuid4()
    made_card = make(provider, "fact", ref)
    services.set_card_status(USER, made_card.id, "delete")
    assert provider.cards_for_source(USER, [ref]) == {}


# --- the flag ----------------------------------------------------------------------------------------------------------
@pytest.fixture
def recall_off(monkeypatch):
    monkeypatch.setattr(feature_flags, "_lookup", lambda name, distinct_id: name != "recall_system")


def test_with_the_flag_off_nothing_is_created_and_nothing_is_known(provider, recall_off):
    with pytest.raises(RecallUnavailable):
        make(provider)
    assert RecallItem.objects.count() == 0 and provider.cards_for_source(USER, [uuid.uuid4()]) == {}


def test_a_flag_lookup_that_raises_counts_as_off(provider, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("posthog down")

    monkeypatch.setattr(provider_module, "flag_enabled", boom)
    with pytest.raises(RecallUnavailable):
        make(provider)
    assert provider.cards_for_source(USER, [uuid.uuid4()]) == {}


def test_without_posthog_the_provider_stays_off(provider, monkeypatch):
    monkeypatch.undo()
    feature_flags.clear_flag_cache()
    with pytest.raises(RecallUnavailable):
        make(provider)


def test_the_app_registers_the_provider_when_it_starts():
    from django.apps import apps

    recall_port.register_recall_provider(None)
    apps.get_app_config("recall").ready()
    assert isinstance(recall_port.get_recall_provider(), RecallProviderImpl)
    assert isinstance(recall_port.get_recall_provider(), recall_port.RecallProvider)


# --- through the real Notes endpoint -----------------------------------------------------------------------------------
def notes_mark(api):
    from modules.notes.tests.marks_support import create, new_document

    return create(api, new_document(), color="g", quote_exact="ITC = output tax less input tax", comment="Section 16")


def test_notes_make_a_card_works_with_the_flag_on_and_is_idempotent(api):
    mark = notes_mark(api)
    first = api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4())})
    assert first.status_code == 200 and first.json_body["existing"] is False
    card = row(first.json_body["card_id"])
    assert card.item.kind == "formula" and card.item.origin_module == "notes" and card.item.origin_ref == mark["id"]
    assert card.item.origin_kind == "formula" and card.item.shareable is False
    again = api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4())})
    assert again.json_body == {"card_id": first.json_body["card_id"], "existing": True}
    other = api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4()), "kind": "definition"})
    assert other.json_body["existing"] is False and RecallCard.objects.count() == 2


def test_notes_make_a_card_is_503_and_the_capability_is_off_with_the_flag_off(api, recall_off):
    mark = notes_mark(api)
    res = api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4())})
    assert res.status_code == 503 and res.json_body["error"]["code"] == "recall_unavailable"
    assert RecallItem.objects.count() == 0
    assert api.get("/notes/settings/").json_body["capabilities"]["recall"] is False


def test_the_notes_capability_is_on_with_the_flag_on(api):
    assert api.get("/notes/settings/").json_body["capabilities"]["recall"] is True
