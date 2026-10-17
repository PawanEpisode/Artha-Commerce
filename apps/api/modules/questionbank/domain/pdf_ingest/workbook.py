"""
Workbook parser: "ILLUSTRATION n ... Solution: ..." blocks grouped by chapter.

Input is a list of pages; each page is a list of blocks in reading order:
  {"type": "text", "text": "..."}            free text (already outside any table)
  {"type": "table", "rows": [[...], ...]}    a table, first row is the header
  {"type": "image", "w": 300, "h": 200}      a large picture (a diagram or graph that text extraction cannot see)

The workbooks print no marks, so every illustration gets `DEFAULT_MARKS` and `marks_source = "inferred"`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .text import collapse_ws, fix_workbook_rupee, layout_to_markdown, markdown_table, normalise_key_text

DEFAULT_MARKS = Decimal("7")

_FOOTER = re.compile(r"Directorate of Studies,\s*The Institute of Cost Accountants of India", re.I)
_RUNNING_HEAD = re.compile(r"^\s*Work\s*Book\s*:", re.I)
_TAG = re.compile(r"^\s*\[\s*Study Material\s*[-–]\s*(?P<what>[^\]]+)\]\s*$", re.I)
_ILLUSTRATION = re.compile(r"^\s*ILLUSTRATION\s*[-–:.]?\s*(?P<n>\d+)\s*[:.)]?\s*(?P<rest>.*)$", re.I)
_SOLUTION = re.compile(
    r"^\s*(?:Suggested\s+)?(?:Solution|Answer|Ans)s?\s*(?::|\.|-|–)\s*(?P<rest>.*)$|^\s*(?:Solution|Answer)s?\s*$", re.I
)
_TOC_LINE = re.compile(r"^\s*\d{1,2}\.\s+(?P<title>\S.*?)\s+\d+\s*[-–]\s*\d+\s*$")
_ONLY_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")
MIN_IMAGE_SIDE = 90  # points; smaller pictures are logos and rules


@dataclass
class WorkbookItem:
    chapter_index: int
    chapter_title: str
    number: int
    ordinal: int  # 1-based position inside the chapter
    stem_md: str
    solution_md: str
    page: int
    status: str = "ok"
    review_reasons: list[str] = field(default_factory=list)
    marks: Decimal = DEFAULT_MARKS
    marks_source: str = "inferred"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_index": self.chapter_index,
            "chapter_title": self.chapter_title,
            "number": self.number,
            "ordinal": self.ordinal,
            "stem_md": self.stem_md,
            "solution_md": self.solution_md,
            "page": self.page,
            "marks": str(self.marks),
            "marks_source": self.marks_source,
            "status": self.status,
            "review_reasons": self.review_reasons,
        }


def toc_titles(pages: list[dict[str, Any]]) -> list[str]:
    """Chapter titles from the printed index ('1.   Decision Making Techniques     1-23')."""
    titles: list[str] = []
    for page in pages[:14]:
        for block in page["blocks"]:
            if block["type"] != "text":
                continue
            for line in block["text"].splitlines():
                m = _TOC_LINE.match(line)
                if m:
                    titles.append(collapse_ws(m.group("title")))
    return titles


def _lines(pages: list[dict[str, Any]]) -> list[tuple[int, str, str]]:
    """Flatten pages to (page, kind, text) lines with running heads and footers removed. kind: text | table | image."""
    out: list[tuple[int, str, str]] = []
    for page in pages:
        number = page["page"]
        for block in page["blocks"]:
            if block["type"] == "image":
                if min(block.get("w", 0), block.get("h", 0)) >= MIN_IMAGE_SIDE:
                    out.append((number, "image", ""))
            elif block["type"] == "table":
                md = markdown_table(block["rows"])
                if md:
                    out.append((number, "table", md))
            else:
                for line in block["text"].splitlines():
                    if _FOOTER.search(line) or _RUNNING_HEAD.match(line):
                        continue
                    out.append((number, "text", line.rstrip()))
    return out


def _strip_title_tail(buffer: list[str], next_title: str | None) -> list[str]:
    """Drop the next chapter's number and title lines that were read as the end of the last solution."""
    target = normalise_key_text(next_title or "")
    while buffer:
        last = buffer[-1].strip()
        if not last:
            buffer.pop()
        elif _ONLY_NUMBER.match(last):
            buffer.pop()
        elif target and normalise_key_text(last) and normalise_key_text(last) in target:
            buffer.pop()
        else:
            break
    return buffer


def _join(lines: list[str]) -> str:
    text = layout_to_markdown("\n".join(lines))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return fix_workbook_rupee(text)


def parse_workbook(pages: list[dict[str, Any]]) -> tuple[list[WorkbookItem], list[str]]:
    """Returns (items in reading order, bank-level problems)."""
    titles = toc_titles(pages)
    flat = _lines(pages)
    problems: list[str] = []

    chapter_index = 0
    chapter_title = ""
    ordinal = 0
    current: dict[str, Any] | None = None
    items: list[WorkbookItem] = []

    def close(next_title: str | None) -> None:
        nonlocal current
        if current is None:
            return
        stem_lines = _strip_title_tail(current["stem"], next_title) if not current["in_solution"] else current["stem"]
        sol_lines = _strip_title_tail(current["solution"], next_title) if current["in_solution"] else []
        reasons = list(current["reasons"])
        stem = _join(stem_lines)
        solution = _join(sol_lines)
        if not current["in_solution"]:
            reasons.append("no 'Solution:' or 'Answer:' marker found")
        elif len(solution) < 15:
            reasons.append("solution is almost empty")
        if len(stem) < 25:
            reasons.append("stem is almost empty")
        items.append(
            WorkbookItem(
                chapter_index=current["chapter_index"],
                chapter_title=current["chapter_title"],
                number=current["number"],
                ordinal=current["ordinal"],
                stem_md=stem,
                solution_md=solution,
                page=current["page"],
                status="needs_review" if reasons else "ok",
                review_reasons=reasons,
            )
        )
        current = None

    recent: list[str] = []  # the last few non-blank text lines: the chapter title sits just above its tag
    for page, kind, text in flat:
        if kind == "text" and text.strip():
            recent = (recent + [text])[-6:]
        tag = _TAG.match(text) if kind == "text" else None
        if tag:
            title_lines: list[str] = []
            for line in reversed(recent[:-1]):
                if _ONLY_NUMBER.match(line):
                    break
                title_lines.append(line.strip())
            printed_title = collapse_ws(" ".join(reversed(title_lines))) if 0 < len(title_lines) <= 4 else ""
            fallback = titles[chapter_index] if chapter_index < len(titles) else None
            close(printed_title or fallback)
            chapter_index += 1
            chapter_title = printed_title or fallback or f"Module {chapter_index}"
            ordinal = 0
            recent = []
            continue
        ill = _ILLUSTRATION.match(text) if kind == "text" else None
        if ill and chapter_index > 0:
            close(None)
            ordinal += 1
            current = {
                "chapter_index": chapter_index,
                "chapter_title": chapter_title,
                "number": int(ill.group("n")),
                "ordinal": ordinal,
                "page": page,
                "stem": [ill.group("rest")] if ill.group("rest").strip() else [],
                "solution": [],
                "in_solution": False,
                "reasons": [],
            }
            continue
        if current is None:
            continue
        if kind == "image":
            current["reasons"].append(f"a picture or diagram on page {page} cannot be read from the text layer")
            continue
        if kind == "text" and not current["in_solution"]:
            sol = _SOLUTION.match(text)
            if sol and current["stem"]:
                current["in_solution"] = True
                rest = (sol.group("rest") or "").strip() if sol.groupdict().get("rest") is not None else ""
                if rest:
                    current["solution"].append(rest)
                continue
        (current["solution"] if current["in_solution"] else current["stem"]).append(text)
    close(None)

    if chapter_index == 0:
        problems.append("no '[Study Material - Module n]' tag found")
    return items, problems
