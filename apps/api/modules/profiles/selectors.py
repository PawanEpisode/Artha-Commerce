"""Read-only queries for the student. Every function takes the student's id from the verified token, never from input."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.feature_flags import flag_enabled
from modules.coverage import selectors as coverage

from . import registry
from .domain import onboarding as flow
from .models import LastVisit, Onboarding, Profile


def get_profile(user_id) -> Profile | None:
    return Profile.objects.filter(pk=user_id).first()


def email_of(user_id) -> str:
    """The address on the student's profile, or an empty string when there is none (read by modules that send email)."""
    return Profile.objects.filter(pk=user_id).values_list("email", flat=True).first() or ""


def get_last_visit(user_id) -> LastVisit | None:
    return LastVisit.objects.filter(pk=user_id).first()


def stored_state(row: Onboarding) -> flow.Stored:
    return flow.Stored(
        completed_version=row.completed_version,
        started=row.started_at is not None,
        items=(row.steps or {}).get("items", {}),
    )


@dataclass(frozen=True)
class Bootstrap:
    profile: Profile
    onboarding: Onboarding
    resolution: flow.Resolution
    course: coverage.CourseSummary | None
    last_visit: LastVisit | None


def resolve_onboarding(profile: Profile, row: Onboarding, enrollment, settings) -> flow.Resolution:
    facts = flow.Facts(
        user_id=profile.id,
        profile=profile,
        enrollment=enrollment,
        settings=settings,
        stored=stored_state(row),
        flag=lambda name: flag_enabled(name, profile.id),
    )
    return flow.resolve(registry.step_specs(), facts)


def bootstrap(profile: Profile, row: Onboarding, today: date | None = None) -> Bootstrap:
    """
    Everything the web needs at boot in 3 queries on top of the two rows already loaded (profile, onboarding):
    last visit, active enrolment with its course, level and term in one join, and the coverage settings.
    """
    enrollment = coverage.get_active_enrollment(profile.id)
    settings = coverage.get_settings(profile.id)
    return Bootstrap(
        profile=profile,
        onboarding=row,
        resolution=resolve_onboarding(profile, row, enrollment, settings),
        course=coverage.course_summary(profile.id, today, enrollment) if enrollment else None,
        last_visit=get_last_visit(profile.id),
    )


def onboarding_resolution(profile: Profile, row: Onboarding) -> flow.Resolution:
    """The state machine on its own (two queries), for the onboarding endpoints."""
    return resolve_onboarding(
        profile, row, coverage.get_active_enrollment(profile.id), coverage.get_settings(profile.id)
    )


def display_names(user_ids) -> dict:
    """{user_id: name} for features that show other students' names later (mentors, shares). Never emails."""
    return {p.id: p.full_name for p in Profile.objects.filter(pk__in=list(user_ids)).only("id", "full_name")}
