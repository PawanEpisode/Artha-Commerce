"""
Rich text rules shared by every module: sanitised Markdown with KaTeX (F-06 PRD 8.2, F-03 PRD 8.2).

The database stores `body_md` (canonical) and a derived plain `body_text`; no HTML is stored. A *profile* says how much
Markdown a field may use, so questions and notes share one pipeline and one conformance corpus
(`core/tests/richtext_cases.json`, also run by the web twin) instead of two diverging linters.

    lint(md, "note")        -> list[Issue]    errors block a save, warnings are shown to the author
    plain_text(md)          -> str            for search vectors, fingerprints and snippets
    sanitise(md)            -> str            canonical text: newlines, control and bidi-override characters
    attachment_refs(md)     -> list[ImageRef] the `![alt](attachment:<uuid>)` images, in order

Scope on purpose: this is a linter and a text extractor, not a renderer. Raw HTML is never an error: like the renderer it is
kept as literal text, and reported as the warning `raw_html`. Code fences and code spans are masked first, so nothing below
fires inside code. KaTeX itself runs on the client with `trust: false`; here we reject the commands that matter for safety.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

CORPUS_VERSION = 1


@dataclass(frozen=True)
class Profile:
    """Limits of one kind of field. `headings` is the allowed (min, max) ATX level, or None when headings are not allowed."""

    name: str
    max_chars: int
    max_images: int
    max_table_rows: int  # body rows, not counting the header
    max_table_cols: int
    headings: tuple[int, int] | None
    task_lists: bool
    rules: bool
    alt_required: (
        bool  # missing alt text is an error (questions) or a warning (notes: the editor offers "mark decorative")
    )
    max_math_chars: int = 2000  # per expression
    max_math_count: int = 200


QUESTION = Profile("question", 20_000, 12, 40, 12, headings=None, task_lists=False, rules=False, alt_required=True)
NOTE = Profile("note", 100_000, 40, 100, 12, headings=(2, 4), task_lists=True, rules=True, alt_required=False)
PROFILES = {p.name: p for p in (QUESTION, NOTE)}


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    line: int | None = None  # 1-based; None for whole-body issues
    severity: str = "error"  # "error" blocks the save, "warning" does not


@dataclass(frozen=True)
class ImageRef:
    attachment_id: uuid.UUID
    alt: str
    line: int


def profile_of(profile: Profile | str) -> Profile:
    return profile if isinstance(profile, Profile) else PROFILES[profile]


# --- Canonical text ---------------------------------------------------------------------------------------------------
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Bidirectional overrides and the byte-order mark can make text read differently from how it is stored. The zero-width
# joiners U+200C and U+200D are NOT touched: Devanagari needs them.
_BIDI = re.compile("[‪-‮⁦-⁩﻿]")


def sanitise(markdown: str) -> str:
    """Canonical form to store: LF newlines, no control or bidi-override characters. Never changes visible text."""
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    return _BIDI.sub("", _CONTROL.sub("", text))


# --- Masking code -----------------------------------------------------------------------------------------------------
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_CODE_SPAN = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)")


def _mask_code(markdown: str) -> list[str]:
    """The lines with fenced blocks and inline code blanked out (same line count), so no rule fires inside code."""
    lines, fence = [], None
    for line in markdown.split("\n"):
        match = _FENCE.match(line)
        if fence:
            closes = match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence)
            if closes and not match.group(2).strip():
                fence = None
            lines.append("")
        elif match:
            fence = match.group(1)
            lines.append("")
        else:
            lines.append(_CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line))
    return lines


def _line_at(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


# --- Patterns ---------------------------------------------------------------------------------------------------------
_DISPLAY_MATH = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
# Inline math follows the Pandoc rule so prices do not become formulas: the opening `$` is followed and the closing `$` is
# preceded by a non-space, and `\$` is a literal dollar. The web twin uses the same expression.
_INLINE_MATH = re.compile(r"(?<![\\$])\$(?!\$)(?=\S)([^$\n]*?\S)(?<!\\)\$(?!\$)")
_FORBIDDEN_TEX = re.compile(
    r"\\(href|url|includegraphics|html[A-Za-z]*|def|edef|gdef|xdef|newcommand|renewcommand|providecommand|input|write)(?![A-Za-z])"
)
_ATTACHMENT = re.compile(r"^attachment:([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$")
_IMAGE = re.compile(r"!\[([^\]\n]*)\]\(\s*([^)\s]*)(?:\s+\"[^\"\n]*\")?\s*\)")
_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(\s*([^)\s]*)(?:\s+\"[^\"\n]*\")?\s*\)")
_AUTOLINK = re.compile(r"<([A-Za-z][A-Za-z0-9+.-]*:[^>\s]*)>")
_HTML_TAG = re.compile(r"</?[A-Za-z][^<>\n]*>|<!--")
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:\s|$)")
_RULE = re.compile(r"^ {0,3}([-*_])(?: *\1){2,} *$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+) *$")
_TASK = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\](?:\s|$)")
_FOOTNOTE = re.compile(r"\[\^[^\]\s]+\]")
_TABLE_DELIMITER = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


def _cells(row: str) -> int:
    row = row.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    return len(re.split(r"(?<!\\)\|", row))


def _table_issues(lines: list[str], p: Profile) -> list[Issue]:
    issues = []
    i = 0
    while i < len(lines) - 1:
        header, delimiter = lines[i], lines[i + 1]
        if "|" in header and _TABLE_DELIMITER.match(delimiter) and "-" in delimiter and "|" in (header + delimiter):
            cols, rows, j = _cells(header), 0, i + 2
            while j < len(lines) and lines[j].strip() and "|" in lines[j]:
                rows += 1
                j += 1
            if cols > p.max_table_cols or rows > p.max_table_rows:
                issues.append(
                    Issue(
                        "table_too_large",
                        f"Tables can have at most {p.max_table_rows} rows and {p.max_table_cols} columns.",
                        i + 1,
                    )
                )
            i = j
        else:
            i += 1
    return issues


def _heading_issues(lines: list[str], p: Profile) -> list[Issue]:
    issues = []
    for n, line in enumerate(lines, 1):
        level = None
        atx = _ATX.match(line)
        if atx:
            level = len(atx.group(1))
        elif n > 1 and lines[n - 2].strip() and not _ATX.match(lines[n - 2]):
            setext = _SETEXT.match(line)
            if setext and not lines[n - 2].lstrip().startswith(("-", "*", "+", ">", "|")):
                level = 1 if setext.group(1)[0] == "=" else 2
        if level is None:
            continue
        if p.headings is None or not p.headings[0] <= level <= p.headings[1]:
            allowed = "not allowed here" if p.headings is None else f"allowed from {p.headings[0]} to {p.headings[1]}"
            issues.append(Issue("heading_level", f"Headings are {allowed}.", n))
    return issues


def _rule_issues(lines: list[str], p: Profile) -> list[Issue]:
    if p.rules:
        return []
    issues = []
    for n, line in enumerate(lines, 1):
        previous_blank = n == 1 or not lines[n - 2].strip()
        if _RULE.match(line) and previous_blank:
            issues.append(Issue("rule_not_allowed", "Horizontal rules are not allowed here.", n))
    return issues


def _math_issues(masked: str, p: Profile) -> list[Issue]:
    issues, expressions = [], []
    for m in _DISPLAY_MATH.finditer(masked):
        expressions.append((m.group(1), _line_at(masked, m.start())))
    rest = _DISPLAY_MATH.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), masked)
    for m in _INLINE_MATH.finditer(rest):
        expressions.append((m.group(1), _line_at(rest, m.start())))
    if len(expressions) > p.max_math_count:
        issues.append(Issue("too_many_formulas", f"At most {p.max_math_count} formulas are allowed.", None))
    for expression, line in expressions:
        if len(expression) > p.max_math_chars:
            issues.append(Issue("formula_too_long", f"A formula can have at most {p.max_math_chars} characters.", line))
        found = _FORBIDDEN_TEX.search(expression)
        if found:
            issues.append(Issue("forbidden_tex", f"The command \\{found.group(1)} is not allowed in formulas.", line))
    return issues


def _link_issues(masked: str) -> list[Issue]:
    issues = []
    targets = [(m.group(1), m.start()) for m in _LINK.finditer(masked)]
    targets += [(m.group(1), m.start()) for m in _AUTOLINK.finditer(masked)]
    for target, pos in targets:
        if not (target.startswith(("https://", "#")) or target == ""):
            issues.append(Issue("link_scheme", "Links must start with https://.", _line_at(masked, pos)))
    return issues


def _image_issues(masked: str, p: Profile) -> list[Issue]:
    issues, count = [], 0
    for m in _IMAGE.finditer(masked):
        count += 1
        line = _line_at(masked, m.start())
        if not _ATTACHMENT.match(m.group(2)):
            issues.append(Issue("image_not_attachment", "Images must be uploaded; use ![alt](attachment:id).", line))
        elif not m.group(1).strip():
            severity = "error" if p.alt_required else "warning"
            issues.append(Issue("missing_alt", "This image has no alt text.", line, severity))
    if count > p.max_images:
        issues.append(Issue("too_many_images", f"At most {p.max_images} images are allowed.", None))
    return issues


def lint(markdown: str, profile: Profile | str = NOTE) -> list[Issue]:
    """All problems with `markdown` under `profile`, sorted by line (whole-body issues first). Errors block a save."""
    p = profile_of(profile)
    issues: list[Issue] = []
    if len(markdown) > p.max_chars:
        issues.append(Issue("too_long", f"The text can have at most {p.max_chars:,} characters.", None))
    lines = _mask_code(markdown)
    masked = "\n".join(lines)
    issues += _heading_issues(lines, p) + _rule_issues(lines, p) + _table_issues(lines, p)
    issues += _math_issues(masked, p) + _link_issues(masked) + _image_issues(masked, p)
    for n, line in enumerate(lines, 1):
        if not p.task_lists and _TASK.match(line):
            issues.append(Issue("task_list_not_allowed", "Task lists are not allowed here.", n))
        if _FOOTNOTE.search(line):
            issues.append(Issue("footnote_not_allowed", "Footnotes are not supported.", n))
        if _HTML_TAG.search(_AUTOLINK.sub("", line)):
            issues.append(Issue("raw_html", "HTML is shown as plain text, not rendered.", n, "warning"))
    return sorted(issues, key=lambda i: (i.line or 0, i.code))


def errors_of(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]


def attachment_refs(markdown: str) -> list[ImageRef]:
    """The uploaded images a body uses, in order, with their alt text (empty when decorative or missing)."""
    masked = "\n".join(_mask_code(markdown))
    refs = []
    for m in _IMAGE.finditer(masked):
        found = _ATTACHMENT.match(m.group(2))
        if found:
            refs.append(ImageRef(uuid.UUID(found.group(1)), m.group(1).strip(), _line_at(masked, m.start())))
    return refs


# --- Plain text -------------------------------------------------------------------------------------------------------
_PLAIN_STEPS = [
    (re.compile(r"!\[([^\]\n]*)\]\([^)\n]*\)"), r"\1"),  # image: its alt text
    (re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)"), r"\1"),  # link: its text
    (_AUTOLINK, r"\1"),  # <https://...>: the address
    (re.compile(r"</?[A-Za-z][^<>\n]*>|<!--|-->"), " "),  # raw HTML tags: the markup, not the words inside
    (re.compile(r"^ {0,3}#{1,6}\s+", re.MULTILINE), ""),  # heading marker
    (re.compile(r"^ {0,3}>+\s?", re.MULTILINE), ""),  # blockquote
    (re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?", re.MULTILINE), ""),  # list and task markers
    (re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*$", re.MULTILINE), ""),  # table delimiter row
    (re.compile(r"^ {0,3}([-*_])(?: *\1){2,} *$|^ {0,3}=+ *$", re.MULTILINE), ""),  # rules and setext underlines
    (re.compile(r"(?<!\\)\|"), " "),  # table cell separators
    (re.compile(r"(\*\*|__|~~|\*|(?<![A-Za-z0-9])_|_(?![A-Za-z0-9]))"), ""),  # emphasis markers
    (re.compile(r"(?<!\\)\$+"), ""),  # math delimiters: the formula text stays searchable
    (re.compile(r"\\([\\`*_{}\[\]()#+\-.!|$])"), r"\1"),  # backslash escapes (after the delimiters: `\$` is a dollar)
]


def _stash(spans: list[str], match: re.Match) -> str:
    inner = match.group(0).strip("`").strip()
    spans.append(inner)
    return f"\x00{len(spans) - 1}\x00"


def _plain_line(line: str) -> str:
    spans: list[str] = []  # code spans are set aside so nothing below rewrites their text
    line = _CODE_SPAN.sub(lambda m: _stash(spans, m), line)
    for pattern, replacement in _PLAIN_STEPS:
        line = pattern.sub(replacement, line)
    return re.sub("\x00(\\d+)\x00", lambda m: spans[int(m.group(1))], line)


def plain_text(markdown: str) -> str:
    """
    The words of a body without Markdown syntax, one line per block, for search and snippets. Code keeps its text. Formulas
    keep their TeX source (a student can search "frac"), without the `$` delimiters.
    """
    kept, fence = [], None
    for line in sanitise(markdown).split("\n"):
        match = _FENCE.match(line)
        if fence:
            if (
                match
                and match.group(1)[0] == fence[0]
                and len(match.group(1)) >= len(fence)
                and not match.group(2).strip()
            ):
                fence = None
            else:
                kept.append(("code", line))
        elif match:
            fence = match.group(1)
        else:
            kept.append(("md", line))
    out = []
    for kind, line in kept:
        if kind == "md":
            line = _plain_line(line)
        words = " ".join(line.split())
        if words:
            out.append(words)
    return "\n".join(out)
