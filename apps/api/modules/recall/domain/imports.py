"""
Paste and CSV import, the pure half (FR-F13, R2-W3 F). No I/O, no Django.

Two shapes of one pasted block:

- plain: one pointer per line, `front :: back` (a tab works too). A line without a back is a row error, never a silent card.
- columns: the first line is the header `kind,front,back,chapter` (comma, tab or semicolon; `chapter` is optional) and every
  other line is one row. Quotes follow CSV, so a cell may hold commas and line breaks. A blank kind means pointer.

A row is `RawRow(line, kind, front, back, chapter, error)`. Parsing never raises: a line that cannot be split becomes a row with
an `error` code and the service reports it like any other invalid row. The ERD states no import row limit, so the limit is 200
a call (the same as a bulk change).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

ROW_LIMIT = 200
TEXT_MAX_CHARS = 400_000
SEPARATOR = " :: "
HEADER = ("kind", "front", "back", "chapter")
DEFAULT_KIND = "pointer"

MISSING_BACK = "missing_back"
TOO_MANY_COLUMNS = "too_many_columns"
BAD_ROW = "bad_row"


@dataclass(frozen=True)
class RawRow:
    line: int  # 1-based position in what she pasted (the row number for `rows[]`)
    kind: str
    front: str
    back: str
    chapter: str = ""
    error: str | None = None


def _delimiter(header_line: str) -> str:
    for d in ("\t", ",", ";"):
        if d in header_line:
            return d
    return ","


def _is_header(line: str) -> bool:
    cells = [c.strip().strip('"').lower() for c in line.split(_delimiter(line))]
    return len(cells) >= 3 and tuple(cells[:3]) == HEADER[:3] and cells[3:] in ([], ["chapter"])


def _plain(text: str) -> list[RawRow]:
    rows: list[RawRow] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        sep = SEPARATOR if SEPARATOR in line else ("\t" if "\t" in line else None)
        if sep is None:
            rows.append(RawRow(number, DEFAULT_KIND, line, "", error=MISSING_BACK))
            continue
        front, back = line.split(sep, 1)
        rows.append(RawRow(number, DEFAULT_KIND, front.strip(), back.strip()))
    return rows


def _columns(text: str) -> list[RawRow]:
    lines = text.splitlines()
    first = next(i for i, ln in enumerate(lines) if ln.strip())
    delimiter = _delimiter(lines[first])
    reader = csv.reader(io.StringIO("\n".join(lines[first + 1 :])), delimiter=delimiter)
    rows: list[RawRow] = []
    previous = 0
    try:
        for cells in reader:
            number = first + 2 + previous  # the physical line this record starts on
            previous = reader.line_num
            if not any(c.strip() for c in cells):
                continue
            if len(cells) > len(HEADER):
                rows.append(RawRow(number, DEFAULT_KIND, "", "", error=TOO_MANY_COLUMNS))
                continue
            cells = [c.strip() for c in cells] + [""] * (len(HEADER) - len(cells))
            kind, front, back, chapter = cells
            rows.append(RawRow(number, (kind or DEFAULT_KIND).lower(), front, back, chapter))
    except csv.Error:
        rows.append(RawRow(first + 2 + previous, DEFAULT_KIND, "", "", error=BAD_ROW))
    return rows


def parse_text(text: str) -> list[RawRow]:
    """The rows of a pasted block, in order. Blank lines are skipped; an empty block gives no rows."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    first = next((ln for ln in text.split("\n") if ln.strip()), None)
    if first is None:
        return []
    return _columns(text) if _is_header(first) else _plain(text)


def from_rows(rows: Iterable[Mapping[str, object]]) -> list[RawRow]:
    """The same rows from a structured list (`rows[]` of the API): each item `{kind?, front, back?, chapter?}`."""
    out: list[RawRow] = []
    for number, item in enumerate(rows, start=1):
        out.append(
            RawRow(
                number,
                (str(item.get("kind") or DEFAULT_KIND)).strip().lower(),
                str(item.get("front") or "").strip(),
                str(item.get("back") or "").strip(),
                str(item.get("chapter") or "").strip(),
            )
        )
    return out


def importable_fields(required: list[str]) -> bool:
    """A kind can be filled from `front` and `back` only when it has at most two required fields."""
    return 1 <= len(required) <= 2


def map_fields(required: list[str], row: RawRow) -> dict[str, str]:
    """`front` fills the first required field and `back` the second (a one-field kind, a cloze, takes the front only)."""
    out = {required[0]: row.front}
    if len(required) > 1:
        out[required[1]] = row.back
    return out
