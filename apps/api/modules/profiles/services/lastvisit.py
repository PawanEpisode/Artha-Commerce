"""Writes for the last visited page. One narrow row per student, updated in place."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db import IntegrityError
from django.utils import timezone

from ..domain.restorable import clean_visit
from ..errors import PathNotRestorable
from ..models import LastVisit
from ..selectors import get_profile

#: The same page reported again inside this window is not written (a tab flipping hidden and visible).
SKIP_WINDOW = timedelta(seconds=60)


def record_visit(user_id, path: str, search: str = "", *, now: datetime | None = None) -> bool:
    """
    Stores the page when it is restorable. Returns False when nothing was written: unchanged and recent, or the
    student no longer exists (a late beacon after account deletion must not bring a row back).
    Raises `PathNotRestorable`.
    """
    cleaned = clean_visit(path, search)
    if cleaned is None:
        raise PathNotRestorable
    if get_profile(user_id) is None:
        return False
    clean_path, clean_search = cleaned
    now = now or timezone.now()

    # One statement: update unless it is the same page seen under a minute ago. Primary key only, no row lock.
    changed = (
        LastVisit.objects.filter(pk=user_id)
        .exclude(path=clean_path, search=clean_search, visited_at__gt=now - SKIP_WINDOW)
        .update(path=clean_path, search=clean_search, visited_at=now)
    )
    if changed:
        return True
    if LastVisit.objects.filter(pk=user_id).exists():
        return False  # the skip rule
    try:
        LastVisit.objects.create(user_id=user_id, path=clean_path, search=clean_search, visited_at=now)
    except IntegrityError:
        return False  # a concurrent first write won
    return True
