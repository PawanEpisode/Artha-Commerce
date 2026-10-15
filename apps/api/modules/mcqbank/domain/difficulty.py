"""
Difficulty domain rules (F-05 ERD 3.5).
Editorial difficulty 1 or 2 is Easy, 3 is Medium, 4 or 5 is Hard, null is "Unrated".
"""

from __future__ import annotations


def format_difficulty_label(difficulty: int | None) -> str:
    """Returns human-readable difficulty label."""
    if difficulty in (1, 2):
        return "Easy"
    if difficulty == 3:
        return "Medium"
    if difficulty in (4, 5):
        return "Hard"
    return "Unrated"


def difficulty_to_band(difficulty: int | None) -> str:
    """Returns canonical difficulty band string: 'easy', 'medium', 'hard', or 'unrated'."""
    if difficulty in (1, 2):
        return "easy"
    if difficulty == 3:
        return "medium"
    if difficulty in (4, 5):
        return "hard"
    return "unrated"
