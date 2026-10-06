from __future__ import annotations

from rest_framework.response import Response

from .. import selectors, serializers
from ..services import permission
from ..services import settings as settings_service
from .base import NotificationsView


class SettingsView(NotificationsView):
    """GET the student's settings (defaults until they change something); PUT a partial change."""

    def get(self, request):
        return Response(serializers.settings_dict(selectors.get_settings(request.user.id)))

    def put(self, request):
        s = serializers.SettingsWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        row = settings_service.update_settings(request.user.id, dict(s.validated_data))
        return Response(serializers.settings_dict(row))


class PermissionStateView(NotificationsView):
    """POST what the browser said (or that the student chose to skip). Safe to repeat."""

    def post(self, request):
        s = serializers.PermissionStateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        row = permission.record_permission_state(request.user.id, **s.validated_data)
        return Response(serializers.settings_dict(row))
