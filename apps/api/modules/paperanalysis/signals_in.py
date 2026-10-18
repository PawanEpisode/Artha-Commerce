"""
Subscribers for question bank events: question_version_live and question_taken_down.
"""

from __future__ import annotations

import logging

from core.events import subscribe

logger = logging.getLogger(__name__)


def on_question_version_live(event: dict) -> None:
    """Checks for drift when a question's mapping changes."""
    # To be wired with flag/service logic in Wave 2
    pass


def on_question_taken_down(event: dict) -> None:
    """Hides question text while preserving marks and statistics facts."""
    # To be wired in Wave 2
    pass


try:
    subscribe("question_version_live", on_question_version_live)
    subscribe("question_taken_down", on_question_taken_down)
except Exception:
    logger.debug("Events bus not ready for subscription yet")
