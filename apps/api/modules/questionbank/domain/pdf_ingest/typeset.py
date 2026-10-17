"""
Typeset workbook working: the Institute's PDF prints solutions as stacked fractions, superscripts and aligned rows, which
plain text extraction flattens ("(1.10)2", "Standard deviation = 10.95 = 0.146 / Mean 75"). A typeset overlay holds the same
content re-written as Markdown + KaTeX by reading the page image (`artha.qbtypeset.v1`).

Pure except `katex_errors`, which shells out to node. Gates decide whether an overlay entry may replace the extracted text:

* hard (entry is rejected, the extracted text is kept and the item goes to review): empty text, lint errors for the QUESTION
  profile, a formula KaTeX cannot parse, a forbidden/unknown wrapper.
* soft (entry is used, the item goes to review with the reason): significant figures of the PDF text are missing from the
  typeset text, the typeset text carries figures the PDF text does not, or the prose changed a lot.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core import richtext

from .text import lint_safe

SCHEMA = "artha.qbtypeset.v1"
WEB_PACKAGE = Path(__file__).resolve().parents[5] / "web" / "package.json"
CHECKER = Path(__file__).with_name("check_katex.mjs")

_FENCE = re.compile(r"(?ms)^ {0,3}(`{3,}|~{3,}).*?^ {0,3}\1[ \t]*$")
_DISPLAY = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_INLINE = re.compile(r"(?<![\\$])\$(?!\$)(?=\S)((?:[^$\n\\]|\\.)*?)(?<=\S)(?<!\\)\$(?!\$)")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_TEX_CMD = re.compile(r"\\[A-Za-z]+")
_WORD = re.compile(r"[A-Za-z]{4,}")
_SPACING = re.compile(r"\\[,;:! ]|\\quad|\\qquad|\\left|\\right|\\displaystyle|\{,\}")


@dataclass
class Formula:
    tex: str
    display: bool


@dataclass
class GateResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


_SPLIT = (
    r"(?ms)(^ {0,3}(?:`{3,}|~{3,}).*?^ {0,3}(?:`{3,}|~{3,})[ \t]*$"
    r"|\$\$.+?\$\$|(?<![\\$])\$(?!\$)(?=\S)(?:[^$\n\\]|\\.)*?(?<=\S)(?<!\\)\$(?!\$))"
)


_LINK_LIKE = re.compile(r"(\[[^\]\n]*\])\(")


def escape_link_like(md: str) -> str:
    """
    Printed "[DC](₹ 40)" would be read as a Markdown link. Outside code fences and math the opening parenthesis is
    escaped (`]\\(`), which displays exactly the same characters and is not a link for the editor lint either.
    """
    parts = re.split(_SPLIT, md)
    for i in range(0, len(parts), 2):
        parts[i] = _LINK_LIKE.sub(lambda m: f"{m.group(1)}\\(", parts[i])
    return "".join(parts)


def _dollar_in_inline(tex: str) -> str:
    """
    The Markdown parser ends an inline `$…$` at any `$`, even `\\$`, so a printed dollar sign inside inline math is written
    as the character code `\\char"24`, which KaTeX draws as the same glyph in math and in `\\text{}`.
    """
    return re.sub(r"(?<!\\)\\\$", lambda _m: '\\char"24 ', tex)


_TABLE_DELIM = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _is_row(line: str) -> bool:
    return "|" in line and bool(line.strip())


def table_spacing(md: str) -> str:
    """
    A table needs a blank line before it, or the parser reads its first row as more of the paragraph (or of the numbered
    item above it) and shows the pipes as text. A blank line is also kept after it.
    """
    lines = md.split("\n")
    out: list[str] = []
    fenced = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^ {0,3}(`{3,}|~{3,})", line):
            fenced = not fenced
        starts = (
            not fenced
            and _is_row(line)
            and i + 1 < len(lines)
            and "-" in lines[i + 1]
            and _TABLE_DELIM.match(lines[i + 1])
        )
        if starts:
            if out and out[-1].strip() and not _is_row(out[-1]):
                out.append("")
            while i < len(lines) and _is_row(lines[i]):
                out.append(lines[i])
                i += 1
            if i < len(lines) and lines[i].strip():
                out.append("")
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def normalize_math(md: str) -> str:
    """
    Two things the web renderer is strict about, both display the same characters:
    * a multi-line `$$…$$` needs its fences on lines of their own, because text after the opening `$$` on the same line is
      read as a label and dropped (`$$\\begin{aligned}` would lose `\\begin{aligned}`);
    * a dollar sign inside inline math (see `_dollar_in_inline`).
    """
    parts = re.split(_SPLIT, md)
    for i in range(1, len(parts), 2):
        part = parts[i]
        if part.startswith("$$"):
            inner = part[2:-2]
            if "\n" in inner.strip():
                parts[i] = "\n\n$$\n" + inner.strip() + "\n$$\n\n"
        elif part.startswith("$"):
            parts[i] = "$" + _dollar_in_inline(part[1:-1]) + "$"
    return re.sub(r"\n{3,}", "\n\n", "".join(parts)).strip("\n")


def formulas_of(md: str) -> list[Formula]:
    """Every math span in Markdown, ignoring code fences and code spans."""
    text = _FENCE.sub("", md)
    found = [Formula(m.group(1), True) for m in _DISPLAY.finditer(text)]
    rest = _DISPLAY.sub(" ", text)
    found += [Formula(m.group(1), False) for m in _INLINE.finditer(rest)]
    return found


def katex_errors(formulas: list[Formula]) -> list[str | None] | None:
    """KaTeX parse result per formula (None = fine). Returns None when node is not available, so callers can say so."""
    if not formulas:
        return []
    node = shutil.which("node")
    if not node or not WEB_PACKAGE.exists():
        return None
    proc = subprocess.run(
        [node, str(CHECKER), str(WEB_PACKAGE)],
        input=json.dumps([{"tex": f.tex, "display": f.display} for f in formulas]),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def _tex_to_text(md: str) -> str:
    """Math spans turned into text so figures can be compared with the PDF text."""

    def flat(tex: str) -> str:
        tex = _SPACING.sub(lambda m: "" if m.group(0) == "{,}" else " ", tex)
        return _TEX_CMD.sub(" ", tex).replace("{", " ").replace("}", " ")

    text = _FENCE.sub(lambda m: m.group(0), md)
    text = _DISPLAY.sub(lambda m: " " + flat(m.group(1)) + " ", text)
    return _INLINE.sub(lambda m: " " + flat(m.group(1)) + " ", text)


def figures(md: str, *, tex: bool = False) -> Counter[str]:
    """Multiset of significant figures (two or more digits, or a decimal) with Indian/Western commas removed."""
    text = _tex_to_text(md) if tex else md
    out: Counter[str] = Counter()
    for raw in _NUMBER.findall(text):
        n = raw.replace(",", "").strip(".")
        if "." in n or len(n) >= 2:
            out[n.lstrip("0") or "0"] += 1
    return out


def words(md: str, *, tex: bool = False) -> set[str]:
    text = _tex_to_text(md) if tex else md
    text = _TEX_CMD.sub(" ", text) if not tex else text
    return {w.lower() for w in _WORD.findall(text)}


def _flattened(figure: str, present: Counter[str]) -> bool:
    """`figure` (from the PDF text) is some figure of the typeset text followed by one or two exponent digits."""
    return any(
        figure.startswith(base) and 1 <= len(figure) - len(base) <= 2 and figure[len(base) :].isdigit()
        for base in present
    )


def _flattened_from(figure: str, original: Counter[str]) -> bool:
    """`figure` (typeset) is the front part of a PDF-text figure that carries flattened exponent digits."""
    return any(
        base.startswith(figure) and 1 <= len(base) - len(figure) <= 2 and base[len(figure) :].isdigit()
        for base in original
    )


def gate(original: str, typeset: str, *, katex: list[str | None] | None, formulas: list[Formula]) -> GateResult:
    res = GateResult()
    if not typeset.strip():
        res.errors.append("typeset text is empty")
        return res
    issues = richtext.errors_of(richtext.lint(typeset, richtext.QUESTION))
    res.errors += [f"lint: {i.message if hasattr(i, 'message') else i}" for i in issues]
    if katex is None:
        if formulas:
            res.warnings.append("KaTeX was not available here, so formulas were not parse-checked")
    else:
        for f, err in zip(formulas, katex, strict=True):
            if err:
                res.errors.append(f"KaTeX cannot render `{f.tex[:60]}`: {err}")
    before, after = figures(original), figures(typeset, tex=True)
    missing = before - after
    extra = after - before
    # The PDF text flattens superscripts onto their base ("1.084" for 1.08 to the 4th, "152" for 15 squared), so a figure
    # that is the base figure plus one or two exponent digits is the same figure, not a difference.
    missing = Counter({m: n for m, n in missing.items() if not _flattened(m, after)})
    extra = Counter({e: n for e, n in extra.items() if not _flattened_from(e, before)})
    if sum(missing.values()) > len(before) // 25:
        res.warnings.append("figures of the PDF text not found in the typeset text: " + ", ".join(sorted(missing)[:8]))
    if sum(extra.values()) > len(before) // 10:
        res.warnings.append("typeset text has figures not in the PDF text: " + ", ".join(sorted(extra)[:8]))
    w_before, w_after = words(original), words(typeset, tex=True)
    if w_before and len(w_before - w_after) / len(w_before) > 0.35:
        res.warnings.append("wording differs noticeably from the PDF text; check nothing was paraphrased")
    return res


def _clean(md: str) -> str:
    return lint_safe(table_spacing(normalize_math(escape_link_like(md.strip("\n")))))


def apply_overlay(
    stem: str,
    solution: str,
    entry: dict[str, Any] | None,
    *,
    check: bool = True,
) -> tuple[str, str, list[str], bool, list[str]]:
    """
    (stem_md, solution_md, review_reasons, typeset?, notes) for one item.
    Without an entry, or when a hard gate fails, the extracted text is kept and a review reason says why.
    `notes` are the transcriber's observations about the print (misprints kept as printed, layout choices). They are
    information for the reviewer and are stored with the item; only a medium/low confidence sends the item to review.
    """
    if not entry:
        return (
            stem,
            solution,
            ["no typeset version yet; the working may show flattened fractions and exponents"],
            False,
            [],
        )
    new_stem = _clean(entry.get("stem_md") or stem)
    new_sol = _clean(entry.get("explanation_md") or solution)
    reasons: list[str] = []
    for label, old, new in (("stem", stem, new_stem), ("solution", solution, new_sol)):
        if not old.strip() and not new.strip():
            continue
        fs = formulas_of(new)
        errs = katex_errors(fs) if check else None
        res = gate(old, new, katex=errs, formulas=fs)
        if not res.ok:
            return (
                stem,
                solution,
                [f"typeset {label} rejected, extracted text kept: {e}" for e in res.errors[:3]],
                False,
                [],
            )
        reasons += [f"typeset {label}: {w}" for w in res.warnings]
    notes = [str(n) for n in entry.get("review", []) or []]
    if entry.get("confidence") in ("low", "medium"):
        reasons.append(f"typeset confidence {entry['confidence']}" + (": " + "; ".join(notes[:3]) if notes else ""))
    return new_stem, new_sol, reasons, True, notes


def apply_text(label: str, old: str, new_raw: str | None, *, check: bool = True) -> tuple[str, list[str], bool]:
    """
    One text field of an overlay entry (a PYQ stem, answer or option body): (text, review_reasons, applied?).
    A hard-gate failure keeps `old` and says why; soft warnings apply the new text and send the part to review.
    """
    if not new_raw or not new_raw.strip():
        return old, [], False
    new = _clean(new_raw)
    fs = formulas_of(new)
    res = gate(old, new, katex=katex_errors(fs) if check else None, formulas=fs)
    if not res.ok:
        return old, [f"typeset {label} rejected, extracted text kept: {e}" for e in res.errors[:3]], False
    return new, [f"typeset {label}: {w}" for w in res.warnings], True


def load_overlay(folder: Path, paper: str) -> dict[str, dict[str, Any]]:
    path = folder / f"p{paper.lower()}.json"
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: expected schema {SCHEMA}")
    return doc.get("items", {})


def load_overlay_file(path: Path) -> dict[str, dict[str, Any]]:
    """A per-paper-term overlay (`seed/cma-final/pyq-typeset/p14-2024-06.json`), keyed by part reference."""
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise ValueError(f"{path.name}: expected schema {SCHEMA}")
    return doc.get("items", {})
