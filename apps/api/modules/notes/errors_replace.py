"""Errors of Replace edition (flag `notes_ai`)."""

from rest_framework import status

from core.errors import CodedError, Conflict


class NotReplaceable(Conflict):
    """409 `not_replaceable`: only a document that is open (ready, not in the trash) can get a newer edition."""

    default_detail = "This document cannot be replaced right now."
    default_code = "not_replaceable"


class AlreadyResolved(Conflict):
    """409 `already_resolved`: the student already decided differently for this mark."""

    default_detail = "You already decided what to do with this mark."
    default_code = "already_resolved"


class NothingToSave(CodedError):
    """422 `nothing_to_save`: the mark has no text or comment, so there is nothing to put in a note."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "This mark has no text to save as a note."
    default_code = "nothing_to_save"


class PageOutOfRange(CodedError):
    """422 `page_out_of_range`: the page is not in the new edition."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That page is not in the new edition."
    default_code = "page_out_of_range"
