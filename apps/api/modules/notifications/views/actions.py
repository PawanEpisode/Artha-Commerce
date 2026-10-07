"""
Buttons on a timer alert (X-01.1 W3.6). No sign-in: the one-time token in the body is the credential, because the
service worker that sends it has no session. Throttled per address; every refusal looks the same. The body is never
logged or sent to Sentry (`core.sentry`).
"""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from ..serializers import ActionTapSerializer
from ..services import actions as action_service


class ActionsView(APIView):
    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "notifications_action"

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        result = action_service.tap(str(data.get("token") or ""))
        return Response(ActionTapSerializer(result).data)
