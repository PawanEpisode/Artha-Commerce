"""Public write interface of the profiles module (views and other modules import from here only)."""

from .account import CONFIRM_WORD, delete_account, export_account
from .avatar import remove_avatar, set_preset, set_upload
from .lastvisit import record_visit
from .onboarding import complete_onboarding, save_step, skip_step
from .profile import (
    ensure_student,
    get_or_create_onboarding,
    get_or_create_profile,
    update_name,
)

__all__ = [
    "CONFIRM_WORD",
    "complete_onboarding",
    "delete_account",
    "ensure_student",
    "export_account",
    "get_or_create_onboarding",
    "get_or_create_profile",
    "record_visit",
    "remove_avatar",
    "save_step",
    "set_preset",
    "set_upload",
    "skip_step",
    "update_name",
]
