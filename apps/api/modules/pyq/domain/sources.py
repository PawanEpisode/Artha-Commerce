"""
Finds the past-paper PDFs the platform hosts, from the folder layout of `docs/source-material/question-bank/cma-final/pyqs`:

    P13 - Corporate and Economic Laws (CEL)/June 24/P13 - ... - Question Paper - June 24.pdf
    P13 - Corporate and Economic Laws (CEL)/June 24/P13 - ... - Suggested Answer - June 24.pdf
    P18 - Corporate Financial Reporting ( CFR )/June 23/P18 - CFR - Question & Answers - June 23.pdf   (one combined file)

The paper number comes from the folder, the sitting from the folder under it, and what the file is from its name. Pure: it
only reads directory listings, so it is tested against a temporary tree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PAPER_DIR = re.compile(r"^P(?P<number>\d+[A-Za-z]?)\s*-")
TERM_DIR = re.compile(r"^(?P<month>June|Dec)\s+(?P<year>\d{2})\s*$", re.IGNORECASE)
MONTH_NUMBER = {"june": "06", "dec": "12"}

KIND_PAPER = "paper"
KIND_SUGGESTED = "suggested_answers"

LABEL_PAPER = "Question Paper (PDF)"
LABEL_SUGGESTED = "Suggested Answers (PDF)"
LABEL_COMBINED = "Question Paper and Answers (PDF)"


@dataclass(frozen=True)
class SourceFile:
    path: Path
    paper_number: str  # "13", "20a"
    term_code: str  # "2024-06"
    link_kind: str
    label: str

    @property
    def external_ref(self) -> str:
        """The ref the question-bank seed loader gives the paper (`pyq:cma-final:p13:2024-06`)."""
        return f"pyq:cma-final:p{self.paper_number}:{self.term_code}"


def term_code_of(folder: str) -> str | None:
    match = TERM_DIR.match(folder.strip())
    if not match:
        return None
    return f"20{match['year']}-{MONTH_NUMBER[match['month'].lower()]}"


def classify(filename: str) -> tuple[str, str] | None:
    """(link kind, label) for a file name, or None when it is neither a paper nor answers."""
    name = filename.lower()
    if "question" in name and "answer" in name and "suggested" not in name:
        return KIND_PAPER, LABEL_COMBINED  # "Question & Answers": the paper and its answers in one file
    if "suggested answer" in name:
        return KIND_SUGGESTED, LABEL_SUGGESTED
    if "question paper" in name:
        return KIND_PAPER, LABEL_PAPER
    return None


def discover(root: Path) -> tuple[list[SourceFile], list[str]]:
    """Every PDF under `root` that maps to a paper, and the paths that did not (reported, never guessed at)."""
    found: list[SourceFile] = []
    unmatched: list[str] = []
    for pdf in sorted(root.rglob("*.pdf")):
        relative = pdf.relative_to(root)
        parts = relative.parts
        paper = PAPER_DIR.match(parts[0]) if len(parts) == 3 else None
        term = term_code_of(parts[1]) if len(parts) == 3 else None
        kind = classify(pdf.name)
        if not (paper and term and kind):
            unmatched.append(str(relative))
            continue
        found.append(SourceFile(pdf, paper["number"].lower(), term, kind[0], kind[1]))
    return found, unmatched
