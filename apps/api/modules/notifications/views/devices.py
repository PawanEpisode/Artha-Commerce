from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from .. import selectors, serializers
from ..services import devices, notify
from .base import NotificationsView


class DevicesView(NotificationsView):
    """GET the student's devices (no secrets); POST a subscription to register or refresh it."""

    def get(self, request):
        return Response({"devices": [serializers.device_dict(row) for row in selectors.list_devices(request.user.id)]})

    def post(self, request):
        s = serializers.DeviceRegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        subscription = data["subscription"]
        registration = devices.register_device(
            request.user.id,
            endpoint=subscription["endpoint"],
            p256dh=subscription["keys"]["p256dh"],
            auth=subscription["keys"]["auth"],
            platform=data["platform"],
            browser=data["browser"],
            display_mode=data["display_mode"],
            sw_version=data.get("sw_version"),
        )
        code = status.HTTP_201_CREATED if registration.created else status.HTTP_200_OK
        return Response({"device_id": str(registration.device.id)}, status=code)


class DeviceDetailView(NotificationsView):
    """DELETE removes one of the student's own devices; repeating it is harmless."""

    def delete(self, request, device_id):
        devices.remove_device(request.user.id, device_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeviceTestView(NotificationsView):
    """POST sends a real test push to one device. Own budget: `notifications_test` (5 a minute)."""

    def scope_for_request(self) -> str:
        return "notifications_test"

    def post(self, request, device_id):
        result = notify.send_test_push(request.user.id, device_id)
        return Response({"result": result.outcome, "reason": result.reason.value if result.reason else None})
