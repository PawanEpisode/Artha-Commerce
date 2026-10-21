"""
Registration with F-06 practice origin registry for F-12 Institute Study Material.
"""

from __future__ import annotations

from typing import Any

from modules.practice.registry import OriginSpec, register_origin


def register_origins() -> None:
    """
    Registers 'material' origin with practice module (ERD 3.4).
    """
    register_origin(
        "material",
        OriginSpec(
            allowed_modes={"untimed", "timed", "chapter_quiz", "revision"},
            default_feedback_policy="instant",
            unique_per_user=False,
            title_for=lambda spec: f"Study Material Practice: {spec.get('title', 'Chapter Items')}",
        ),
    )
