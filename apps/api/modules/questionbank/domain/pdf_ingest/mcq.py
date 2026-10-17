"""
MCQ bank parser.

Input is the rows of every table in a bank PDF. Question rows are `[no, stem, opt1..opt4]`; the answer table at the end of
the PDF has `[no, stem, correct answer text]`. Questions and answers are re-joined by number, and the answer text is matched
to an option. Only an exact match (ignoring case, spacing and punctuation) is trusted; anything else becomes `needs_review`
and loads as a draft with the evidence in `review_reasons`.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from .text import collapse_ws, fix_workbook_rupee, normalise_key_text

OPTION_LABELS = "ABCD"
_MULTI = re.compile(r"\b(select all|choose all|more than one (correct|answer)|one or more of the following)\b", re.I)
_LETTER_REF = re.compile(r"^\(?([a-d1-4])\)?[.)]?$", re.I)


@dataclass
class ParsedMcq:
    number: int
    stem: str
    options: list[str]
    answer_text: str | None
    correct_index: int | None
    kind: str = "mcq_single"
    status: str = "ok"  # ok | needs_review
    review_reasons: list[str] = field(default_factory=list)
    key_evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "kind": self.kind,
            "stem_md": self.stem,
            "options": [{"body_md": o, "is_correct": i == self.correct_index} for i, o in enumerate(self.options)],
            "answer_text": self.answer_text,
            "key_evidence": self.key_evidence,
            "status": self.status,
            "review_reasons": self.review_reasons,
        }


def split_rows(table_rows: list[list[str | None]]) -> tuple[dict[int, list[str]], dict[int, list[str]], list[str]]:
    """Separate question rows from answer rows. Returns (questions, answers, problems)."""
    questions: dict[int, list[str]] = {}
    answers: dict[int, list[str]] = {}
    problems: list[str] = []
    for row in table_rows:
        if not row:
            continue
        first = collapse_ws(row[0] or "")
        if not first.isdigit():
            continue  # header row or a stray cell
        number = int(first)
        cells = [collapse_ws(c or "") for c in row]
        if len(cells) >= 6:
            if number in questions:
                problems.append(f"question {number} appears twice")
            questions[number] = cells
        elif len(cells) == 3:
            if number in answers:
                problems.append(f"answer {number} appears twice")
            answers[number] = cells
        else:
            problems.append(f"row {number} has {len(cells)} cells")
    return questions, answers, problems


def match_answer(answer_text: str, options: list[str]) -> tuple[int | None, str, str]:
    """
    Returns (index, confidence, evidence). confidence is "exact", "fuzzy" or "none".
    Only "exact" is trusted without review.
    """
    target = normalise_key_text(answer_text)
    if not target:
        return None, "none", "answer cell is empty"
    normalised = [normalise_key_text(o) for o in options]
    hits = [i for i, n in enumerate(normalised) if n and n == target]
    if len(hits) == 1:
        return hits[0], "exact", f"answer text equals option {OPTION_LABELS[hits[0]]}"
    if len(hits) > 1:
        return None, "none", f"answer text equals {len(hits)} identical options"

    letter = _LETTER_REF.match(collapse_ws(answer_text))
    if letter:
        ref = letter.group(1).lower()
        idx = "abcd".index(ref) if ref in "abcd" else int(ref) - 1
        if idx < len(options) and options[idx]:
            return idx, "fuzzy", f"answer cell is the label '{answer_text}', taken as option {OPTION_LABELS[idx]}"

    contains = [
        i for i, n in enumerate(normalised) if n and (target in n or n in target) and min(len(n), len(target)) >= 4
    ]
    if len(contains) == 1:
        return contains[0], "fuzzy", f"answer text is part of option {OPTION_LABELS[contains[0]]} (or the reverse)"

    scored = sorted(
        ((difflib.SequenceMatcher(None, target, n).ratio(), i) for i, n in enumerate(normalised) if n), reverse=True
    )
    if scored and scored[0][0] >= 0.85 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.1):
        return (
            scored[0][1],
            "fuzzy",
            f"answer text is {scored[0][0]:.0%} similar to option {OPTION_LABELS[scored[0][1]]}",
        )
    return None, "none", "answer text matches no option"


def parse_mcq_tables(table_rows: list[list[str | None]]) -> tuple[list[ParsedMcq], list[str]]:
    """Parse every table row of one MCQ bank PDF. Returns (items in number order, bank-level problems)."""
    questions, answers, problems = split_rows(table_rows)
    items: list[ParsedMcq] = []
    for number in sorted(questions):
        cells = questions[number]
        stem = fix_workbook_rupee(cells[1])
        options = [fix_workbook_rupee(c) for c in cells[2:6]]
        reasons: list[str] = []
        if not stem:
            reasons.append("stem is empty")
        blank = [OPTION_LABELS[i] for i, o in enumerate(options) if not o]
        if blank:
            reasons.append(f"option {', '.join(blank)} is empty")
        answer_row = answers.get(number)
        answer_text = fix_workbook_rupee(answer_row[2]) if answer_row else None
        index: int | None = None
        evidence = ""
        if answer_row is None:
            reasons.append("no row for this number in the answer table")
        else:
            index, confidence, evidence = match_answer(answer_text or "", options)
            if confidence != "exact":
                reasons.append(f"answer key not confirmed: {evidence}; answer table says '{answer_text}'")
            if confidence == "none":
                index = None
        kind = "mcq_multi" if _MULTI.search(stem) else "mcq_single"
        if kind == "mcq_multi":
            reasons.append("stem asks for more than one answer but the bank gives one answer text")
        items.append(
            ParsedMcq(
                number=number,
                stem=stem,
                options=options,
                answer_text=answer_text,
                correct_index=index,
                kind=kind,
                status="needs_review" if reasons else "ok",
                review_reasons=reasons,
                key_evidence=evidence,
            )
        )
    if questions:
        missing = [n for n in range(1, max(questions) + 1) if n not in questions]
        if missing:
            problems.append(f"question numbers missing from the PDF: {missing[:20]}")
    extra = sorted(set(answers) - set(questions))
    if extra:
        problems.append(f"answers without a question: {extra[:20]}")
    return items, problems
