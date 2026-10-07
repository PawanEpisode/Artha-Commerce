from __future__ import annotations

from rest_framework.response import Response

from .. import serializers
from ..services import thought
from .base import NotificationsView


class ThoughtTodayView(NotificationsView):
    """
    GET today's thought for the first open of the student's local day. The first call picks and records it; every later
    call that day answers the same one. `thought` is null when there is nothing to show (the library is empty or fully
    seen in the last 60 days, or the student switched the Daily thought category off for the app).
    """

    def get(self, request):
        return Response(serializers.thought_response(thought.todays_thought(request.user.id)))
