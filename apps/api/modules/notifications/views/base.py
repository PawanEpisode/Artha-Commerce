"""Thin views: authenticate, gate, parse, call a service or selector, present."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from ..errors import NotificationsDisabled
from ..flags import ui_enabled


class NotificationsView(APIView):
    """Authenticated, throttled, and behind the environment switch plus the UI flag."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "notifications_read"

    def get_throttles(self):
        # Reads and writes draw from separate budgets.
        self.throttle_scope = "notifications_read" if self.request.method in ("GET", "HEAD") else "notifications_write"
        return super().get_throttles()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not ui_enabled(request.user.id):
            raise NotificationsDisabled
