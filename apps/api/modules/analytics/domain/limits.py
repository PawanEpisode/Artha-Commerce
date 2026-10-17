"""
Constants and boundary limits for Performance Analytics (F-10).
Mirrored in apps/web/src/modules/analytics/lib/limits.ts.
"""

from decimal import Decimal

# Answer time window for speed metrics (filter out instant clicks and idle tabs)
MIN_ANSWER_TIME_MS = 2000        # 2 seconds
MAX_ANSWER_TIME_MS = 600000      # 10 minutes (600 seconds)

# Default target accuracy (70%)
DEFAULT_TARGET_ACCURACY = Decimal("0.70")
MIN_TARGET_ACCURACY = Decimal("0.50")
MAX_TARGET_ACCURACY = Decimal("0.95")

# Database batch limits
BATCH_UPSERT_SIZE = 500
MAX_REFRESH_PENDING_SESSIONS = 5

# Readiness formula defaults
DEFAULT_HALF_LIFE_DAYS = 45
DEFAULT_LOOKBACK_FACTOR = 4       # 4 x 45 = 180 days lookback
DEFAULT_MODE_WEIGHT_EXAM = Decimal("1.25")
DEFAULT_REPEAT_WEIGHT = Decimal("0.50")
DEFAULT_PRIOR_MEAN = Decimal("0.50")
DEFAULT_PRIOR_STRENGTH = Decimal("4.0")
DEFAULT_TOPIC_PRIOR_STRENGTH = Decimal("2.0")

# Readiness component weights (must sum to 1.0)
DEFAULT_WEIGHT_ACCURACY = Decimal("0.400")
DEFAULT_WEIGHT_BREADTH = Decimal("0.150")
DEFAULT_WEIGHT_COVERAGE = Decimal("0.200")
DEFAULT_WEIGHT_RETENTION = Decimal("0.150")
DEFAULT_WEIGHT_SPEED = Decimal("0.100")

# Minimum gates before showing readiness
MIN_ANSWERS_SUBJECT = 30
MIN_DAYS_SUBJECT = 3
MIN_WEIGHT_SHARE = Decimal("0.25")
MIN_ANSWERS_CHAPTER = 5
MIN_ANSWERS_TOPIC = 4
RECENT_WINDOW_DAYS = 60
STALE_AFTER_DAYS = 21

# Confidence band cut-offs (half-width)
BAND_HIGH_CUTOFF = Decimal("5.0")      # half-width <= 5.0 -> High
BAND_MEDIUM_CUTOFF = Decimal("10.0")   # half-width <= 10.0 -> Medium
BAND_MAX_HALFWIDTH = Decimal("15.0")   # above 15.0 -> score hidden
BAND_FLOOR = Decimal("3.0")
BAND_MISSING_ADD = Decimal("2.0")

# Readiness label levels
LABEL_GETTING_THERE = 40
LABEL_SOLID = 60
LABEL_STRONG = 75

# Fix set limits
FIX_SET_DEFAULT_SIZE = 10
FIX_SET_MIN_SIZE = 5
FIX_SET_MAX_SIZE = 20
