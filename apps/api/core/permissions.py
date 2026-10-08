"""Reusable DRF building blocks shared by every feature module's views."""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.views import APIView

from core.errors import FeatureDisabled
from core.feature_flags import flag_enabled


def flag_required(flag: str, error: type[Exception] = FeatureDisabled, *, strict: bool = False) -> type[BasePermission]:
    """
    A permission class for one PostHog flag. Off for this student means `error` (403 `feature_disabled` by default), so
    a module gates every endpoint the same way and the web shows its own "not available yet" state. Fails open like the
    web hook (`core.feature_flags`): only an explicit off blocks. `strict=True` fails closed (only an explicit on counts):
    for features that cost money or send content to a third party.
    """

    class FlagEnabled(BasePermission):
        def has_permission(self, request, view):
            if not flag_enabled(flag, request.user.id, strict=strict):
                raise error
            return True

    FlagEnabled.__name__ = f"FlagEnabled_{flag}"
    return FlagEnabled


class ParsedAPIView(APIView):
    """`self.parse(Serializer, data)` validates at the edge and returns the serializer (400 with field errors)."""

    def parse(self, serializer_class, data, **kwargs):
        serializer = serializer_class(data=data, **kwargs)
        serializer.is_valid(raise_exception=True)
        return serializer
