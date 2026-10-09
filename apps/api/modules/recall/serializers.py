"""Input parsing and output shapes of the card endpoints. Card text leaves only in a response body, never in a log or a metric."""

from __future__ import annotations

from rest_framework import serializers

from .models import ITEM_IMPORTANCES, ITEM_KINDS
from .selectors import CardView
from .selectors.cards import SORTS, STATES
from .services.cards import BULK_ACTIONS, SELECTION_ORIGINS
from .vocab import STATE_NAMES

KIND = serializers.CharField(max_length=24)  # the registry decides what exists: 422 `unknown_kind`, not 400


class CardListQuery(serializers.Serializer):
    subject_key = serializers.CharField(required=False, max_length=80)
    chapter_id = serializers.UUIDField(required=False)
    kind = serializers.ChoiceField(choices=ITEM_KINDS, required=False)
    tier = serializers.ChoiceField(choices=ITEM_IMPORTANCES, required=False)
    state = serializers.ChoiceField(choices=STATES, required=False)
    deck_id = serializers.UUIDField(required=False)
    q = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    status = serializers.ChoiceField(choices=("active", "suspended", "archived", "deleted"), required=False)
    sort = serializers.ChoiceField(choices=tuple(SORTS), required=False, default="newest")
    cursor = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100)


class CardCreateSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    kind = KIND
    fields = serializers.DictField()
    chapter_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    topic_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    importance = serializers.CharField(required=False, default="bullet", max_length=12)
    tags = serializers.ListField(child=serializers.JSONField(), required=False, default=list, max_length=50)
    reference_keys = serializers.ListField(child=serializers.JSONField(), required=False, default=list, max_length=50)
    deck_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list, max_length=20)
    force = serializers.BooleanField(required=False, default=False)


class SelectionSourceSerializer(serializers.Serializer):
    module = serializers.CharField(max_length=16)
    object_id = serializers.CharField(max_length=80)
    locator = serializers.DictField(required=False, default=dict)


class SelectionSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    origin = serializers.ChoiceField(choices=tuple(SELECTION_ORIGINS))
    selection_text = serializers.CharField(max_length=8000, trim_whitespace=False)
    source = SelectionSourceSerializer()
    chapter_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    topic_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    kind = serializers.CharField(required=False, allow_null=True, default=None, max_length=24)
    quick = serializers.BooleanField(required=False, default=True)
    cloze = serializers.BooleanField(required=False, default=False)
    force = serializers.BooleanField(required=False, default=False)


class CardPatchSerializer(serializers.Serializer):
    """Only the keys that were sent are applied (`chapter_id: null` means Unsorted, a missing key means unchanged)."""

    base_rev = serializers.IntegerField(min_value=1)
    fields = serializers.DictField(required=False)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    topic_id = serializers.UUIDField(required=False, allow_null=True)
    importance = serializers.CharField(required=False, max_length=12)
    tags = serializers.ListField(child=serializers.JSONField(), required=False, max_length=50)


class StatusSerializer(serializers.Serializer):
    until = serializers.DateTimeField(required=False)


class UndoSerializer(serializers.Serializer):
    undo_token = serializers.CharField(max_length=500)


class BulkSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )  # the 200 cap is a 422 from the service
    action = serializers.ChoiceField(choices=BULK_ACTIONS)
    chapter_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    topic_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    importance = serializers.CharField(required=False, max_length=12)
    tag = serializers.CharField(required=False, max_length=80)
    deck_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        needs = {"set_importance": "importance", "add_tag": "tag", "add_to_deck": "deck_id"}.get(attrs["action"])
        if needs and needs not in attrs:
            raise serializers.ValidationError({needs: "This field is required for this action."})
        return attrs


# --- output ---------------------------------------------------------------------------------------------------------
def iso(value):
    return value.isoformat().replace("+00:00", "Z") if value else None


def chapter_dict(view: CardView) -> dict | None:
    ref = view.chapter
    if ref is None:
        return {"id": str(view.card.chapter_id), "key": None, "name": None} if view.card.chapter_id else None
    return {
        "id": str(ref.id),
        "key": ref.key,
        "name": ref.name,
        "subject_key": ref.subject_key,
        "subject_name": ref.subject_name,
    }


def badges_of(view: CardView, now=None) -> list[str]:
    c = view.card
    out = []
    if c.status == "suspended":
        out.append("suspended")
    if c.leech:
        out.append("tricky")
    if c.needs_recheck:
        out.append("recheck")
    if c.buried_until and (now is None or c.buried_until > now):
        out.append("buried")
    return out


def source_dict(view: CardView) -> dict | None:
    item = view.item
    if not item.origin_module:
        return (
            {"origin": item.origin, "module": None, "ref_id": None, "locator": None}
            if item.origin != "manual"
            else None
        )
    return {
        "origin": item.origin,
        "module": item.origin_module,
        "ref_id": item.origin_ref,
        "locator": item.origin_locator,
    }


def card_dict(view: CardView) -> dict:
    c, item = view.card, view.item
    return {
        "id": str(c.id),
        "rev": c.rev,
        "item_id": str(item.id),
        "item_version_id": str(c.item_version_id),
        "kind": item.kind,
        "ordinal": c.ordinal,
        "front_md": view.front_md,
        "back_md": view.back_md,
        "fields": view.fields,
        "state": c.state,
        "state_name": STATE_NAMES[c.state],
        "status": c.status,
        "importance": item.importance,
        "chapter": chapter_dict(view),
        "subject_key": c.subject_key,
        "tags": item.tags,
        "reference_keys": item.reference_keys,
        "deck_ids": [str(d) for d in view.deck_ids],
        "badges": badges_of(view),
        "source": source_dict(view),
        "due_at": iso(c.due_at),
        "buried_until": iso(c.buried_until),
        "reps": c.reps,
        "lapses": c.lapses,
        "created_at": iso(c.created_at),
        "updated_at": iso(c.updated_at),
    }
