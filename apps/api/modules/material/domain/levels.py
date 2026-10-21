"""
Materialisation level calculation from source capabilities (F-12 PRD 4.3, ERD 3.3).
"""

from __future__ import annotations

from typing import Iterable


LEVEL_0_CAPS = {"metadata"}
LEVEL_1_CAPS = LEVEL_0_CAPS | {"link_out"}
LEVEL_2_CAPS = LEVEL_1_CAPS | {"host_questions", "host_solutions"}
LEVEL_3_CAPS = LEVEL_2_CAPS | {"practice"}
LEVEL_4_CAPS = LEVEL_3_CAPS | {"public_seo"}


def level_for(capabilities: Iterable[str]) -> int:
    """
    Computes the maximum materialisation level for a set of capabilities:
    L0: metadata
    L1: link_out
    L2: host_questions and host_solutions
    L3: practice
    L4: public_seo
    """
    caps = set(capabilities)

    if LEVEL_4_CAPS.issubset(caps):
        return 4
    if LEVEL_3_CAPS.issubset(caps):
        return 3
    if LEVEL_2_CAPS.issubset(caps):
        return 2
    if LEVEL_1_CAPS.issubset(caps):
        return 1
    if LEVEL_0_CAPS.issubset(caps):
        return 0

    return 0


def required_capabilities_for_level(level: int) -> set[str]:
    """
    Returns the required capabilities set for a given materialisation level.
    """
    if level >= 4:
        return set(LEVEL_4_CAPS)
    if level == 3:
        return set(LEVEL_3_CAPS)
    if level == 2:
        return set(LEVEL_2_CAPS)
    if level == 1:
        return set(LEVEL_1_CAPS)
    return set(LEVEL_0_CAPS)
