"""Small shared vocabulary of the recall module (names of enumerations and their stored numbers)."""

IMPORTANCE_INT = {"bullet": 0, "important": 1, "mandatory": 2}
IMPORTANCE_NAME = {v: k for k, v in IMPORTANCE_INT.items()}
STATE_NAMES = {0: "new", 1: "learning", 2: "review", 3: "relearning"}
