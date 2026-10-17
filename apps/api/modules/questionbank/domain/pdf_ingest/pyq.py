"""
Past-paper builder: a transcription of one exam paper (read from the page images, answers paired from the suggested-answer
PDF) becomes an `artha.paper.v1` document that `pyq.services.import_paper` loads.

Transcription format `artha.pyq-transcription.v1` (one file per paper and term):

  {"schema": "artha.pyq-transcription.v1", "paper": "14", "term_code": "2024-06", "total_marks": 100,
   "duration_minutes": 180, "answers_source": "suggested_answer_pdf" | "none",
   "sections": [{"label": "Section A", "instruction_md": "...", "choice": {"rule": "compulsory"},
                 "questions": [{"number": "1", "marks": 30, "intro_md": "...",
                                "parts": [{"label": "i", "kind": "mcq_single", "marks": 2, "stem_md": "...",
                                           "options": ["...", "...", "...", "..."], "correct": "B",
                                           "answer_md": "", "confidence": "high", "review": []}]}]}]}

A question with one undivided body has one part with the label "". Anything the transcriber could not read or pair with
confidence goes in `review`; that part is loaded as a private draft and never published automatically.
"""

from __future__ import annotations

import calendar
import re
from decimal import Decimal
from typing import Any

from ..difficulty import estimate_difficulty
from . import review as review_mod
from .cases import format_case_groups
from .chapters import ChapterIndex, classify
from .seedbuild import LOW_CONFIDENCE, chapter_defs
from .text import fix_pipeless_tables, lint_safe
from .typeset import apply_text

SCHEMA_IN = "artha.pyq-transcription.v1"
OPTION_LETTERS = "ABCDEF"
# The question kinds need a key (MCQ) or a reference solution (long form) before they can exist at all. Where the Institute
# printed none, the part is stored with this plain statement of fact, flagged, and never published.
NO_ANSWER_NOTE = "Suggested answer not available for this paper."
SECTION_REF = {"a": "secA", "b": "secB", "c": "secC", "d": "secD", "e": "secE"}


class TranscriptionError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


def term_title(paper_number: str, subject_name: str, term_code: str) -> str:
    year, month = term_code.split("-")
    subject_name = re.sub(r"\s*\((?:Elective\s+)?Paper\s+\w+\)\s*$", "", subject_name, flags=re.I).strip()
    return f"CMA Final {calendar.month_name[int(month)]} {year}: {subject_name} (Paper {paper_number})"


def _option_text(option: Any) -> str:
    """Options may be plain strings or `{"key": "A", "body_md": "..."}` objects."""
    return lint_safe(str(option.get("body_md", "") if isinstance(option, dict) else option).strip())


def _marks(value: Any) -> Decimal:
    return Decimal(str(value))


def _ref_suffix(number: str, label: str) -> str:
    """`q2a` for 2(a); `q1aii` for 1(a)(ii). Parentheses and spaces never reach the idempotency key."""
    return f"q{number}{re.sub(r'[^0-9a-z]', '', label.lower())}"


def _number_label(number: str, label: str) -> str:
    """`2(a)`, `1(a)(ii)`; accepts labels printed with or without brackets."""
    label = label.strip()
    return f"{number}{label}" if label.startswith("(") else f"{number}({label})"


def validate_transcription(t: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if t.get("schema") != SCHEMA_IN:
        issues.append(f"schema must be {SCHEMA_IN}")
    for field_name in ("paper", "term_code", "total_marks", "sections"):
        if not t.get(field_name):
            issues.append(f"missing '{field_name}'")
    seen: set[str] = set()
    for section in t.get("sections", []):
        questions = section.get("questions") or []
        if not questions:
            issues.append(f"{section.get('label')}: no questions")
        for q in questions:
            number = str(q.get("number"))
            if number in seen:
                issues.append(f"question {number} appears twice")
            seen.add(number)
            parts = q.get("parts") or []
            if not parts:
                issues.append(f"Q.{number}: no parts")
            for part in parts:
                tag = f"Q.{number} {part.get('label')}" if part.get("label") else f"Q.{number}"
                if not str(part.get("stem_md", "")).strip():
                    issues.append(f"{tag}: empty stem")
                if part.get("kind", "long_form").startswith("mcq"):
                    options = part.get("options") or []
                    if len(options) < 2:
                        issues.append(f"{tag}: fewer than two options")
                    correct = part.get("correct")
                    if correct is not None and (
                        correct not in OPTION_LETTERS or OPTION_LETTERS.index(correct) >= len(options)
                    ):
                        issues.append(f"{tag}: correct '{correct}' is not one of the options")
    return issues


def build_paper(
    t: dict[str, Any],
    *,
    subject: dict[str, Any],
    overlay: dict[str, dict[str, Any]] | None = None,
    decisions: dict[str, dict[str, Any]] | None = None,
    check: bool = True,
    cases: bool = True,
) -> dict[str, Any]:
    """Returns an `artha.paper.v1` dict plus a `_report` with per-part review reasons (ignored by the importer)."""
    issues = validate_transcription(t)
    if issues:
        raise TranscriptionError(issues)

    paper_no = str(t["paper"]).lower().removeprefix("p")
    term_code = t["term_code"]
    index = ChapterIndex(chapter_defs(subject))
    has_answers = t.get("answers_source") == "suggested_answer_pdf"

    parts_out: list[dict[str, Any]] = []
    choice_groups: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []
    notes_out: dict[str, list[str]] = {}
    decided: dict[str, dict[str, Any]] = {}
    sort_order = 0
    answered = 0
    leaves = 0

    for s_idx, section in enumerate(t["sections"]):
        questions = section["questions"]
        choice = section.get("choice") or {"rule": "compulsory"}
        ref = SECTION_REF.get(section["label"].strip()[-1].lower(), f"sec{s_idx + 1}")
        rule = choice.get("rule", "compulsory")
        of_count = len(questions)
        pick = int(choice.get("pick", of_count)) if rule != "compulsory" else of_count
        if rule != "compulsory" and int(choice.get("of", of_count)) != of_count:
            raise TranscriptionError(
                [f"{section['label']}: choice says 'of {choice.get('of')}' but {of_count} questions are listed"]
            )
        choice_groups.append(
            {
                "ref": ref,
                "label": section.get("choice_label")
                or (
                    f"{section['label']}: compulsory"
                    if rule == "compulsory"
                    else f"{section['label']}: answer any {pick} of {of_count}"
                ),
                "rule_kind": rule,
                "pick_count": pick,
                "of_count": of_count,
                "section_label": section["label"],
                "sort_order": s_idx,
            }
        )
        for q in questions:
            number = str(q["number"])
            parts = q["parts"]
            single = len(parts) == 1 and not parts[0].get("label")
            if not single:
                sort_order += 1
                parts_out.append(
                    {
                        "ref": number,
                        "number_label": number,
                        "depth": 0,
                        "sort_order": sort_order,
                        "is_leaf": False,
                        "marks": str(_marks(q["marks"])),
                        "kind": "long_form",
                        "descriptor": (q.get("intro_md") or "")[:200],
                        "choice_group_ref": ref,
                    }
                )
            for part in parts:
                sort_order += 1
                label = part.get("label", "")
                number_label = number if single else _number_label(number, label)
                kind = part.get("kind", "long_form")
                marks = _marks(part.get("marks", q["marks"] if single else 0))
                stem = fix_pipeless_tables(lint_safe(part["stem_md"].strip()))
                answer = fix_pipeless_tables(lint_safe((part.get("answer_md") or "").strip()))
                reasons = list(part.get("review") or [])
                options_in = list(part.get("options") or [])
                typeset_notes: list[str] = []
                entry = (overlay or {}).get(number_label)
                if entry:
                    stem, r, _ = apply_text("stem", stem, entry.get("stem_md"), check=check)
                    reasons += r
                    answer, r, _ = apply_text("answer", answer, entry.get("answer_md"), check=check)
                    reasons += r
                    new_opts = entry.get("options")
                    if new_opts and len(new_opts) == len(options_in):
                        merged = []
                        for o, n in zip(options_in, new_opts, strict=True):
                            body, r, _ = apply_text(
                                f"option {n.get('key', '')}", _option_text(o), n.get("body_md"), check=check
                            )
                            reasons += r
                            merged.append(body)
                        options_in = merged
                    elif new_opts:
                        reasons.append("typeset options ignored: option count differs from the transcription")
                    typeset_notes = [str(n) for n in entry.get("review") or []]
                    if typeset_notes:
                        notes_out[number_label] = typeset_notes
                    if entry.get("confidence") in ("low", "medium"):
                        reasons.append(
                            f"typeset confidence {entry['confidence']}"
                            + (": " + "; ".join(typeset_notes[:3]) if typeset_notes else "")
                        )
                if not has_answers:  # a question-only paper is expected to have no answers; that is not a doubt
                    reasons = [r for r in reasons if not re.search(r"no (suggested )?answer", r, re.I)]
                decision = (decisions or {}).get(number_label)
                problems: list[str] = []
                if decision:
                    for field in ("stem_md", "answer_md"):
                        text = decision.get(field)
                        if text is None:
                            continue
                        cleaned, errors = review_mod._checked(text, check=check)
                        if errors:
                            problems.append(f"reviewed {field} rejected, kept the previous text: {errors[0]}")
                        elif field == "stem_md":
                            stem = cleaned
                        else:
                            answer = cleaned
                    letter = str(decision.get("correct") or "").upper()
                    if letter and part.get("correct") is None and letter in OPTION_LETTERS[: len(options_in)]:
                        part = {**part, "correct": letter}
                    new_opts = decision.get("options")
                    if new_opts and len(new_opts) == len(options_in):
                        fixed = []
                        for o, n in zip(options_in, new_opts, strict=True):
                            cleaned, errors = review_mod._checked(str(n.get("body_md", "")), check=check)
                            if errors or not cleaned.strip():
                                problems.append(f"reviewed option {n.get('key', '')} rejected, kept the previous text")
                                fixed.append(o)
                            else:
                                fixed.append(cleaned)
                        options_in = fixed
                    decided[number_label] = {
                        "verdict": decision.get("verdict"),
                        "reason": decision.get("reason", ""),
                        "fixes": decision.get("fixes", []),
                        "printed_issues": decision.get("printed_issues", []),
                        "by": review_mod.REVIEWER,
                    }
                is_mcq = kind.startswith("mcq")
                leaf: dict[str, Any] = {
                    "ref": number_label,
                    "number_label": number_label,
                    "ref_suffix": _ref_suffix(number, label),
                    "depth": 0 if single else 1,
                    "sort_order": sort_order,
                    "is_leaf": True,
                    "marks": str(marks),
                    "kind": kind,
                    "stem_md": stem,
                }
                if single:
                    leaf["choice_group_ref"] = ref
                else:
                    leaf["parent_ref"] = number
                leaves += 1
                pending_answer = False  # nothing to publish yet: no key or no reference solution
                if is_mcq and part.get("correct") is None:
                    # No single key (not published, or the Institute accepts several options): keep the printed options in
                    # the stem and store a long-form draft so nothing is lost and nothing is guessed.
                    lines = [f"({OPTION_LETTERS[i]}) {_option_text(o)}" for i, o in enumerate(options_in)]
                    stem = stem + "\n\n" + "\n".join(lines)
                    leaf["stem_md"] = stem
                    leaf["kind"] = kind = "long_form"
                    is_mcq = False
                    pending_answer = True
                    if has_answers:  # in a question-only paper this is expected, not a doubt
                        reasons.append(
                            "MCQ has no single answer key; stored as a long-form draft with its options in the stem"
                        )
                if is_mcq:
                    options = options_in
                    correct = part.get("correct")
                    leaf["options"] = [
                        {"body_md": _option_text(o), "is_correct": correct is not None and OPTION_LETTERS[i] == correct}
                        for i, o in enumerate(options)
                    ]
                    if correct is None and has_answers:
                        reasons.append("no answer key was found for this MCQ in the suggested answers")
                    if correct is not None:
                        answered += 1
                    leaf["explanation_md"] = answer
                else:
                    if answer:
                        leaf["explanation_md"] = answer
                        leaf["reference_solution_md"] = answer
                        answered += 1
                    else:
                        pending_answer = True
                        leaf["explanation_md"] = leaf["reference_solution_md"] = NO_ANSWER_NOTE
                        if has_answers:
                            reasons.append("no suggested answer was found for this part")
                if answer or (is_mcq and part.get("correct")):
                    leaf["answer_source"] = "icmai_suggested"
                leaf["difficulty"] = estimate_difficulty(
                    kind=kind,
                    stem=stem,
                    options=[o["body_md"] for o in leaf.get("options", [])],
                    marks=marks,
                    solution=answer,
                )
                cls = classify(index, f"{stem}\n{answer[:800]}")
                leaf["chapter_key"] = cls.chapter_key
                leaf["mapping_confidence"] = cls.confidence
                leaf["mapping_state"] = "confirmed" if cls.confidence >= LOW_CONFIDENCE else "pending"
                if part.get("confidence", "high") == "low":
                    reasons.append("transcriber marked this part low confidence")
                if decision:
                    verdict = decision.get("verdict")
                    resolved = not pending_answer and stem.strip() and not problems
                    if verdict == "approve" and resolved:
                        reasons = []
                    else:
                        reasons += problems
                        if verdict == "hold":
                            reasons.append(f"review hold: {decision.get('reason', '')}")
                        elif verdict == "approve":
                            reasons.append(
                                "review approved the part but an answer or key is still missing, or its corrected text failed a gate"
                            )
                leaf["publish"] = not reasons and not pending_answer
                if reasons:
                    report.append({"part": number_label, "reasons": reasons})
                parts_out.append(leaf)

    case_labels = format_case_groups([x for x in parts_out if x.get("is_leaf")]) if cases else []
    subject_name = subject["name"]
    payload = {
        "schema": "artha.paper.v1",
        "external_ref": f"pyq:cma-final:p{paper_no}:{term_code}",
        "course_code": "cma",
        "level_code": "final",
        "subject_key": subject["key"],
        "term_code": term_code,
        "title": term_title(paper_no.upper(), subject_name, term_code),
        "paper_code": f"P{paper_no.upper()}",
        "total_marks": str(_marks(t["total_marks"])),
        "duration_minutes": int(t.get("duration_minutes", 180)),
        "delivery": "hosted",
        "rights_basis": "institute_material",
        "source_name": "ICMAI",
        "answers_status": "none"
        if not has_answers or answered == 0
        else ("complete" if answered == leaves else "partial"),
        "marks_note": t.get("marks_note", ""),
        "links": [],
        "choice_groups": choice_groups,
        "parts": parts_out,
    }
    return {
        "payload": payload,
        "report": report,
        "typeset_notes": notes_out,
        "decisions": decided,
        "case_groups": case_labels,
        "counts": {"leaves": leaves, "draft_parts": len(report), "answered": answered},
    }
