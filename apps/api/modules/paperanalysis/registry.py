"""
Registries and extension points for F-11 Paper Analysis.
Reference: ERD 3.3.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol
from uuid import UUID

from .domain.types import PaperRef, PaperView, WeaknessSignal


class PaperSource(Protocol):
    def get_paper(self, origin_ref: str) -> PaperView: ...
    def list_papers(self, subject_key: str, scheme_id: UUID | None = None) -> list[PaperRef]: ...


WeaknessSourceFn = Callable[[UUID, Sequence[UUID]], Mapping[UUID, WeaknessSignal]]

_paper_sources: dict[str, PaperSource] = {}
_weakness_sources: list[tuple[int, str, WeaknessSourceFn]] = []


def register_paper_source(origin_module: str, source: PaperSource) -> None:
    """Registers an origin module paper source (e.g., 'pyq', 'mtp')."""
    _paper_sources[origin_module] = source


def get_paper_source(origin_module: str) -> PaperSource | None:
    return _paper_sources.get(origin_module)


def register_weakness_source(name: str, fn: WeaknessSourceFn, *, priority: int = 100) -> None:
    """Registers a weakness source. Lowest priority number wins."""
    global _weakness_sources
    # Remove existing with same name if any
    _weakness_sources = [s for s in _weakness_sources if s[1] != name]
    _weakness_sources.append((priority, name, fn))
    _weakness_sources.sort(key=lambda item: item[0])


def get_weakness_signals(user_id: UUID, chapter_ids: Sequence[UUID]) -> dict[UUID, WeaknessSignal]:
    """Resolves weakness signals across registered sources by priority."""
    result: dict[UUID, WeaknessSignal] = {}
    if not chapter_ids or not _weakness_sources:
        return result

    for _prio, _name, fn in _weakness_sources:
        try:
            signals = fn(user_id, chapter_ids)
            for cid, sig in signals.items():
                if cid not in result:
                    result[cid] = sig
        except Exception:
            continue
    return result
