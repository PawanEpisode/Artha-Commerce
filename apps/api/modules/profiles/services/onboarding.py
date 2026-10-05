"""Writes for onboarding: save a step through the owning module, skip an optional step, complete."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core import events
from core.authentication import SupabaseUser

from .. import registry, selectors
from ..domain import onboarding as flow
from ..errors import OnboardingIncomplete, StepMandatory, StepNotFound
from ..models import Onboarding, Profile


def _lock(user_id) -> Onboarding:
    """Row lock, so two tabs saving the same step (or completing together) serialise."""
    return Onboarding.objects.select_for_update().get(pk=user_id)


def _record(row: Onboarding, key: str, state: str) -> None:
    now = timezone.now()
    items = dict((row.steps or {}).get("items", {}))
    items[key] = {"state": state, "at": now.isoformat()}
    row.steps = {"v": 1, "items": items}
    row.current_step = key
    row.started_at = row.started_at or now
    row.save()


def _usable_step(user_id, key: str) -> tuple[flow.StepSpec, Profile, Onboarding]:
    """The step exists, is registered with a handler, and applies to this student (a hidden step is a 404)."""
    spec = registry.get_spec(key)
    if spec is None:
        raise StepNotFound
    profile = Profile.objects.get(pk=user_id)
    row = _lock(user_id)
    resolution = selectors.onboarding_resolution(profile, row)
    view = next((v for v in resolution.steps if v.key == key), None)
    if view is None or view.state is flow.StepState.UNAVAILABLE:
        raise StepNotFound
    return spec, profile, row


@transaction.atomic
def save_step(user: SupabaseUser, key: str, data: dict) -> flow.Resolution:
    """Idempotent: the same data twice leaves the same facts (each owner service is idempotent) and one record."""
    handler = registry.get_handler(key)
    _, profile, row = _usable_step(user.id, key)
    if handler is None:
        raise StepNotFound
    handler.apply(user, data)
    _record(row, key, "done")
    profile.refresh_from_db()
    return selectors.onboarding_resolution(profile, row)


@transaction.atomic
def skip_step(user_id, key: str) -> flow.Resolution:
    spec, profile, row = _usable_step(user_id, key)
    if spec.mandatory:
        raise StepMandatory
    _record(row, key, "skipped")
    return selectors.onboarding_resolution(profile, row)


@transaction.atomic
def complete_onboarding(user_id) -> flow.Resolution:
    """
    Verifies every mandatory step from the facts (409 with the missing keys), then records the version. Calling it
    again is a no-op that returns the same state, so two tabs or a double tap are harmless.
    """
    profile = Profile.objects.get(pk=user_id)
    row = _lock(user_id)
    resolution = selectors.onboarding_resolution(profile, row)
    if resolution.missing:
        raise OnboardingIncomplete(extra={"missing": resolution.missing})
    if row.completed_version >= flow.ONBOARDING_VERSION:
        return resolution
    now = timezone.now()
    row.completed_version = flow.ONBOARDING_VERSION
    row.completed_at = now
    row.started_at = row.started_at or now
    row.save()
    summary = selectors.bootstrap(profile, row)
    transaction.on_commit(
        lambda: events.emit(
            "onboarding_completed",
            user_id=str(user_id),
            version=flow.ONBOARDING_VERSION,
            course=summary.course.course_code if summary.course else None,
            level=summary.course.level_code if summary.course else None,
        )
    )
    return summary.resolution
