"""Fake providers for Today's tests: small, explicit and independent of any real module."""

from __future__ import annotations

import uuid
from datetime import date

from modules.today import registry
from modules.today.registry import (
    DeepLink,
    KindSpec,
    ProviderResult,
    Signals,
    TaskCandidate,
    register_task_provider,
)

TODAY = date(2026, 10, 14)


def candidate(key="k1", kind="fake_mcq", subject_id=None, minutes=10, sig=(50, 50, 50, 50), **over) -> TaskCandidate:
    u, i, w, f = sig
    fields = dict(
        kind=kind,
        dedupe_key=key,
        title=f"Task {key}",
        reason_code="custom",
        reason="because",
        link=DeepLink("/app/revision"),
        est_minutes=minutes,
        signals=Signals(u, i, w, f),
        subject_id=subject_id,
    )
    fields.update(over)
    return TaskCandidate(**fields)


def register_fake(name="fake.mcq", candidates=(), *, kinds=None, **kwargs):
    """Registers a provider that returns the given candidates (or a callable producing them) and returns its calls list."""
    kinds = kinds or [KindSpec("fake_mcq", "practice", "mcq", "ListChecks", 10)]
    calls: list = []

    def provide(request):
        calls.append(request)
        got = candidates(request) if callable(candidates) else candidates
        return got if isinstance(got, ProviderResult) else ProviderResult(candidates=list(got))

    register_task_provider(name, provide, kinds=kinds, label=name, **kwargs)
    return calls


def new_id() -> uuid.UUID:
    return uuid.uuid4()


def clear_providers():
    registry.clear()


def register_practice():
    """A stand-in for the practice engine: one MCQ set and one formula drill per paper, so a plan has a realistic shape."""
    kinds = [
        KindSpec("fake_mcq", "practice", "mcq", "ListChecks", 10),
        KindSpec("fake_formula", "practice", "formula", "Sigma", 8),
    ]

    def offers(request):
        out = []
        for paper in request.ctx.papers:
            out.append(candidate(f"mcq:{paper.key}", "fake_mcq", paper.subject_id, 10, (40, 50, 60, 40)))
            out.append(candidate(f"formula:{paper.key}", "fake_formula", paper.subject_id, 8, (30, 50, 50, 40)))
        return out

    return register_fake("fake.practice", offers, kinds=kinds)
