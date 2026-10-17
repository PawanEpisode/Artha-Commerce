"""
Registration for analytics-originated practice sessions (origin 'analytics_fix').
"""

from __future__ import annotations

from modules.practice.registry import OriginSpec, register_origin


def register_analytics_origins() -> None:
    """Registers origin 'analytics_fix' in practice registry."""
    register_origin(
        "analytics_fix",
        OriginSpec(
            allowed_modes={"revision", "untimed", "timed"},
            default_feedback_policy="instant",
            unique_per_user=False,
        ),
    )
