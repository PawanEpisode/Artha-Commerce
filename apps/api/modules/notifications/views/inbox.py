from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from ..services import inbox
from .base import NotificationsView


class InboxClickView(NotificationsView):
    """POST: the page opened from a notification reports it. Marks read and clicked; 204, 404 for someone else's."""

    def post(self, request, notification_id):
        inbox.mark_clicked(request.user.id, notification_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
