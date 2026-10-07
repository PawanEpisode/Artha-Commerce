"""Reading a stored file for the worker: the original PDF to a temp file, in range reads, capped (ERD 6.5)."""

from __future__ import annotations

import os

from core.storage import StorageError
from modules.media import services as media
from modules.media.scanner import TooLarge, object_chunks

SLACK_BYTES = 1024 * 1024  # the declared size is a promise, not a measurement


class SourceMissing(Exception):
    """The object is gone or storage cannot serve it; the job retries, and fails after its attempts."""


class SourceTooLarge(Exception):
    pass


def download_to(path: str | os.PathLike, attachment, *, limit: int) -> int:
    """Writes the attachment's object to `path` (replacing it) and returns the byte count. Never holds the file in memory."""
    total = 0
    try:
        with open(path, "wb") as out:
            for piece in object_chunks(
                media.get_storage(), attachment.bucket, attachment.path, limit=limit + SLACK_BYTES
            ):
                out.write(piece)
                total += len(piece)
    except TooLarge as exc:
        raise SourceTooLarge from exc
    except StorageError as exc:
        raise SourceMissing(str(exc)[:200]) from exc
    if total == 0:
        raise SourceMissing("The object is empty.")
    return total
