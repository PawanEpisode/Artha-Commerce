"""
Key string parser for F-08 Mock Tests (FR-F08-55).
Parses answer keys like '1-A 2-C 3-B' or '1. A\\n2. C' into position-key pairs.
"""

from __future__ import annotations

import re
from typing import Any


def parse_key_string(text: str) -> list[dict[str, Any]]:
    """
    Parses a string containing question numbers and answers.
    Supported patterns:
      '1-A 2-B 3-C'
      '1. A 2. B'
      '1: A, 2: B'
      'Q1: A, Q2: B'
      '1 - A\\n2 - B'
    Returns list of dicts: [{'position': int, 'key': str}] sorted by position.
    """
    if not text or not text.strip():
        return []

    cleaned = text.strip()

    # Pattern matches: optional 'Q' or 'q', digits (position), separator (:.- or spaces), followed by option letter or word
    pattern = re.compile(
        r"(?:[Qq]\.?\s*)?(\d+)[\s.:\-\)]+\s*([A-Za-z0-9_\.\-]+)",
        re.MULTILINE,
    )

    results: dict[int, str] = {}
    for match in pattern.finditer(cleaned):
        pos_str, key_val = match.groups()
        try:
            pos = int(pos_str)
            results[pos] = key_val.strip().upper()
        except ValueError:
            continue

    sorted_items = [{"position": pos, "key": results[pos]} for pos in sorted(results.keys())]
    return sorted_items
