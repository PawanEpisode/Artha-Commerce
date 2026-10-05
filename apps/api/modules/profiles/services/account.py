"""Account data rights (DPDP): export everything, delete everything. Modules take part through `core.registry`."""

from __future__ import annotations

import hashlib
import logging
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core import auth_admin, events, registry
from core.authentication import SupabaseUser, recent_authentication
from core.storage import get_storage

from .. import selectors
from ..avatar_urls import avatar_summary
from ..errors import ConfirmationRequired, DeletionIncomplete, ReauthRequired
from ..models import LastVisit, Onboarding, Profile, StorageDelete

logger = logging.getLogger(__name__)

CONFIRM_WORD = "DELETE"


def export_account(user_id) -> dict:
    """Profile, onboarding, last visit and avatar, plus whatever each registered module holds for the student."""
    profile = selectors.get_profile(user_id)
    onboarding = Onboarding.objects.filter(pk=user_id).first()
    visit = selectors.get_last_visit(user_id)
    out = {
        "exported_at": timezone.now().isoformat(),
        "profile": None
        if profile is None
        else {
            "email": profile.email,
            "full_name": profile.full_name,
            "avatar": avatar_summary(profile),
            "created_at": profile.created_at.isoformat(),
        },
        "onboarding": None
        if onboarding is None
        else {
            "completed_version": onboarding.completed_version,
            "completed_at": onboarding.completed_at.isoformat() if onboarding.completed_at else None,
            "steps": (onboarding.steps or {}).get("items", {}),
        },
        "last_visit": None if visit is None else {"path": visit.path, "visited_at": visit.visited_at.isoformat()},
        "modules": {},
    }
    for name, exporter in registry.exporters():
        out["modules"][name] = exporter(user_id)
    return out


def _delete_avatar_files(user_id) -> None:
    """Every object under the student's prefix, including ones queued for a retry. Idempotent."""
    storage = get_storage()
    bucket = settings.SUPABASE_AVATAR_BUCKET
    paths = storage.list_prefix(bucket, str(user_id))
    storage.delete(bucket, paths)


def delete_account(user: SupabaseUser, *, confirm: str, now: float | None = None) -> None:
    """
    Needs the typed word and a recent authentication. Order: every module's eraser (dependents first), the avatar
    files, the profile rows, then the Supabase user. Each step is idempotent, so after a failure the same call can be
    repeated safely; the error says which steps finished.
    """
    if confirm != CONFIRM_WORD:
        raise ConfirmationRequired
    if not recent_authentication(user.claims, now=now if now is not None else time.time()):
        raise ReauthRequired

    done: list[str] = []

    def step(name: str, action) -> None:
        try:
            action()
        except Exception:
            logger.exception("Account deletion failed at %s", name)
            raise DeletionIncomplete(done, name) from None
        done.append(name)

    for name, eraser in registry.erasers():
        step(name, lambda eraser=eraser: eraser(user.id))
    step("avatar_files", lambda: _delete_avatar_files(user.id))
    step("profile", lambda: _delete_profile_rows(user.id))
    step("auth", lambda: auth_admin.delete_user(user.id))
    events.emit("account_deleted", user_ref=hashlib.sha256(str(user.id).encode()).hexdigest()[:16], modules=len(done))


@transaction.atomic
def _delete_profile_rows(user_id) -> None:
    LastVisit.objects.filter(pk=user_id).delete()
    StorageDelete.objects.filter(user_id=user_id).delete()
    Onboarding.objects.filter(pk=user_id).delete()
    Profile.objects.filter(pk=user_id).delete()
