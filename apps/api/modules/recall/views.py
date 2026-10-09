"""
Thin views for /api/v1/recall/ (cards, W4): auth, the `recall_system` flag, parse, call a service or selector, serialise.
No ORM and no business rules here. Every view is flag gated; `RECALL_OPEN_PATHS` is the (for now empty) list of the paths that
must keep working with the flag off (data export and delete-all arrive in W11, D4), which the flag test reads.
"""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.http import request_has_secret
from core.permissions import ParsedAPIView

from . import selectors, serializers, services
from .errors import BatchTooLarge, CardDeleted
from .permissions import RecallFlagEnabled
from .selectors import CardFilter, QueueFilters
from .services.cards import UNDO_SECONDS, SelectionSource
from .vocab import IMPORTANCE_INT

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


# --- reviews, sessions, catch-up (W5) ---------------------------------------------------------------------------------
TICK_HEADER = "X-Recall-Tick-Secret"


class ReviewView(RecallView):
    """Rating a card is never limited by quota; the `recall_review` throttle (600/min) is only politeness."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "recall_review"


class ReviewSubmitView(ReviewView):
    def post(self, request):
        event = self.parse(serializers.ReviewSerializer, request.data).to_event()
        result = services.reviews.submit_review(request.user.id, event)
        if result.status == services.reviews.INVALID:
            if result.reason == "unknown_card":
                raise NotFound("Card not found.")
            raise ValidationError({"detail": result.reason, "code": result.reason})
        return Response(serializers.review_result_dict(result), status=200 if result.status == "duplicate" else 201)


class ReviewBatchView(ReviewView):
    def post(self, request):
        raw = self.parse(serializers.ReviewBatchSerializer, request.data).validated_data["events"]
        if len(raw) > services.reviews.lim.BATCH_MAX_EVENTS:
            raise BatchTooLarge
        events = []
        rejected: dict[int, str] = {}
        for i, item in enumerate(raw):
            s = serializers.ReviewSerializer(data=item)
            if s.is_valid():
                events.append(s.to_event())
            else:
                rejected[i] = "invalid_event"
        results, cards = services.reviews.submit_reviews(request.user.id, events)
        body = [serializers.review_result_dict(r) for r in results]
        body += [
            {
                "event_id": str(raw[i].get("id", "")),
                "status": "invalid",
                "reason": reason,
                "merged": False,
                "card": None,
            }
            for i, reason in rejected.items()
        ]
        return Response(
            {
                "results": body,
                "cards": [serializers.review_card_dict(c) for c in cards],
                "server_time": serializers.iso(timezone.now()),
            }
        )


class ReviewUndoView(ReviewView):
    def post(self, request):
        d = self.parse(serializers.ReviewUndoSerializer, request.data).validated_data
        result = services.reviews.undo_review(request.user.id, d["undo_id"], d["voids_id"])
        return Response(
            {
                "undo_id": str(result.undo_id),
                "voids_id": str(result.voids_id),
                "card": serializers.review_card_dict(result.card) if result.card else None,
            }
        )


class SessionOpenView(ReviewView):
    def post(self, request):
        d = self.parse(serializers.SessionOpenSerializer, request.data).validated_data
        row, created = services.sessions.open_session(
            request.user.id,
            d["client_id"],
            source=d["source"],
            spec=d["spec"],
            tz=d["tz"],
            planned_count=d["planned_count"],
        )
        return Response(serializers.session_dict(row), status=201 if created else 200)


class SessionCloseView(ReviewView):
    def post(self, request, session_id):
        row, summary = services.sessions.close_session(request.user.id, session_id)
        return Response({**serializers.session_dict(row), "summary": summary})


class RebalanceView(WriteView):
    def post(self, request):
        d = self.parse(serializers.RebalanceSerializer, request.data or {}).validated_data
        return Response(services.catchup.rebalance(request.user.id, d["days"]))


class VacationView(WriteView):
    def put(self, request):
        d = self.parse(serializers.VacationSerializer, request.data).validated_data
        result = services.preferences.set_vacation(request.user.id, d["until"])
        return Response({**result, "vacation_until": d["until"].isoformat() if d["until"] else None})


class TickView(ParsedAPIView):
    """
    Cron entry (Vercel Cron GET or a POST from any scheduler): closes sessions idle for 60 minutes. Authenticated by a shared
    secret, not a student token, open whatever the flag says, bounded and safe to repeat.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes: list = []

    def _tick(self, request):
        if not request_has_secret(request, settings.RECALL_TICK_SECRET, TICK_HEADER):
            return Response({"error": {"code": "forbidden", "message": "Not allowed.", "details": None}}, status=403)
        return Response({"sessions_closed": services.sessions.close_idle()})

    get = post = _tick


# --- read side (W6): GETs never write ----------------------------------------------------------------------------------
class TodayView(RecallView):
    def get(self, request):
        d = self.parse(serializers.TodayQuery, request.query_params).validated_data
        now = timezone.now()
        return Response(serializers.today_dict(selectors.today_plan(request.user.id, now=now, tz=d.get("tz")), now))


class QueueView(RecallView):
    def get(self, request):
        d = self.parse(serializers.QueueQuery, request.query_params).validated_data
        now = timezone.now()
        study = selectors.load_study(request.user.id, now, d.get("tz"))
        forgotten_ids: list[str] = []
        if d["source"] == "forgotten":
            forgotten_ids = [str(r.card.id) for r in selectors.forgotten(request.user.id, now=now, limit=50)]
        cards = selectors.build_queue(
            study,
            d["source"],
            limit=d["limit"],
            filters=QueueFilters(
                chapter_id=d.get("chapter_id"),
                deck_id=d.get("deck_id"),
                kind=d.get("kind"),
                tier=IMPORTANCE_INT[d["tier"]] if d.get("tier") else None,
            ),
            exclude=d.get("exclude", []),
            forgotten_ids=forgotten_ids,
            extra=d["extra"],
        )
        return Response(
            {
                "source": d["source"],
                "server_time": serializers.iso(now),
                "cards": [{**serializers.queue_card_dict(c), **serializers.memory_dict(c.card)} for c in cards],
            }
        )


class PackView(RecallView):
    def get(self, request):
        d = self.parse(serializers.PackQuery, request.query_params).validated_data
        now = timezone.now()
        pack = selectors.pack_for_device(request.user.id, now=now, limit=d.get("limit"))
        s = pack.study
        cards = []
        for q in pack.cards:
            cards.append({**serializers.queue_card_dict(q), **serializers.memory_dict(q.card)})
        return Response(
            {
                "pack_id": pack.pack_id,
                "generated_at": serializers.iso(now),
                "server_time": serializers.iso(now),
                "expires_at": serializers.iso(pack.expires_at),
                "settings": serializers.settings_dict(s.settings, s.scheduler_version),
                "weights": list(s.weights),
                "scheduler_version": s.scheduler_version,
                "cards": cards,
                "counters": {
                    "new_done_today": s.new_done,
                    "reviews_done_today": s.reviews_done,
                    "local_date": s.today.isoformat(),
                },
            }
        )


class ForgottenView(RecallView):
    def get(self, request):
        d = self.parse(serializers.ForgottenQuery, request.query_params).validated_data
        rows = selectors.forgotten(
            request.user.id,
            now=timezone.now(),
            window_days=d["window_days"],
            limit=d["limit"],
            subject_key=d.get("subject_key"),
        )
        return Response({"items": [serializers.forgotten_dict(r) for r in rows]})


class StatsView(RecallView):
    """`stats/<name>/`: a report with an `ETag` (the web keeps it for 60 seconds), 304 when it has not changed."""

    report: str = ""

    def get(self, request):
        d = self.parse(serializers.StatsQuery, request.query_params).validated_data
        now, uid, tz = timezone.now(), request.user.id, d.get("tz")
        if self.report == "summary":
            rep = selectors.stats_summary(uid, range_=d["range"], now=now, tz=tz)
        elif self.report == "retention":
            rep = selectors.stats_retention(uid, range_=d["range"], now=now, tz=tz)
        elif self.report == "forecast":
            rep = selectors.stats_forecast(uid, now=now, days=d["days"], tz=tz)
        else:
            rep = selectors.stats_chapters(uid, now=now, tz=tz)
        headers = {"ETag": rep.etag, "Cache-Control": "private, no-cache"}
        if request.headers.get("If-None-Match") == rep.etag:
            return Response(status=304, headers=headers)
        return Response(rep.data, headers=headers)


class SettingsView(RecallView):
    def get_throttles(self):
        if self.request.method == "PUT":
            self.throttle_classes, self.throttle_scope = [ScopedRateThrottle], "recall_write"
        return super().get_throttles()

    def get(self, request):
        s = selectors.get_settings(request.user.id)
        return Response(serializers.settings_dict(s, selectors.active_params(s)[2]))

    def put(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        unknown = sorted(set(data) - set(serializers.SETTINGS_KEYS))
        if unknown:
            raise ValidationError({k: "Unknown setting." for k in unknown})
        row = services.preferences.update_settings(request.user.id, data)
        return Response(serializers.settings_dict(row, selectors.active_params(row)[2]))
