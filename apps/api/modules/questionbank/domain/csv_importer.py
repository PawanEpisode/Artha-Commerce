"""
CSV question batch importer for staff editors (F-06 Slice 16).
"""

from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal
from typing import Any

from modules.questionbank.domain.content import lint_stem
from modules.questionbank.domain.payload import QuestionPayload
from modules.questionbank.registry import get_kind
from modules.questionbank.services import upsert_from_source


def parse_and_import_questions_csv(
    csv_text: str,
    editor_id: uuid.UUID,
    *,
    auto_publish: bool = False,
) -> dict[str, Any]:
    """
    Parses CSV text containing question definitions and creates or updates them.
    Expected columns:
      stem_md (or stem/question), kind (optional, default mcq_single), marks (default 1),
      option_a, option_b, option_c, option_d, correct_option (A/B/C/D),
      explanation_md, difficulty, chapter_key.
    """
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    total = 0
    imported = 0
    errors: list[dict[str, Any]] = []

    for row_no, row in enumerate(reader, start=1):
        total += 1
        stem_md = (row.get("stem_md") or row.get("stem") or row.get("question") or "").strip()
        if not stem_md:
            errors.append({"row": row_no, "error": "Missing question stem."})
            continue

        kind = (row.get("kind") or "mcq_single").strip().lower()
        kind_spec = get_kind(kind)
        if not kind_spec:
            errors.append({"row": row_no, "error": f"Unknown question kind: '{kind}'."})
            continue

        marks_val = float(Decimal(str(row.get("marks") or "1.0")))
        correct_letter = (row.get("correct_option") or row.get("answer") or "A").strip().upper()

        options_data: list[dict[str, Any]] = []
        if kind in ("mcq_single", "mcq_multi"):
            for letter in ["A", "B", "C", "D"]:
                opt_key = f"option_{letter.lower()}"
                opt_text = (row.get(opt_key) or "").strip()
                if opt_text:
                    is_correct = letter in correct_letter
                    options_data.append({"body_md": opt_text, "is_correct": is_correct})

            if not options_data:
                errors.append({"row": row_no, "error": "MCQ requires at least one option column (option_a..option_d)."})
                continue

        payload: QuestionPayload = {
            "kind": kind,
            "stem_md": stem_md,
            "marks": marks_val,
            "options": options_data,
            "explanation_md": (row.get("explanation_md") or "").strip(),
            "labels": {
                "source_kind": "csv_import",
                "difficulty": (row.get("difficulty") or "medium").strip(),
                "chapter_key": (row.get("chapter_key") or "").strip(),
            },
        }

        # Validate payload
        validation_errors = kind_spec.validate_payload(payload)
        stem_lint = lint_stem(stem_md)
        all_errs = validation_errors + stem_lint
        if all_errs:
            errors.append({"row": row_no, "error": "; ".join(all_errs)})
            continue

        external_ref = row.get("external_ref") or f"csv:{editor_id}:{row_no}:{uuid.uuid4().hex[:8]}"

        try:
            upsert_from_source(
                origin_module="csv",
                external_ref=external_ref,
                payload=payload,
                ownership="platform",
                rights_status="original",
                actor_id=editor_id,
                auto_publish=auto_publish,
            )
            imported += 1
        except Exception as e:
            errors.append({"row": row_no, "error": str(e)})

    return {
        "total_rows": total,
        "imported_count": imported,
        "errors": errors,
    }
