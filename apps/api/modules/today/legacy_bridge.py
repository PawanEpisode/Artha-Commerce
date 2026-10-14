"""
The `recall.legacy` bridge: Recall's tasks in Today with no change to Recall (BUILD-WAVES section 0).

Recall registered with `core.today_port` (a small stand-in written before Today existed): `collect(user_id, now=)` answers objects with
a `key` and `tasks` carrying `kind`, `title`, `count`, `est_minutes`, `subject_key` and a `target` path relative to `/app/recall`.
This provider calls `collect` and maps each task to a `TaskCandidate`, so the student sees recall cards, forgotten cards, re-checks,
changed decks and quick revision in the General pool (a task with a `subject_key` goes to that paper).

When Recall registers with `today.registry` itself (its own PR), this file and `core/today_port.py` are deleted together. Nothing
else changes: the kinds below are the kinds Recall will declare, with the same names.
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl

from django.utils import timezone

from core import today_port

from .domain.constants import PROVIDER_REASON_MAX, PROVIDER_TITLE_MAX
from .registry import (
    DeepLink,
    KindSpec,
    ProviderResult,
    Signals,
    TaskCandidate,
    TaskRequest,
    register_reason,
    register_task_provider,
)

logger = logging.getLogger(__name__)

NAME = "recall.legacy"
BASE = "/app/recall"

KINDS = (
    KindSpec("recall_cards", "revise", "recall", "Layers", 10),
    KindSpec("forgotten_cards", "revise", "other", "Brain", 5),
    KindSpec("recheck", "news", "amendment", "ShieldCheck", 5),
    KindSpec("cards_changed", "news", "read", "RefreshCw", 3),
    KindSpec("quick_revision", "revise", "revision", "Zap", 10),
)

#: kind -> (dedupe key, reason code, signals as a function of the count)
_RULES = {
    "recall_cards": ("recall:due", "recall_due", lambda n: Signals(min(100, 20 + 2 * n), 60, 50, 40)),
    "forgotten_cards": ("recall:forgotten", "weak_topic", lambda n: Signals(40, 50, 90, 60)),
    "recheck": ("recall:recheck", "amendment_new", lambda n: Signals(70, 60, 30, 40)),
    "cards_changed": ("recall:changed", "deck_updated", lambda n: Signals(30, 40, 20, 60)),
    "quick_revision": ("recall:quick", "exam_close", lambda n: Signals(80, 80, 50, 50)),
}
_REASONS = {
    "recall_cards": "{n} cards are due for recall",
    "forgotten_cards": "Cards you forgot recently",
    "recheck": "{n} cards need a re-check after an update",
    "cards_changed": "{n} cards changed in your decks today",
    "quick_revision": "Your exam is close: today's share of the cards at risk",
}
_COUNTED = {"recall_cards", "forgotten_cards", "recheck", "quick_revision"}  # tasks with a number of cards to finish


def _link(target: str) -> DeepLink:
    path, _, query = (target or "").partition("?")
    path = f"{BASE}/{path.strip('/')}" if path.strip("/") else BASE
    return DeepLink(path, dict(parse_qsl(query)))


def provide(request: TaskRequest) -> ProviderResult:
    papers = {p.key: p.subject_id for p in request.ctx.papers}
    candidates: list[TaskCandidate] = []
    for result in today_port.collect(request.ctx.user_id, now=timezone.now()):
        if result.key != "recall":  # another stand-in provider: it has its own bridge or its own registration
            continue
        for task in result.tasks:
            rule = _RULES.get(task.kind)
            if rule is None or task.count <= 0:
                continue
            subject_key = getattr(task, "subject_key", None)
            if subject_key is not None and subject_key not in papers:
                continue  # a paper the student is no longer enrolled in
            key, reason_code, signals = rule
            candidates.append(
                TaskCandidate(
                    kind=task.kind,
                    dedupe_key=key,
                    title=" ".join(str(task.title).split())[:PROVIDER_TITLE_MAX],
                    reason_code=reason_code,
                    reason=_REASONS[task.kind].format(n=task.count)[:PROVIDER_REASON_MAX],
                    link=_link(getattr(task, "target", "")),
                    est_minutes=max(1, min(int(task.est_minutes or 1), 90)),
                    signals=signals(task.count),
                    subject_id=papers.get(subject_key) if subject_key else None,
                    target_value=min(task.count, 100) if task.kind in _COUNTED else None,
                    payload={"v": 1, "count": task.count},
                )
            )
    return ProviderResult(candidates=candidates[: request.limit])


def register() -> None:
    register_reason(
        "recall_due", label="Cards are due for recall"
    )  # same text as the built-in: harmless on a second call
    register_reason("deck_updated", label="Your decks changed")
    register_reason("exam_close", label="Your exam is close")
    register_task_provider(NAME, provide, kinds=KINDS, label="Recall (legacy port)", timeout_ms=800, max_candidates=5)
