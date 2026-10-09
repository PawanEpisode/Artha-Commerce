"""Write paths of the recall module. Views call these; they never call views. Services are added wave by wave."""

from . import cards, log_guard, quota, student

__all__ = ["cards", "log_guard", "quota", "student"]
