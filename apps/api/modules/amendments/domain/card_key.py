from __future__ import annotations

import re


def _slugify(text: str) -> str:
    """Normalize text to lowercase alphanumeric with hyphens."""
    cleaned = text.replace("_", "-")
    cleaned = re.sub(r"[^\w\s-]", "", cleaned).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned)


def generate_card_key(
    law_key: str,
    provision_label: str,
    change_type: str,
    title: str = "",
) -> str:
    """
    Generates a deterministic, normalized key for a change card that remains stable across
    document re-issues and revisions.

    Format:
        {normalized_law}:{normalized_provision}:{normalized_type}[:optional_title_stem]
    Max length 120 chars.
    """
    norm_law = _slugify(law_key or "general")[:30].strip("-")
    norm_provision = _slugify(provision_label or "misc")[:40].strip("-")
    norm_type = _slugify(change_type or "modification")[:20].strip("-")

    base = f"{norm_law}:{norm_provision}:{norm_type}"

    if title:
        title_stem = _slugify(title)[:25].strip("-")
        if title_stem:
            key = f"{base}:{title_stem}"
            return key[:120]

    return base[:120]
