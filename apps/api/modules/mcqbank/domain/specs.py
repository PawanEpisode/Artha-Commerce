"""
Strict Pydantic models for MCQ picker and preset specs (F-05 ERD 3.2).
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class McqSetPickerSpec(BaseModel):
    v: int = 1
    set_id: uuid.UUID
    count: int | None = None
    order: Literal["set", "random"] = "set"

    model_config = {"extra": "forbid"}


class ChapterQuota(BaseModel):
    chapter_id: uuid.UUID | None = None
    chapter_key: str | None = None
    n: int = Field(gt=0)


class McqBlueprintPickerSpec(BaseModel):
    v: int = 1
    chapters: list[ChapterQuota] | None = None
    subject_key: str | None = None
    count: int = Field(default=20, gt=0, le=100)
    mix: Literal["smart", "random"] = "smart"
    difficulty_mix: list[int] | None = None
    filter: dict[str, Any] | None = None
    hide_amended: bool = True

    model_config = {"extra": "forbid"}


class McqAdaptivePickerSpec(BaseModel):
    v: int = 1
    run_id: uuid.UUID
    round_no: int = Field(gt=0)

    model_config = {"extra": "forbid"}
