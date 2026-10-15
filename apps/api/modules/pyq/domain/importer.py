"""
Validation and parser for artha.paper.v1 schema (F-09 ERD 2.1, 3.2).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from .choice import validate_choice_groups
from .links import validate_paper_link
from .marks import validate_marks_tree

TERM_CODE_REGEX = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")


class SchemaError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


def validate_paper_payload(payload: dict[str, Any]) -> list[str]:
    """
    Validates artha.paper.v1 dictionary.
    Returns list of validation error strings.
    """
    errors: list[str] = []

    # Mandatory top-level attributes
    for field in ["external_ref", "course_code", "level_code", "subject_key", "term_code", "title", "total_marks"]:
        if not payload.get(field):
            errors.append(f"Missing required field '{field}'.")

    term_code = payload.get("term_code", "")
    if term_code and not TERM_CODE_REGEX.match(term_code):
        errors.append(f"Invalid term_code '{term_code}'. Format must be YYYY-MM.")

    total_marks = Decimal(str(payload.get("total_marks", 0)))
    if total_marks <= 0:
        errors.append(f"total_marks must be greater than 0, got {total_marks}.")

    delivery = payload.get("delivery", "link_out")
    if delivery not in ("link_out", "hosted"):
        errors.append(f"delivery must be 'link_out' or 'hosted', got '{delivery}'.")

    if delivery == "hosted" and not payload.get("rights_basis"):
        errors.append("delivery='hosted' requires rights_basis ('original', 'licensed', or 'institute_material').")

    # Links validation
    links = payload.get("links", [])
    for idx, link in enumerate(links, start=1):
        url = link.get("url", "")
        valid, host, msg = validate_paper_link(url)
        if not valid:
            errors.append(f"Link #{idx} ({link.get('link_kind', 'link')}): {msg}")

    # Parts validation
    parts = payload.get("parts", [])
    if not parts:
        errors.append("Paper must contain at least one question part.")

    seen_refs = set()
    top_level_parts = []
    for idx, p in enumerate(parts, start=1):
        ref = p.get("ref") or p.get("number_label")
        if not ref:
            errors.append(f"Part #{idx} missing ref / number_label.")
        elif ref in seen_refs:
            errors.append(f"Duplicate part ref '{ref}'.")
        seen_refs.add(ref)

        depth = int(p.get("depth", 0))
        if depth > 3:
            errors.append(f"Part '{ref}' depth {depth} exceeds maximum depth of 3.")

        if depth == 0 and not p.get("parent_ref"):
            top_level_parts.append(p)
        elif depth > 0 and not p.get("parent_ref"):
            errors.append(f"Part '{ref}' with depth > 0 must specify parent_ref.")

    # Choice groups validation
    choice_groups = payload.get("choice_groups", [])
    if choice_groups:
        cg_errors = validate_choice_groups(choice_groups, top_level_parts)
        errors.extend(cg_errors)

    # Marks tree validation
    marks_note = payload.get("marks_note", "")
    marks_errors = validate_marks_tree(parts, total_marks, marks_note=marks_note, choice_groups=choice_groups)
    errors.extend(marks_errors)

    return errors
