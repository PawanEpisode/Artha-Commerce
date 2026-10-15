"""
Domain property and unit tests for MCQ Bank (F-05 ERD 3.5).
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from modules.mcqbank.domain.adaptive import (
    predict_success_probability,
    update_theta_from_answers,
)
from modules.mcqbank.domain.blueprint import (
    allocate_difficulty_mix,
    allocate_quotas,
    apply_smart_mix,
)
from modules.mcqbank.domain.difficulty import difficulty_to_band, format_difficulty_label
from modules.mcqbank.domain.links import is_safe_linkout_url
from modules.mcqbank.domain.negative_insight import (
    AnswerInsightInput,
    compute_negative_insight,
)
from modules.mcqbank.domain.pattern import resolve_pattern_profile
from modules.mcqbank.domain.sources import categorize_source_kind


def test_difficulty_formatting():
    assert format_difficulty_label(1) == "Easy"
    assert format_difficulty_label(2) == "Easy"
    assert format_difficulty_label(3) == "Medium"
    assert format_difficulty_label(4) == "Hard"
    assert format_difficulty_label(5) == "Hard"
    assert format_difficulty_label(None) == "Unrated"

    assert difficulty_to_band(2) == "easy"
    assert difficulty_to_band(3) == "medium"
    assert difficulty_to_band(4) == "hard"
    assert difficulty_to_band(None) == "unrated"


def test_sources_categorization():
    assert categorize_source_kind("institute_mat") == "institute"
    assert categorize_source_kind("institute_pyq") == "institute"
    assert categorize_source_kind("coaching") == "coaching"
    assert categorize_source_kind("teacher_list") == "coaching"
    assert categorize_source_kind("platform") == "platform"
    assert categorize_source_kind("user") == "community"


def test_blueprint_quota_allocation_properties():
    ch_keys = ["ch1", "ch2", "ch3"]
    weights = [10.0, 20.0, 30.0]
    avail = [5, 10, 20]

    quotas = allocate_quotas(15, ch_keys, weights, avail)
    # Total sum equals target
    assert sum(quotas.values()) == 15
    # Capped at availability
    for k, q in quotas.items():
        idx = ch_keys.index(k)
        assert 0 <= q <= avail[idx]

    # Monotonicity test: raising count never lowers a quota
    q1 = allocate_quotas(10, ch_keys, weights, avail)
    q2 = allocate_quotas(15, ch_keys, weights, avail)
    for k in ch_keys:
        assert q2[k] >= q1[k]


def test_blueprint_quota_exceeding_capacity():
    ch_keys = ["ch1", "ch2"]
    weights = [1.0, 1.0]
    avail = [3, 4]  # total capacity 7

    quotas = allocate_quotas(10, ch_keys, weights, avail)
    assert sum(quotas.values()) == 7
    assert quotas["ch1"] == 3
    assert quotas["ch2"] == 4


def test_difficulty_mix_allocation():
    mix = allocate_difficulty_mix(10, (3, 5, 2))
    assert sum(mix.values()) == 10
    assert mix["easy"] == 3
    assert mix["medium"] == 5
    assert mix["hard"] == 2

    # With shortage: only 1 easy available, 1 hard available -> rest filled by medium
    avail = {"easy": 1, "medium": 15, "hard": 1}
    mix_short = allocate_difficulty_mix(10, (3, 5, 2), available_by_diff=avail)
    assert sum(mix_short.values()) == 10
    assert mix_short["easy"] == 1
    assert mix_short["hard"] == 1
    assert mix_short["medium"] == 8


def test_smart_mix_priority():
    unseen = [1, 2, 3]
    wrong = [4, 5]
    due = [6]
    others = [7, 8, 9]

    # Pick 4: should be all 3 unseen + 1 wrong
    picked = apply_smart_mix(unseen, wrong, due, others, 4)
    assert picked == [1, 2, 3, 4]

    # Deduplication in priority order
    unseen_overlap = [1, 2]
    wrong_overlap = [2, 3]  # 2 already in unseen
    picked_dedup = apply_smart_mix(unseen_overlap, wrong_overlap, [], [], 3)
    assert picked_dedup == [1, 2, 3]


def test_negative_insight_exact_vector():
    """
    Test vector from ERD 3.5:
    11 guesses, 4 right at +1, 7 wrong at -0.25
    gives net_guess = 2.25, accuracy = 36.4%, break_even = 20%.
    """
    answers = []
    # 4 correct guesses
    for _ in range(4):
        answers.append(
            AnswerInsightInput(
                result="correct",
                confidence=3,  # guess
                marks_max=Decimal("1.0"),
                negative_max=Decimal("0.25"),
                marks_awarded=Decimal("1.0"),
                negative_applied=Decimal("0.0"),
            )
        )
    # 7 incorrect guesses
    for _ in range(7):
        answers.append(
            AnswerInsightInput(
                result="incorrect",
                confidence=3,  # guess
                marks_max=Decimal("1.0"),
                negative_max=Decimal("0.25"),
                marks_awarded=Decimal("-0.25"),
                negative_applied=Decimal("0.25"),
            )
        )

    report = compute_negative_insight(answers)

    assert report.total_penalties == Decimal("1.75")
    assert report.penalised_count == 7
    assert report.break_even_pct == 20.0
    assert report.guess.count == 11
    assert report.guess.correct_count == 4
    assert report.guess.accuracy_pct == 36.4
    assert report.guess.net_marks == Decimal("2.25")
    assert report.guess.paying_off is True


def test_adaptive_theta_and_probability():
    # P(correct | theta=0, b=0) == 0.5
    assert predict_success_probability(0.0, 0.0) == 0.5
    # Harder item has lower P
    assert predict_success_probability(0.0, 1.5) < 0.5
    # Easier item has higher P
    assert predict_success_probability(0.0, -1.5) > 0.5

    # Theta updates: all correct answers increases theta
    answers = [("correct", 0.0), ("correct", 0.5), ("correct", -0.5)]
    new_theta, new_n, correct_cnt = update_theta_from_answers(0.0, answers, 0)
    assert new_theta > 0.0
    assert new_n == 3
    assert correct_cnt == 3

    # Skipped answers do not change theta
    skipped_theta, skip_n, _ = update_theta_from_answers(new_theta, [("skipped", 0.0)], new_n)
    assert skipped_theta == new_theta
    assert skip_n == new_n


def test_pattern_resolution():
    class FakeProfile:
        def __init__(self, id, status, verified, eff_from, eff_to=None, scheme_id=None):
            self.id = id
            self.status = status
            self.verified = verified
            self.effective_from = eff_from
            self.effective_to = eff_to
            self.scheme_id = scheme_id

    d2024 = datetime.date(2024, 6, 1)
    p_generic = FakeProfile(1, "active", True, datetime.date(2023, 1, 1), None, None)
    p_scheme = FakeProfile(2, "active", True, datetime.date(2023, 1, 1), None, "s-2022")
    p_unverified = FakeProfile(3, "active", False, datetime.date(2024, 1, 1), None, "s-2022")

    # Prefers verified, active profile matching scheme
    resolved = resolve_pattern_profile([p_generic, p_scheme, p_unverified], d2024, scheme_id="s-2022")
    assert resolved.id == 2

    # Falls back to generic if no scheme match
    resolved_fallback = resolve_pattern_profile([p_generic, p_unverified], d2024, scheme_id="s-other")
    assert resolved_fallback.id == 1


def test_link_safety():
    assert is_safe_linkout_url("https://icmai.in/students/mcq.pdf") is True
    assert is_safe_linkout_url("https://boslive.icai.org/test") is True
    assert is_safe_linkout_url("http://icmai.in/insecure") is False  # not https
    assert is_safe_linkout_url("https://malicious-site.com/fake") is False
