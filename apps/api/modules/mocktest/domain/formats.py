"""
Pydantic schema validation for ExamFormat sections_spec (ERD Section 2.7).
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ChoiceSpec(BaseModel):
    any: int = Field(ge=1)
    of: int = Field(ge=2)


class SectionSpec(BaseModel):
    key: str
    title: str
    kind: Literal["objective", "descriptive", "mixed"]
    marks: float = Field(gt=0)
    count: int | None = None
    marks_each: float | None = None
    choice: ChoiceSpec | None = None


class SectionsSpec(BaseModel):
    v: int = 1
    sections: list[SectionSpec]


def validate_sections_spec(data: dict[str, Any]) -> dict[str, Any]:
    validated = SectionsSpec.model_validate(data)
    return validated.model_dump()
