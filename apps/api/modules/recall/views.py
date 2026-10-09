"""
Thin views for /api/v1/recall/ (cards, W4): auth, the `recall_system` flag, parse, call a service or selector, serialise.
No ORM and no business rules here. Every view is flag gated; `RECALL_OPEN_PATHS` is the (for now empty) list of the paths that
must keep working with the flag off (data export and delete-all arrive in W11, D4), which the flag test reads.
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.permissions import ParsedAPIView

from . import selectors, serializers, services
from .errors import CardDeleted
from .permissions import RecallFlagEnabled
from .selectors import CardFilter
from .services.cards import UNDO_SECONDS, SelectionSource

RECALL_OPEN_PATHS: tuple[str, ...] = ()


class RecallView(ParsedAPIView):
    """Reads carry the default per-user throttle; writes use the `recall_write` scope."""

    permission_classes = [IsAuthenticated, RecallFlagEnabled]


class WriteView(RecallView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "recall_write"


def _card_payload(user_id, card_id) -> dict:
    view = selectors.get_card(user_id, card_id)
    if view is None:
        raise NotFound("Card not found.")
    return serializers.card_dict(view)


def _created_payload(user_id, result) -> dict:
    views = [selectors.get_card(user_id, c.id) for c in result.cards]
    return {
        "item_id": str(result.item_id),
        "kind": result.kind,
        "existing": result.existing,
        "cards": [serializers.card_dict(v) for v in views if v is not None],
    }


class CardListCreateView(RecallView):
    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_classes, self.throttle_scope = [ScopedRateThrottle], "recall_write"
        return super().get_throttles()

    def get(self, request):
        d = self.parse(serializers.CardListQuery, request.query_params).validated_data
        page = selectors.list_cards(
            request.user.id,
            CardFilter(
                subject_key=d.get("subject_key"),
                chapter_id=d.get("chapter_id"),
                kind=d.get("kind"),
                tier=d.get("tier"),
                state=d.get("state"),
                deck_id=d.get("deck_id"),
                q=d.get("q", ""),
                status=d.get("status"),
                sort=d["sort"],
            ),
            cursor=d.get("cursor"),
            limit=d.get("limit"),
        )
        return Response(
            {
                "items": [serializers.card_dict(v) for v in page.items],
                "next_cursor": page.next_cursor,
                "server_time": serializers.iso(timezone.now()),
            }
        )

    def post(self, request):
        d = self.parse(serializers.CardCreateSerializer, request.data).validated_data
        result = services.cards.create_card(
            request.user.id,
            kind=d["kind"],
            fields=d["fields"],
            chapter_id=d["chapter_id"],
            topic_id=d["topic_id"],
            importance=d["importance"],
            tags=d["tags"],
            reference_keys=d["reference_keys"],
            deck_ids=d["deck_ids"],
            client_id=d["client_id"],
            force=d["force"],
        )
        return Response(_created_payload(request.user.id, result), status=200 if result.existing else 201)


class CardFromSelectionView(WriteView):
    def post(self, request):
        d = self.parse(serializers.SelectionSerializer, request.data).validated_data
        src = d["source"]
        result = services.cards.create_card_from_selection(
            request.user.id,
            origin=d["origin"],
            selection_text=d["selection_text"],
            source=SelectionSource(src["module"], src["object_id"], src["locator"]),
            chapter_id=d["chapter_id"],
            topic_id=d["topic_id"],
            kind=d["kind"],
            client_id=d["client_id"],
            force=d["force"],
            cloze=d["cloze"],
            quick=d["quick"],
        )
        body = _created_payload(request.user.id, result)
        body |= {
            "card_id": str(result.card_id),
            "undo_token": result.undo_token,
            "undo_seconds": UNDO_SECONDS if result.undo_token else 0,
        }
        return Response(body, status=200 if result.existing else 201)


class CardDetailView(RecallView):
    def get_throttles(self):
        if self.request.method != "GET":
            self.throttle_classes, self.throttle_scope = [ScopedRateThrottle], "recall_write"
        return super().get_throttles()

    def get(self, request, card_id):
        view = selectors.get_card(request.user.id, card_id)
        if view is None:
            raise NotFound("Card not found.")
        if view.card.status == "deleted":
            raise CardDeleted
        return Response(serializers.card_dict(view))

    def patch(self, request, card_id):
        d = self.parse(serializers.CardPatchSerializer, request.data).validated_data
        extra = {k: d[k] for k in ("chapter_id", "topic_id") if k in d}
        services.cards.update_card(
            request.user.id,
            card_id,
            base_rev=d["base_rev"],
            fields=d.get("fields"),
            importance=d.get("importance"),
            tags=d.get("tags"),
            **extra,
        )
        return Response(_card_payload(request.user.id, card_id))

    def delete(self, request, card_id):
        _, token = services.cards.set_card_status(request.user.id, card_id, "delete")
        return Response({"deleted": True, "card_id": str(card_id), "undo_token": token, "undo_seconds": UNDO_SECONDS})


class CardActionView(WriteView):
    """`POST cards/{id}/<action>/`: `action` is set in the URL conf (suspend, unsuspend, bury, reset, recheck_ok)."""

    action: str = ""

    def post(self, request, card_id):
        d = self.parse(serializers.StatusSerializer, request.data or {}).validated_data
        services.cards.set_card_status(request.user.id, card_id, self.action, until=d.get("until"))
        return Response(_card_payload(request.user.id, card_id))


class CardUndoView(WriteView):
    def post(self, request):
        d = self.parse(serializers.UndoSerializer, request.data).validated_data
        card = services.cards.undo(request.user.id, d["undo_token"])
        return Response(_card_payload(request.user.id, card.id))


class CardBulkView(WriteView):
    def post(self, request):
        d = self.parse(serializers.BulkSerializer, request.data).validated_data
        args = {k: d[k] for k in ("chapter_id", "topic_id", "importance", "tag", "deck_id") if k in d}
        result = services.cards.bulk_update(request.user.id, d["ids"], d["action"], **args)
        return Response({"count": result.count})
