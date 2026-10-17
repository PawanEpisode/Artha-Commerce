"""
Turns parsed MCQ and workbook items into the reviewable seed documents (`artha.qbseed.v1`) that are committed to the repo.

Pure: takes already-parsed items and the syllabus chapters of the paper, returns plain dicts. The loader
(`load_question_bank_seed`) is the only code that writes these to the database.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from ..difficulty import estimate_difficulty
from . import review as review_mod
from . import typeset as typeset_mod
from .chapters import ChapterDef, ChapterIndex, classify, classify_sequence
from .mcq import ParsedMcq
from .workbook import WorkbookItem

SCHEMA = "artha.qbseed.v1"
COURSE, LEVEL, SCHEME = "cma", "final", "2022"
MCQ_MARKS = Decimal("2")  # CMA Final: Section A is 15 MCQs x 2 marks = 30
LOW_CONFIDENCE = 0.5

_SINGLE_ASK = re.compile(r"\b(calculate|compute|determine|ascertain|find|what is|what will be)\b", re.I)
_EXTRA_ASK = re.compile(
    r"\b(and|also|then)\s+(calculate|compute|determine|ascertain|find|comment|advise|discuss|explain|state)\b|\bcomment\b|\badvise\b",
    re.I,
)
_PART_MARK = re.compile(r"(?m)^\s*(?:\(?[a-h]\)|\(?(?:i{1,3}|iv|v|vi{0,3}|ix|x)\)|\(?[1-9]\)|[a-h]\.)\s+\S")
_LAST_NUMBER = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(%|times|days|units|years|months|lakhs?|crores?)?\s*\.?\s*$", re.I)


def chapter_defs(subject: dict[str, Any]) -> list[ChapterDef]:
    """ChapterDefs from one subject entry of `syllabus/seed/cma/final/2022.json`."""
    return [
        ChapterDef(ch["key"], ch["name"], tuple(t["name"] for t in ch.get("topics", []))) for ch in subject["chapters"]
    ]


def single_numeric_answer(stem: str, solution: str) -> dict[str, Any] | None:
    """
    A numeric key only when the question asks for exactly one thing and the worked solution ends on one figure.
    Deliberately strict: a wrong key would mark a correct student wrong, and the caller sends the item to review anyway.
    """
    if _PART_MARK.search(stem) or _EXTRA_ASK.search(stem):
        return None
    asks = _SINGLE_ASK.findall(stem)
    if len(asks) != 1:
        return None
    lines = [ln.strip() for ln in solution.splitlines() if ln.strip() and not ln.strip().startswith(("|", "```"))]
    if not lines or len(solution) > 900:
        return None
    last = lines[-1]
    if "=" not in last and not last.lower().startswith(("answer", "ans")):
        return None
    match = _LAST_NUMBER.search(last)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    try:
        value = Decimal(raw)
    except Exception:
        return None
    return {
        "numeric_value": str(value),
        "tolerance_rel": "0.01",
        "unit": (match.group(2) or "").lower(),
        "key_note": f"Taken from the last line of the Institute's worked solution: {last[:160]}",
    }


def _base_labels(source: dict[str, Any], ref: str, difficulty: int, tags: list[str], nature: str) -> dict[str, Any]:
    return {
        "source_kind": source["source_kind"],
        "source_name": source["source_name"],
        "source_ref": ref,
        "source_year": source.get("source_year"),
        "source_term_code": source.get("source_term_code", ""),
        "difficulty": difficulty,
        "tags": tags,
        "nature": nature,
    }


def apply_mcq_overlay(
    stem: str, options: list[str], reasons: list[str], entry: dict[str, Any] | None
) -> tuple[str, list[str], list[str], list[str], bool]:
    """(stem, options, review_reasons, notes, typeset?) after a typeset entry; the answer key is never involved."""
    notes: list[str] = []
    done = False
    if not entry:
        return stem, options, reasons, notes, done
    stem, r, done = typeset_mod.apply_text("stem", stem, entry.get("stem_md"))
    reasons = reasons + r
    new_opts = entry.get("options")
    if new_opts and len(new_opts) == len(options):
        merged = []
        for old, n in zip(options, new_opts, strict=True):
            body, r, ok = typeset_mod.apply_text(f"option {n.get('key', '')}", old, n.get("body_md"))
            reasons += r
            done = done or ok
            merged.append(body)
        options = merged
    elif new_opts:
        reasons = reasons + ["typeset options ignored: option count differs from the parsed options"]
    notes = [str(n) for n in entry.get("review") or []]
    if entry.get("confidence") in ("low", "medium"):
        reasons = reasons + [
            f"typeset confidence {entry['confidence']}" + (": " + "; ".join(notes[:3]) if notes else "")
        ]
    return stem, options, reasons, notes, done


def build_mcq_seed(
    items: list[ParsedMcq],
    *,
    paper: str,
    subject: dict[str, Any],
    source: dict[str, Any],
    problems: list[str],
    overlay: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """`overlay` maps external_ref to a typeset entry (stem and/or options); the key (`is_correct`) is never touched."""
    chapters = chapter_defs(subject)
    index = ChapterIndex(chapters)
    texts = [f"{i.stem} {' '.join(i.options)}" for i in items]
    classes = classify_sequence(index, texts)
    out: list[dict[str, Any]] = []
    for item, cls in zip(items, classes, strict=True):
        ref = f"mcq:cma-final:p{paper.lower()}:q{item.number:03d}"
        difficulty = estimate_difficulty(kind=item.kind, stem=item.stem, options=item.options, marks=MCQ_MARKS)
        stem, options, reasons, notes, typeset_done = apply_mcq_overlay(
            item.stem, list(item.options), list(item.review_reasons), (overlay or {}).get(ref)
        )
        out.append(
            {
                "external_ref": ref,
                "origin_module": "mcq",
                "status": "needs_review" if reasons else item.status,
                "review_reasons": reasons,
                "payload": {
                    "kind": item.kind,
                    "stem_md": stem,
                    "options": [{"body_md": o, "is_correct": i == item.correct_index} for i, o in enumerate(options)],
                    "marks": str(MCQ_MARKS),
                    "explanation_md": "",
                    "labels": _base_labels(
                        source, ref, difficulty, ["institute_mcq", f"paper:{paper.lower()}"], "theory"
                    ),
                    "mapping": [
                        {
                            "course": COURSE,
                            "level": LEVEL,
                            "subject_key": subject["key"],
                            "chapter_key": cls.chapter_key,
                            "primary": True,
                        }
                    ],
                },
                "mapping_meta": {"confidence": cls.confidence, "runner_up": cls.runner_up},
                "marks_source": "pattern",
                "evidence": {
                    "number": item.number,
                    "answer_text": item.answer_text,
                    "key_match": item.key_evidence,
                    **({"typeset": True, "typeset_notes": notes} if typeset_done else {}),
                },
            }
        )
    return _document("mcq", paper, subject, source, out, problems)


def build_workbook_seed(
    items: list[WorkbookItem],
    *,
    paper: str,
    subject: dict[str, Any],
    source: dict[str, Any],
    problems: list[str],
    overlay: dict[str, dict[str, Any]] | None = None,
    decisions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    `overlay` maps external_ref to a typeset entry (see typeset.py); None builds from the extracted text alone.
    `decisions` maps external_ref to a review decision (see review.py).
    """
    chapters = chapter_defs(subject)
    index = ChapterIndex(chapters)
    out: list[dict[str, Any]] = []
    for item in items:
        ref = f"workbook:cma-final:p{paper.lower()}:ch{item.chapter_index}:q{item.ordinal}"
        title_hint = "" if re.fullmatch(r"Module \d+", item.chapter_title) else item.chapter_title
        cls = classify(index, f"{item.stem_md}\n{item.solution_md[:1500]}", title_hint=title_hint)
        difficulty = estimate_difficulty(
            kind="long_form", stem=item.stem_md, marks=item.marks, solution=item.solution_md
        )
        reasons = list(item.review_reasons)
        stem_md, solution_md = item.stem_md, item.solution_md
        typeset_done = False
        typeset_notes: list[str] = []
        if overlay is not None:
            stem_md, solution_md, typeset_reasons, typeset_done, typeset_notes = typeset_mod.apply_overlay(
                item.stem_md, item.solution_md, overlay.get(ref)
            )
            reasons += typeset_reasons
        decision = (decisions or {}).get(ref)
        stem_md, solution_md, reasons, review_evidence = review_mod.apply_decision(
            stem_md, solution_md, reasons, decision
        )
        payload: dict[str, Any] = {
            "kind": "long_form",
            "stem_md": stem_md,
            "marks": str(item.marks),
            "explanation_md": solution_md,
            "rubric": {
                "reference_solution_md": solution_md,
                "steps": [
                    {
                        "title": "Complete solution and working notes",
                        "description_md": "Self-assess against the Institute's worked solution.",
                        "marks": str(item.marks),
                        "kind": "concept",
                        "mandatory": True,
                        "partial_allowed": True,
                    }
                ],
            },
            "labels": _base_labels(source, ref, difficulty, ["workbook", f"paper:{paper.lower()}"], "practical"),
            "mapping": [
                {
                    "course": COURSE,
                    "level": LEVEL,
                    "subject_key": subject["key"],
                    "chapter_key": cls.chapter_key,
                    "primary": True,
                }
            ],
        }
        if decision:
            key = review_mod.numeric_key_from(decision)  # the reviewer settled it; nothing is guessed again
        else:
            key = single_numeric_answer(item.stem_md, item.solution_md) if not reasons else None
        if key:
            payload["kind"] = "numeric"
            payload["numeric_key"] = key
            payload.pop("rubric")
            if not decision:
                reasons.append("numeric key was detected automatically from the last line of the solution; confirm it")
        out.append(
            {
                "external_ref": ref,
                "origin_module": "workbook",
                "status": "needs_review" if reasons else "ok",
                "review_reasons": reasons,
                "payload": payload,
                "mapping_meta": {"confidence": cls.confidence, "runner_up": cls.runner_up},
                "marks_source": item.marks_source,
                "evidence": {
                    "chapter_title": item.chapter_title,
                    "page": item.page,
                    "printed_number": item.number,
                    "typeset": typeset_done,
                    "typeset_notes": typeset_notes,
                    **({"review": review_evidence} if review_evidence else {}),
                },
            }
        )
    return _document("workbook", paper, subject, source, out, problems)


def _document(
    kind: str,
    paper: str,
    subject: dict[str, Any],
    source: dict[str, Any],
    items: list[dict[str, Any]],
    problems: list[str],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "kind": kind,
        "course": COURSE,
        "level": LEVEL,
        "scheme": SCHEME,
        "paper": paper,
        "paper_number": subject["paper_number"],
        "subject_key": subject["key"],
        "source": source,
        "parser_problems": problems,
        "counts": {
            "items": len(items),
            "ok": sum(1 for i in items if i["status"] == "ok"),
            "needs_review": sum(1 for i in items if i["status"] != "ok"),
        },
        "items": items,
    }


def needs_review_markdown(seed: dict[str, Any]) -> str:
    """One page per paper and kind: what loads as a draft and why, plus chapter guesses an editor should confirm."""
    lines = [
        f"# Needs review: {seed['source']['source_name']} ({seed['kind']})",
        "",
        f"{seed['counts']['needs_review']} of {seed['counts']['items']} items load as DRAFT and are never published automatically.",
        "",
    ]
    if seed["parser_problems"]:
        lines += ["## Problems with the PDF as a whole", ""] + [f"- {p}" for p in seed["parser_problems"]] + [""]
    drafts = [i for i in seed["items"] if i["status"] != "ok"]
    if drafts:
        lines += ["## Loaded as draft", "", "| Item | Why |", "|---|---|"]
        for item in drafts:
            why = "; ".join(item["review_reasons"]).replace("|", "\\|")
            lines.append(f"| `{item['external_ref']}` | {why} |")
        lines.append("")
    low = [i for i in seed["items"] if i["mapping_meta"]["confidence"] < LOW_CONFIDENCE]
    lines += [
        "## Chapter mapping to confirm",
        "",
        f"{len(low)} items have a low-confidence chapter guess. They are still loaded (as *suggested* mappings, origin `ingestion`).",
        "",
    ]
    if low:
        lines += ["| Item | Chapter guessed | Confidence |", "|---|---|---|"]
        for item in low:
            mapping = item["payload"]["mapping"][0]
            lines.append(
                f"| `{item['external_ref']}` | {mapping['chapter_key']} | {item['mapping_meta']['confidence']} |"
            )
    return "\n".join(lines) + "\n"
