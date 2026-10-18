"""
Pure domain packages for paperanalysis.
"""

from .aggregate import calculate_chapter_aggregates
from .apportion import apportion
from .backtest import run_walk_forward_backtest
from .comparability import ComparabilityStatus, evaluate_comparability
from .effective import (
    calculate_choice_group_attemptable,
    calculate_effective_marks,
    is_practical_format_or_nature,
)
from .explain import DISCLAIMER_KEY, DISCLAIMER_TEXT, TEMPLATES, lint_copy, render_reason
from .params import DEFAULT_PARAMS, ENGINE_VERSION, validate_params
from .planner import (
    PlannerChapterCandidate,
    PlannerPaceContext,
    compute_personal_pace,
    plan_n_days,
)
from .scoring import ChapterInput, PaperSittingInput, SubjectScoringInput, score_subject
from .status import DataStatus, determine_data_status

__all__ = [
    "calculate_chapter_aggregates",
    "apportion",
    "run_walk_forward_backtest",
    "ComparabilityStatus",
    "evaluate_comparability",
    "calculate_choice_group_attemptable",
    "calculate_effective_marks",
    "is_practical_format_or_nature",
    "DISCLAIMER_KEY",
    "DISCLAIMER_TEXT",
    "TEMPLATES",
    "lint_copy",
    "render_reason",
    "DEFAULT_PARAMS",
    "ENGINE_VERSION",
    "validate_params",
    "PlannerChapterCandidate",
    "PlannerPaceContext",
    "compute_personal_pace",
    "plan_n_days",
    "ChapterInput",
    "PaperSittingInput",
    "SubjectScoringInput",
    "score_subject",
    "DataStatus",
    "determine_data_status",
]
