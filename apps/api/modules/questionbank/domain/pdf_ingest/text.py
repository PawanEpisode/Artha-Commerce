"""
Text clean-up shared by the PDF parsers.

Why this exists: the Institute's PDFs encode the rupee sign in three different broken ways, and OCR adds more.
We repair them by rule, never by rewording the question.
"""

from __future__ import annotations

import re

RUPEE = "₹"

_WS = re.compile(r"[ \t ]+")
# Workbooks print the rupee as a backtick: "` 60,00,000", "`.8/hour", "`.6.20 lakh".
_BACKTICK_MONEY = re.compile(r"`\.?\s?(?=\d)")
# Suggested-answer PDFs print the rupee as the letter D: "D 4,18,279", "D1,000". Never touches "(D)" or "Option D".
_D_MONEY = re.compile(r"(?<![A-Za-z0-9(])(?<!Section )(?<!Option )(?<!Part )(?<!Annexure )D\s?(?=\d)")
# OCR reads the rupee glyph as one of these when it sits directly before a number.
_OCR_MONEY = re.compile(r"(?:(?<=\s)|(?<=\()|^)[¥€&*=<«~]\s?(?=\d)", re.M)
_OCR_PERCENT_MONEY = re.compile(r"(?:(?<=\s)|(?<=\()|^)%\s?(?=\d)", re.M)


def collapse_ws(text: str) -> str:
    """One line, single spaces. Used for table cells and MCQ stems."""
    return _WS.sub(" ", (text or "").replace("\r", "").replace("\n", " ")).strip()


_LONE_BACKTICK = re.compile(r"(?<!`)`(?!``)")


def fix_workbook_rupee(text: str) -> str:
    """The workbooks' rupee glyph is a backtick. Every backtick that is not part of a markdown ``` fence is a rupee sign."""
    out = _BACKTICK_MONEY.sub(RUPEE + " ", text or "").replace(RUPEE + "  ", RUPEE + " ")
    return _LONE_BACKTICK.sub(RUPEE, out)


def fix_answer_rupee(text: str) -> str:
    """Suggested-answer PDFs: the letter D stands for the rupee sign when it sits right before a figure."""
    return _D_MONEY.sub(RUPEE + " ", text or "").replace(RUPEE + "  ", RUPEE + " ")


def fix_ocr_rupee(text: str) -> str:
    """OCR output: the rupee sign comes back as ¥ € & * = < % ~ before a figure. Percent signs after a digit are untouched."""
    out = _OCR_MONEY.sub(RUPEE, text or "")
    return _OCR_PERCENT_MONEY.sub(RUPEE, out)


def normalise_key_text(text: str) -> str:
    """Comparison form for matching an answer cell to an option cell: lowercase letters and digits only."""
    t = (text or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", t)


def markdown_table(rows: list[list[str]]) -> str:
    """Rows of cells to a GitHub markdown table. The first row is the header. Pipes in cells are escaped."""
    clean = [[collapse_ws(c).replace("|", "\\|") for c in row] for row in rows if any((c or "").strip() for c in row)]
    if not clean:
        return ""
    width = max(len(r) for r in clean)
    clean = [r + [""] * (width - len(r)) for r in clean]
    head, *body = clean
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * width) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


# --- tables rebuilt from layout text -------------------------------------------------------------------------------------

_SEG = re.compile(r"\S+(?: \S+)*")  # a run of words separated by single spaces; two or more spaces start a new cell
_NUMBERISH = re.compile(r"^[\s\d,.\-–()%₹`/]+$")
_LIST_MARK = re.compile(r"^(?:[0-9]{1,2}|[ivxIVX]{1,4}|[a-zA-Z])[.)]$")


def _segments(line: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in _SEG.finditer(line)]


def _is_tabular(segs: list[tuple[int, int, str]]) -> bool:
    if len(segs) >= 3:
        return True
    if len(segs) == 2:
        first, second = segs[0][2], segs[1][2]
        if _LIST_MARK.match(first) and len(second) > 25:
            return False  # "i.        To avoid sub optimisation, ..." is a numbered paragraph, not a table
        return any(ch.isdigit() for ch in first + second) and len(first) + len(second) <= 80
    return False


def _split_words(line: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", line)]


# Mirrors the question editor lint (tables of at most 40 rows and 12 columns).
MAX_TABLE_ROWS = 40
MAX_TABLE_COLS = 12


def _fence(rows: list[str]) -> str:
    indent = min((len(r) - len(r.lstrip())) for r in rows if r.strip())
    body = "\n".join(r[indent:].rstrip() for r in rows)
    return f"```text\n{body}\n```"


def _render_group(rows: list[str]) -> str:
    """Rebuild one run of tabular layout lines as a markdown table, or keep it as an aligned text block if unsure."""
    parsed = [_segments(r) for r in rows]
    anchor = max(parsed, key=len)
    spans = [(s, e) for s, e, _ in anchor]
    if len(rows) > MAX_TABLE_ROWS or len(spans) > MAX_TABLE_COLS:
        return _fence(rows)  # the editor's table limit; an aligned text block keeps every figure intact
    header_words = len(parsed[0]) < len(spans)
    if header_words:
        parsed[0] = _split_words(rows[0])  # a header row whose labels were separated by single spaces
    grid: list[list[str]] = []
    for ridx, segs in enumerate(parsed):
        cells = [""] * len(spans)
        for s, e, text in segs:
            overlaps = [max(0, min(e, ce) - max(s, cs)) for cs, ce in spans]
            best = max(range(len(spans)), key=lambda i: overlaps[i])
            if overlaps[best] == 0:
                centre = (s + e) / 2
                nearest = min(range(len(spans)), key=lambda i: abs((spans[i][0] + spans[i][1]) / 2 - centre))
                if abs((spans[nearest][0] + spans[nearest][1]) / 2 - centre) > 8:
                    return _fence(rows)
                best = nearest
            if cells[best]:
                if ridx == 0 and header_words:
                    cells[best] += " " + text  # several header words fall in one column
                    continue
                return _fence(rows)  # two cells claim the same column: alignment is not what we thought
            cells[best] = text
        grid.append(cells)
    header_is_data = any(_NUMBERISH.match(c) and any(ch.isdigit() for ch in c) for c in grid[0])
    if header_is_data:
        grid = [[""] * len(spans), *grid]
    return markdown_table(grid)


def layout_to_markdown(text: str) -> str:
    """
    Turn layout text (pdftotext -layout style) into markdown: runs of two or more tabular lines become tables,
    everything else is kept line for line. A table whose columns do not line up is kept as an aligned text block, so a
    figure is never moved to the wrong column.
    """
    out: list[str] = []
    group: list[str] = []

    def flush() -> None:
        if len(group) >= 2:
            out.append(_render_group(group))
        else:
            out.extend(group)
        group.clear()

    lines = text.splitlines()
    tabular = [bool(ln.strip()) and _is_tabular(_segments(ln)) for ln in lines]
    # A column-header line such as "Year    CFAT" has no digits, so it is not tabular on its own; it belongs to the table below it.
    for i in range(len(lines) - 1):
        segs = _segments(lines[i])
        if not tabular[i] and tabular[i + 1] and len(segs) >= 2 and all(len(t) <= 40 for _, _, t in segs):
            tabular[i] = True
    for i, line in enumerate(lines):
        if tabular[i]:
            group.append(line.rstrip())
            continue
        flush()
        out.append(line.rstrip())
    flush()
    return "\n".join(out)


# --- keep transcribed markdown inside the editor's lint rules, without changing what it says --------------------------

_ATX_LINE = re.compile(r"^( {0,3})(#{1,6})(?=\s|$)", re.M)
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def lint_safe(md: str) -> str:
    """
    A printed `#` at the start of a line is escaped (renders the same, is not a heading) and a table larger than the editor
    allows is kept as an aligned text block. Nothing is reworded.
    """
    if not md:
        return md
    md = _ATX_LINE.sub(lambda m: f"{m.group(1)}\\{m.group(2)}", md)
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and "|" in lines[i] and _TABLE_SEP.match(lines[i + 1]) and "-" in lines[i + 1]:
            j = i + 2
            while j < len(lines) and lines[j].strip() and "|" in lines[j]:
                j += 1
            cols = len(re.split(r"(?<!\\)\|", lines[i].strip().strip("|")))
            if (j - i - 2) > MAX_TABLE_ROWS or cols > MAX_TABLE_COLS:
                out += ["```text", *lines[i:j], "```"]
            else:
                out += lines[i:j]
            i = j
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


_BARE_DELIM = re.compile(r"^\s*:?-{3,}:?(\s*\|\s*:?-{3,}:?)+\s*$")


def fix_pipeless_tables(md: str) -> str:
    """
    Tables transcribed without the outer pipes ("Firm | Capital | Value" over "---|---|---") are valid GFM only when the
    delimiter row is written in full; the page images often gave a bare delimiter and a leading space on the header, which
    the renderer shows as text. Rewrites such blocks as standard `| a | b |` tables. Everything else is untouched.
    """
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    fenced = False
    while i < len(lines):
        line = lines[i]
        if re.match(r"^ {0,3}(`{3,}|~{3,})", line):
            fenced = not fenced
        if (
            not fenced
            and i + 1 < len(lines)
            and "|" in line
            and not line.strip().startswith("$")
            and _BARE_DELIM.match(lines[i + 1])
            and not (
                line.strip().startswith("|") and line.strip().endswith("|") and lines[i + 1].strip().startswith("|")
            )
        ):
            width = len([c for c in lines[i + 1].strip().strip("|").split("|")])
            block = [line]
            j = i + 2
            while j < len(lines) and lines[j].strip() and "|" in lines[j]:
                block.append(lines[j])
                j += 1

            def cells(row: str, n: int = width) -> str:
                body = row.strip()
                if body.startswith("|"):
                    body = body[1:]
                if body.endswith("|"):
                    body = body[:-1]
                parts = [c.strip() for c in body.split("|")]
                parts += [""] * (n - len(parts))
                return "| " + " | ".join(parts[:n]) + " |"

            if out and out[-1].strip():
                out.append("")
            out.append(cells(block[0]))
            out.append("|" + "|".join("---" for _ in range(width)) + "|")
            out.extend(cells(r) for r in block[1:])
            i = j
            continue
        out.append(line)
        i += 1
    return "\n".join(out)
