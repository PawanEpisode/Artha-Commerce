"""
Public write interface of notes (ERD 3.2). Other modules call these and never import the models.

    notes.create_clip(...)           "Save to notes" from the question bank, previous papers, study material, amendments
    account.delete_all_for_user(id)  registered with `core.registry` for account deletion
    account.export_for_user(id)      registered with `core.registry` for account export
"""

from . import account, quota, settings, tags, trash
from .notes import CreateResult, UpdateResult, create_clip, create_note, restore_version, retag_note, update_note
from .trash import restore_note, trash_note

__all__ = [
    "CreateResult",
    "UpdateResult",
    "account",
    "create_clip",
    "create_note",
    "quota",
    "restore_note",
    "restore_version",
    "retag_note",
    "settings",
    "tags",
    "trash",
    "trash_note",
    "update_note",
]
