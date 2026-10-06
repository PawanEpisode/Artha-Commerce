"""
How each built-in onboarding step is saved: validate (DRF serializer) then call the OWNING module's service, so no
business rule is duplicated here. Registered into `registry` by `ProfilesConfig.ready`. A step that changes data the
student cannot afford to lose is idempotent because the owner's service is.
"""

from __future__ import annotations

from rest_framework import serializers

from core.authentication import SupabaseUser
from modules.coverage import selectors as coverage_selectors
from modules.coverage import serializers as coverage_serializers
from modules.coverage import services as coverage
from modules.coverage.errors import CoverageError, to_api_exception
from modules.notifications import selectors as notifications_selectors
from modules.tracking import selectors as tracking_selectors
from modules.tracking import services as tracking

from . import registry
from .domain.names import InvalidName
from .domain.onboarding import StepSpec
from .services.profile import update_name


class ProfileStepSerializer(serializers.Serializer):
    full_name = serializers.CharField(trim_whitespace=False)


class CourseStepSerializer(serializers.Serializer):
    scheme = serializers.UUIDField()
    target_term = serializers.UUIDField(required=False, allow_null=True)
    exam_date = serializers.DateField(required=False, allow_null=True)
    electives = coverage_serializers.ElectiveChoicesField(required=False)


class HoursStepSerializer(serializers.Serializer):
    daily_minutes = serializers.IntegerField(min_value=15, max_value=960)
    use_as_goal = serializers.BooleanField(required=False, default=True)


class TargetsStepSerializer(coverage_serializers.TargetsSerializer):
    pass


class CatchupStepSerializer(serializers.Serializer):
    chapter_ids = serializers.ListField(child=serializers.UUIDField(), max_length=300, required=False, default=list)
    also_revised = serializers.BooleanField(required=False, default=False)


class AcknowledgeSerializer(serializers.Serializer):
    """The avatar step has no data of its own (the avatar endpoints save it); this just records that it was seen."""


def _coverage_errors(fn):
    """Coverage services raise their own domain errors; the API speaks one error shape."""

    def wrapper(user, data):
        try:
            return fn(user, data)
        except CoverageError as exc:
            raise to_api_exception(exc) from exc

    return wrapper


def _apply_profile(user: SupabaseUser, data: dict) -> None:
    try:
        update_name(user.id, data["full_name"])
    except InvalidName as exc:
        raise serializers.ValidationError({"full_name": [str(exc)]}) from exc


@_coverage_errors
def _apply_course(user: SupabaseUser, data: dict) -> None:
    """Same scheme: update term and date. Same level, other scheme: switch (progress carries over). Else enrol."""
    current = coverage_selectors.get_active_enrollment(user.id)
    scheme_id = data["scheme"]
    term_id, exam_date = data.get("target_term"), data.get("exam_date")
    if current and str(current.scheme_id) == str(scheme_id):
        patch = {"exam_date": exam_date} if "exam_date" in data else {}
        if "target_term" in data:
            term = coverage_selectors.get_term(term_id)
            if term_id and term is None:
                raise serializers.ValidationError({"target_term": ["Unknown exam term."]})
            patch["target_term"] = term
        if patch:
            coverage.update_enrollment(current, data=patch)
        if data.get("electives"):
            coverage.set_electives(current, data["electives"])
        return
    if current and coverage_selectors.scheme_level_id(scheme_id) == current.level_id:
        current, _ = coverage.switch_scheme(user.id, current, scheme_id, target_term_id=term_id)
        coverage.update_enrollment(current, data={"exam_date": exam_date} if "exam_date" in data else {})
        return
    coverage.create_enrollment(
        user.id, scheme_id=scheme_id, target_term_id=term_id, exam_date=exam_date, electives=data.get("electives")
    )


@_coverage_errors
def _apply_hours(user: SupabaseUser, data: dict) -> None:
    enrollment = coverage_selectors.get_active_enrollment(user.id)
    if enrollment is None:
        raise serializers.ValidationError({"detail": "Choose your course first."})
    coverage.update_enrollment(enrollment, data={"daily_minutes": data["daily_minutes"]})
    if data.get("use_as_goal") and not tracking_selectors.has_daily_goal(user.id):
        tracking.set_goals(user.id, [{"period": "daily", "target_minutes": data["daily_minutes"]}])


@_coverage_errors
def _apply_targets(user: SupabaseUser, data: dict) -> None:
    coverage.save_settings(user.id, new_targets=coverage_serializers.targets_from(data))


@_coverage_errors
def _apply_catchup(user: SupabaseUser, data: dict) -> None:
    if data["chapter_ids"]:
        coverage.catchup(user.id, data["chapter_ids"], also_revised=data["also_revised"])


def _apply_nothing(user: SupabaseUser, data: dict) -> None:
    return None


def _apply_alerts(user: SupabaseUser, data: dict) -> None:
    """
    The web records the browser result through `POST notifications/permission-state/` first (that is the consent
    record); this only confirms a decision exists, so the step can never be marked done without one (facts over flags).
    """
    if not notifications_selectors.permission_decided(user.id):
        raise serializers.ValidationError({"detail": "Choose an option for alerts first."})


HANDLERS = {
    "profile": registry.StepHandler(ProfileStepSerializer, _apply_profile),
    "course": registry.StepHandler(CourseStepSerializer, _apply_course),
    "hours": registry.StepHandler(HoursStepSerializer, _apply_hours),
    "targets": registry.StepHandler(TargetsStepSerializer, _apply_targets),
    "catchup": registry.StepHandler(CatchupStepSerializer, _apply_catchup),
    "avatar": registry.StepHandler(AcknowledgeSerializer, _apply_nothing),
}


#: X-01.1 W2.5. Optional (every outcome, including "Not now", finishes it), shown only while the notifications UI is
#: on for this student (environment switch and `notifications_ui` flag), done once a decision is recorded.
ALERTS = StepSpec(
    "alerts",
    80,
    False,
    3,
    lambda f: notifications_selectors.permission_decided(f.user_id),
    available=lambda f: notifications_selectors.ui_enabled(f.user_id),
)
ALERTS_HANDLER = registry.StepHandler(AcknowledgeSerializer, _apply_alerts)


def register_built_in_handlers() -> None:
    for key, handler in HANDLERS.items():
        registry.register_handler(key, handler)
    registry.register_onboarding_step(ALERTS, ALERTS_HANDLER)
