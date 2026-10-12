"""
Thin views for the AI suggestion endpoints (R2-W5): auth, the `recall_system` and `recall_ai` flags, parse, call a service or
selector, serialise. No ORM and no business rules here. The `recall_ai` flag fails closed; withdrawing consent stays open
whatever the flags say (a student can always take consent back, as in Notes).
"""

from __future__ import annotations

from django.http import Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.permissions import ParsedAPIView

from . import selectors, services
from . import serializers_ai as ser
from .permissions import RecallAiFlagEnabled, RecallFlagEnabled
from .views import _created_payload


class AiView(ParsedAPIView):
    permission_classes = [IsAuthenticated, RecallFlagEnabled, RecallAiFlagEnabled]


class AiWriteView(AiView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "recall_write"


class AiOverviewView(AiView):
    """`GET ai/`: is AI on for her, her consent, what is left of today's quota, the sources she can pick."""

    def get(self, request):
        return Response(selectors.suggestions.overview(request.user.id))


class AiConsentView(AiView):
    """`GET ai/consent/` the notice and her state; `POST` agrees to the version she read."""

    def get(self, request):
        return Response(selectors.suggestions.consent_state(request.user.id))

    def post(self, request):
        d = self.parse(ser.ConsentSerializer, request.data).validated_data
        services.ai_consent.grant(request.user.id, d["version"])
        return Response(selectors.suggestions.consent_state(request.user.id))


class AiConsentWithdrawView(ParsedAPIView):
    """`POST ai/consent/withdraw/`: open with the flags off. Waiting drafts are deleted."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "recall_write"

    def post(self, request):
        out = services.ai_consent.withdraw(request.user.id)
        return Response({"withdrawn": True, **out})


class SuggestionBatchListView(AiView):
    """`GET suggestions/` her recent batches; `POST` asks for a new one (202 queued, 200 when an earlier one is returned)."""

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_classes, self.throttle_scope = [ScopedRateThrottle], "recall_ai"
        return super().get_throttles()

    def get(self, request):
        q = self.parse(ser.BatchListQuery, request.query_params).validated_data
        views = selectors.suggestions.list_batches(request.user.id, chapter_id=q.get("chapter_id"), limit=q["limit"])
        return Response({"results": [ser.batch_dict(v) for v in views]})

    def post(self, request):
        d = self.parse(ser.SuggestionRequestSerializer, request.data).validated_data
        out = services.suggestions.request_batch(
            request.user.id,
            chapter_id=d["chapter_id"],
            sources=d["sources"],
            pasted_text=d["pasted_text"],
            count=d["count"],
            kinds=d["kinds"],
            client_id=d["client_id"],
        )
        view = selectors.suggestions.get_batch(request.user.id, out.batch.id)
        body = ser.batch_dict(view, estimate_seconds=out.estimate_seconds, reused=out.reused)
        return Response(body, status=202 if out.created else 200)


class SuggestionBatchView(AiView):
    """`GET suggestions/<id>/`: the batch and its drafts; the screen polls it while the status is queued or running."""

    def get(self, request, batch_id):
        view = selectors.suggestions.get_batch(request.user.id, batch_id)
        if view is None:
            raise Http404
        return Response(ser.batch_dict(view))


class SuggestionAcceptView(AiWriteView):
    """`POST suggestions/items/<id>/accept/`: make the card (optionally with her edits). Idempotent."""

    def post(self, request, suggestion_id):
        d = self.parse(ser.AcceptSerializer, request.data).validated_data
        out = services.suggestions.accept(request.user.id, suggestion_id, fields=d.get("fields"), force=d["force"])
        body = _created_payload(request.user.id, out.created)
        body |= {"card_id": str(out.created.card_id), "suggestion": ser.suggestion_dict(out.suggestion)}
        return Response(body, status=200 if out.created.existing else 201)


class SuggestionRejectView(AiWriteView):
    """`POST suggestions/items/<id>/reject/`: not this one; it is not suggested again for 90 days."""

    def post(self, request, suggestion_id):
        out = services.suggestions.reject(request.user.id, suggestion_id)
        return Response({"suggestion": ser.suggestion_dict(out.suggestion)})
