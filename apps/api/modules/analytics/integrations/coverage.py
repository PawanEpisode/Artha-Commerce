"""
Adapter for Coverage Module (F-02 coverage module).
"""

from __future__ import annotations

import logging
import uuid

from modules.coverage import selectors as coverage_selectors
from modules.coverage.models import Rollup

logger = logging.getLogger(__name__)


def get_active_enrollment_id(user_id: uuid.UUID) -> uuid.UUID | None:
    """Returns active enrollment ID or None."""
    try:
        enr = coverage_selectors.get_active_enrollment(user_id)
        return enr.id if enr else None
    except Exception as exc:
        logger.warning("Failed to get active enrollment for user %s: %s", user_id, exc)
        return None


def get_subject_coverage_fractions(user_id: uuid.UUID) -> dict[uuid.UUID, float]:
    """
    Returns dict of subject_id -> coverage_fraction in [0.0, 1.0].
    """
    try:
        enr = coverage_selectors.get_active_enrollment(user_id)
        if not enr:
            return {}

        rollups = Rollup.objects.filter(enrollment=enr, node_type="subject")
        res: dict[uuid.UUID, float] = {}
        for r in rollups:
            pct = float(r.pct_weighted if r.pct_weighted is not None else (r.pct_simple or 0))
            res[r.node_id] = max(0.0, min(1.0, pct / 100.0))
        return res
    except Exception as exc:
        logger.warning("Failed to get subject coverage fractions for user %s: %s", user_id, exc)
        return {}
