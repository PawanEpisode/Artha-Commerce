"""Fixtures for the read-side tests: a library of cards in known states, built with a handful of bulk inserts."""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.utils import timezone

from modules.recall.models import RecallCard, RecallDailyRollup, RecallItem, RecallItemVersion

from .factories import fingerprint
from .w5 import ME


def library(
    n: int,
    *,
    user=ME,
    now=None,
    shape=None,
    subjects=("taxation", "laws"),
    kinds=("pointer",),
    chapter_id=None,
    importance=None,
):
    """
    `n` cards. `shape(i)` returns one of `due`, `new`, `later`, `learning`, `learning_tomorrow` (default: cycles through the first
    four). Due cards are 3 days overdue with 10 days of stability. Returns the created cards.
    """
    now = now or timezone.now()
    shape = shape or (lambda i: ("due", "new", "later", "learning")[i % 4])
    items = [
        RecallItem(
            kind=kinds[i % len(kinds)], ownership="user", owner_user_id=user, fingerprint=fingerprint(f"{uuid.uuid4()}")
        )
        for i in range(n)
    ]
    RecallItem.objects.bulk_create(items)
    versions = [
        RecallItemVersion(
            item=it,
            version_no=1,
            state="live",
            fields={"v": 1, "prompt_md": f"Question {i}?", "answer_md": f"Answer {i}"},
            content_hash=fingerprint(f"h{i}{it.id}"),
            plain_text=f"Question {i}?",
        )
        for i, it in enumerate(items)
    ]
    RecallItemVersion.objects.bulk_create(versions)
    cards = []
    for i, (it, v) in enumerate(zip(items, versions, strict=True)):
        kind = shape(i)
        base = {
            "user_id": user,
            "item": it,
            "item_version": v,
            "subject_key": subjects[i % len(subjects)],
            "chapter_id": chapter_id,
            "importance": (i % 3) if importance is None else importance,
        }
        if kind == "new":
            pass
        else:
            due = {
                "due": now - timedelta(days=3),
                "later": now + timedelta(days=5),
                "learning": now - timedelta(minutes=5),
                "learning_tomorrow": now + timedelta(hours=14),
            }[kind]
            base |= {
                "state": 2 if kind in ("due", "later") else 1,
                "step": None if kind in ("due", "later") else 0,
                "stability": 10.0,
                "difficulty": 5.0,
                "due_scheduled_at": due,
                "due_at": due,
                "last_review_at": due - timedelta(days=10 if kind in ("due", "later") else 0, minutes=10),
                "reps": 3,
            }
        cards.append(RecallCard(**base))
    RecallCard.objects.bulk_create(cards)
    return cards


def done_today(user=ME, *, now=None, new=0, reviews=0, **extra):
    """Today's rollup row, as if she had already studied (reviews count as review-phase reviews)."""
    from modules.recall.selectors import load_study

    study = load_study(user, now or timezone.now())
    return RecallDailyRollup.objects.update_or_create(
        user_id=user, local_date=study.today, defaults={"new_cards": new, "review_reviews": reviews, **extra}
    )[0]
