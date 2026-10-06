"""Errors of the notifications module. Each class carries the `default_code` the web branches on."""

from rest_framework import status

from core.errors import CodedError, Conflict, FeatureDisabled


class NotificationsDisabled(FeatureDisabled):
    default_detail = "Notifications are not available yet."
    default_code = "notifications_disabled"


class InvalidSettings(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Those notification settings are not valid."
    default_code = "invalid"


class DeviceLimit(Conflict):
    default_detail = "You have too many devices. Remove one first."
    default_code = "device_limit"


class InvalidEndpoint(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "That push address is not accepted."
    default_code = "invalid_endpoint"


class InvalidDeepLink(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "That link is not allowed."
    default_code = "invalid_deep_link"
