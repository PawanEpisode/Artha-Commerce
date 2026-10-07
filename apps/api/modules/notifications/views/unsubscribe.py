"""
The public unsubscribe endpoint (X-01.1 W3.5). No login: the signed token in the link is the credential. GET tells the
web page what the link is for; POST switches the email off (also what a mail client sends for List-Unsubscribe-Post,
RFC 8058, as a form post to the same URL). Always available, even when notifications are switched off: a student who
asks to stop is always honoured. Throttled per address.
"""

from __future__ import annotations

from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from ..services import unsubscribe as unsubscribe_service


class UnsubscribeView(APIView):
    authentication_classes: list = []
    permission_classes: list = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "notifications_unsubscribe"
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def _token(self, request) -> str:
        data = request.data if hasattr(request.data, "get") else {}
        return request.query_params.get("t") or data.get("token") or ""

    def get(self, request):
        target = unsubscribe_service.read(self._token(request))
        return Response({"category": target.category, "label": target.label, "unsubscribed": False})

    def post(self, request):
        target = unsubscribe_service.unsubscribe(self._token(request))
        return Response({"category": target.category, "label": target.label, "unsubscribed": True})
