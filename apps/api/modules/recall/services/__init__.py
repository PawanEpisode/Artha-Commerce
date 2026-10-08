"""Write paths of the recall module. Views call these; they never call views. Services are added wave by wave."""

from . import log_guard, quota

__all__ = ["log_guard", "quota"]
