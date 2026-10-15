"""
Source categorization domain rules (F-05 ERD 3.5).
Maps source kinds to student-facing category buckets: Institute, Platform, Coaching, Community.
"""

from __future__ import annotations

INSTITUTE_KINDS = {
    "institute_mat",
    "institute_pyq",
    "institute_mtp",
    "institute_rtp",
    "institute_mcq",
}
COACHING_KINDS = {"coaching", "teacher_list"}
PLATFORM_KINDS = {"platform"}
COMMUNITY_KINDS = {"user", "user_created", "user_uploaded"}


def categorize_source_kind(source_kind: str) -> str:
    """Returns top-level source bucket for facets and display."""
    sk = (source_kind or "").lower()
    if sk in INSTITUTE_KINDS:
        return "institute"
    if sk in COACHING_KINDS:
        return "coaching"
    if sk in PLATFORM_KINDS:
        return "platform"
    if sk in COMMUNITY_KINDS:
        return "community"
    return "other"
