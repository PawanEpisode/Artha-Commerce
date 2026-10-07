"""
Public write interface of notes (ERD 3.2). Other modules call these and never import the models.

    documents.reserve_document(...)  PDF uploads, edits, platform documents (R2); document_trash and document_ranges next to it
    notes.create_clip(...)           "Save to notes" from the question bank, previous papers, study material, amendments
    account.delete_all_for_user(id)  registered with `core.registry` for account deletion
    account.export_for_user(id)      registered with `core.registry` for account export
"""

from . import account, annotations, document_ranges, document_trash, documents, quota, recall, settings, tags, trash
from .annotations import AnnotationOp, BatchResult, OpResult, apply_annotation_ops
from .notes import CreateResult, UpdateResult, create_clip, create_note, restore_version, retag_note, update_note
from .recall import CardResult, create_recall_card
from .trash import restore_note, trash_note

__all__ = [
    "documents",
    "document_trash",
    "document_ranges",
    "AnnotationOp",
    "BatchResult",
    "CardResult",
    "OpResult",
    "annotations",
    "apply_annotation_ops",
    "create_recall_card",
    "recall",
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
