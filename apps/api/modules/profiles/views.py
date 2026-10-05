"""Thin views: authenticate, parse, call a service or selector, present. No business rules here."""

from __future__ import annotations

import time

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from core.feature_flags import flag_enabled
from core.http import tagged_response

from . import registry, selectors, serializers, services
from .domain.names import InvalidName
from .errors import FieldReadOnly, PersonalizationDisabled, StepNotFound

PERSONALIZATION_FLAG = "personalization"


class ScopedView(APIView):
    """Authenticated, student-scoped writes with a per-scope throttle (set `throttle_scope`)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle, ScopedRateThrottle]


class PersonalizationView(ScopedView):
    """Onboarding and last-visit writes sit behind the `personalization` flag. Reading `/me/` never does."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not flag_enabled(PERSONALIZATION_FLAG, request.user.id):
            raise PersonalizationDisabled


class MeView(ScopedView):
    """GET the bootstrap (profile, avatar, onboarding summary, course, last visit); PATCH the name; DELETE the account."""

    @property
    def throttle_scope(self):
        # Reads are not part of any write budget (no scope, no throttle).
        return {"PATCH": "profile_write", "DELETE": "account_delete"}.get(self.request.method)

    def get(self, request):
        profile, onboarding = services.ensure_student(request.user)
        bootstrap = selectors.bootstrap(profile, onboarding)
        return tagged_response(request, serializers.bootstrap_dict(bootstrap, request.user))

    def patch(self, request):
        stale = [f for f in serializers.MePatchSerializer.DEPRECATED_FIELDS if f in request.data]
        if stale:
            raise FieldReadOnly(extra={"fields": stale})
        s = serializers.MePatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.ensure_student(request.user)
        try:
            services.update_name(request.user.id, s.validated_data["full_name"])
        except InvalidName as exc:
            return Response(
                {"error": {"code": "invalid", "message": str(exc), "details": {"full_name": [str(exc)]}}}, status=400
            )
        profile, onboarding = services.ensure_student(request.user)
        return Response(serializers.bootstrap_dict(selectors.bootstrap(profile, onboarding), request.user))

    def delete(self, request):
        s = serializers.DeleteAccountSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.delete_account(request.user, confirm=s.validated_data["confirm"], now=time.time())
        return Response(status=204)


class ExportView(ScopedView):
    throttle_scope = "account_export"

    def get(self, request):
        return Response(services.export_account(request.user.id))


class OnboardingView(ScopedView):
    """GET the state and the step list."""

    def get_throttles(self):
        return []

    def get(self, request):
        profile, row = services.ensure_student(request.user)
        return Response(serializers.steps_dict(selectors.onboarding_resolution(profile, row)))


class OnboardingStepView(PersonalizationView):
    throttle_scope = "onboarding_write"

    def put(self, request, key):
        handler = registry.get_handler(key)
        if handler is None:
            raise StepNotFound
        services.ensure_student(request.user)
        s = handler.serializer(data=request.data)
        s.is_valid(raise_exception=True)
        resolution = services.save_step(request.user, key, s.validated_data)
        return Response(serializers.steps_dict(resolution))


class OnboardingSkipView(PersonalizationView):
    throttle_scope = "onboarding_write"

    def post(self, request, key):
        services.ensure_student(request.user)
        return Response(serializers.steps_dict(services.skip_step(request.user.id, key)))


class OnboardingCompleteView(PersonalizationView):
    throttle_scope = "onboarding_write"

    def post(self, request):
        services.ensure_student(request.user)
        resolution = services.complete_onboarding(request.user.id)
        # The server's default; the web applies its own precedence (gate, deep link, last visit) after the celebration.
        return Response({"state": serializers.steps_dict(resolution), "destination": "/app"})
