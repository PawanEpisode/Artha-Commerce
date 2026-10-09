"""The scheduler inputs of one student, loaded once per request: settings, `Cfg` and the weight set (ERD 3.5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..domain.fsrs6 import DEFAULT_WEIGHTS, Cfg, MemoryState
from ..domain.scheduling import local_date_of
from ..models import RecallCard, RecallParams, RecallSettings
from . import student


@dataclass(frozen=True)
class Engine:
    settings: RecallSettings
    cfg: Cfg
    weights: tuple[float, ...]
    params_id: object

    def local_date(self, instant: datetime):
        return local_date_of(instant, self.settings.tz, self.settings.day_start_hour)


def load(user_id) -> Engine:
    s = student.settings_for(user_id)
    params = s.params or RecallParams.objects.filter(scope="default", status="active").first()
    weights = tuple(float(x) for x in params.weights) if params is not None else DEFAULT_WEIGHTS
    retention = s.desired_retention if isinstance(s.desired_retention, Decimal) else Decimal(str(s.desired_retention))
    cfg = Cfg(
        desired_retention=float(retention),
        learning_steps=tuple(int(x) for x in s.learning_steps_min),
        relearning_steps=tuple(int(x) for x in s.relearning_steps_min),
        max_interval_days=int(s.max_interval_days),
        fuzz=True,
    )
    return Engine(s, cfg, weights, params.id if params is not None else None)


def memory_of(card: RecallCard) -> MemoryState:
    return MemoryState(
        phase=card.state,
        step=card.step,
        stability=card.stability,
        difficulty=card.difficulty,
        last_review_at=card.last_review_at,
        reps=card.reps,
        lapses=card.lapses,
        last_lapse_at=card.last_lapse_at,
    )
