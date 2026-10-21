"""
Palette state resolution for F-08 Mock Tests (FR-F08-26).
"""

from __future__ import annotations

from typing import Literal


PaletteStatus = Literal[
    "not_visited",
    "not_answered",
    "answered",
    "marked",
    "answered_marked",
    "not_counted",
    "locked",
    "pages_ready",
]


def determine_palette_status(
    *,
    visited: bool,
    answered: bool,
    marked_for_review: bool,
    section_closed: bool = False,
    is_not_counted: bool = False,
    has_pages: bool = False,
) -> PaletteStatus:
    """
    Computes single palette status enum value for UI display and accessibility.
    """
    if is_not_counted:
        return "not_counted"
    if section_closed:
        return "locked"
    if has_pages:
        return "pages_ready"
    if answered and marked_for_review:
        return "answered_marked"
    if marked_for_review:
        return "marked"
    if answered:
        return "answered"
    if visited:
        return "not_answered"
    return "not_visited"
