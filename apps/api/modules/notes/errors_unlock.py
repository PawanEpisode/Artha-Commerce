"""Errors of Unlock for search (flag `notes_ai`). Codes are what the web branches on."""

from rest_framework import status

from core.errors import CodedError, Conflict


class NotLocked(Conflict):
    """409 `not_locked`: only a PDF that is waiting for its password (and is not in the trash) can be unlocked."""

    default_detail = "This PDF does not need a password to be searched."
    default_code = "not_locked"


class UnlockBusy(Conflict):
    """409 `unlock_in_progress`: a try is already on its way."""

    default_detail = "We are already reading this PDF."
    default_code = "unlock_in_progress"


class TooManyAttempts(CodedError):
    """429 `too_many_attempts`: five wrong passwords in an hour; the lock lifts by itself."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many wrong passwords. Try again in an hour."
    default_code = "too_many_attempts"


class UnlockUnavailable(CodedError):
    """503 `unlock_unavailable`: this deployment has no key to keep a password safe for the few seconds it is needed."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Searching locked PDFs is not available yet."
    default_code = "unlock_unavailable"
