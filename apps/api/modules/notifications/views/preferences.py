from __future__ import annotations

from rest_framework.response import Response

from .. import selectors, serializers
from ..services import preferences
from .base import NotificationsView


class CategoriesView(NotificationsView):
    """GET the catalogue merged with the student's switches."""

    def get(self, request):
        return Response({"categories": selectors.category_view(request.user.id)})


class PreferencesView(NotificationsView):
    """PUT a bulk change of switches; answers with the merged catalogue."""

    def put(self, request):
        s = serializers.PreferencesWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        items = [(p["category"], p["channel"], p["enabled"]) for p in s.validated_data["preferences"]]
        preferences.set_preferences(request.user.id, items)
        return Response({"categories": selectors.category_view(request.user.id)})
