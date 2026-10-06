from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from .. import selectors, serializers
from ..services import inbox
from .base import NotificationsView


class InboxClickView(NotificationsView):
    """POST: the page opened from a notification reports it. Marks read and clicked; 204, 404 for someone else's."""

    def post(self, request, notification_id):
        inbox.mark_clicked(request.user.id, notification_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InboxView(NotificationsView):
    """GET the student's inbox: newest first, cursor paged, the last 50 at most, with the unread count."""

    def get(self, request):
        q = serializers.InboxQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        rows, next_cursor = selectors.list_inbox(
            request.user.id, cursor=q.validated_data.get("cursor"), limit=q.validated_data["limit"]
        )
        return Response(
            {
                "results": [serializers.inbox_item_dict(r) for r in rows],
                "next_cursor": next_cursor,
                "unread_count": selectors.unread_count(request.user.id),
            }
        )


class InboxReadView(NotificationsView):
    """POST mark some or all read; answers with the new unread count."""

    def post(self, request):
        s = serializers.InboxReadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        inbox.mark_read(request.user.id, ids=s.validated_data.get("ids"))
        return Response({"unread_count": selectors.unread_count(request.user.id)})
