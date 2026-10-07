"""
The daily digest offer and switch (X-01.1 W3.7, FR-N34). GET says whether the offer is due and whether the digest is
on; POST records an answer: `seen` (the card was shown), `accept`, `decline`, or `stop` (back to separate alerts).
"""

from __future__ import annotations

from rest_framework.response import Response

from .. import selectors, serializers
from ..selectors import fatigue as fatigue_selectors
from ..services import digest as digest_service
from .base import NotificationsView


def _state(user_id, row=None) -> dict:
    row = row or selectors.get_settings(user_id)
    return serializers.digest_dict(row, offer=fatigue_selectors.digest_offer_due(user_id))


class DigestView(NotificationsView):
    def get(self, request):
        return Response(_state(request.user.id))

    def post(self, request):
        s = serializers.DigestAnswerSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        row = digest_service.answer(request.user.id, digest_service.Answer(s.validated_data["answer"]))
        return Response(_state(request.user.id, row))
