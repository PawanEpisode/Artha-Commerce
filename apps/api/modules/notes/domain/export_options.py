"""
Options of a flattened PDF export (contract `POST documents/{id}/exports/`) and the rule for who may export, both pure.

Who may export (PRD FR-F03-20, ERD 6.5): never a locked file (needs a password), never a file that is not inspected yet, and
never a copy-restricted one, which means the permission flags the inspector read say copying OR modifying is forbidden
(`can_copy` or `can_modify` is False). Unknown flags (None) are allowed here and the worker's own check on the real file has
the last word (`restricted`). Annotating such a file stays allowed; only the burned-in copy is refused.
"""

from __future__ import annotations

from dataclasses import dataclass

from .legend import COLOR_KEYS
from .pagespec import PageSpecError, format_pages, parse_pages

INCLUDE_KINDS = ("highlight", "underline", "ink", "textbox", "sticky", "area")
INK_KEYS = ("i1", "i2", "i3", "i4", "i5")
ALL_COLORS = (*COLOR_KEYS, *INK_KEYS)
MAX_TAGS = 50
KNOWN_OPTIONS = frozenset({"pages", "include", "colors", "tags", "appendix"})


class OptionsError(ValueError):
    """`field` names the option at fault, for the 422 `invalid_options` details."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class ExportOptions:
    pages: tuple[int, ...] | None = None  # None: every page
    include: tuple[str, ...] = INCLUDE_KINDS
    colors: tuple[str, ...] | None = None  # None: every colour; marks without a colour are always kept
    tags: tuple[str, ...] | None = None  # None: no tag filter; otherwise marks carrying any of these tag ids
    appendix: bool = False

    def stored(self) -> dict:
        """What is saved on the job: only what the student chose, in canonical form."""
        out: dict = {}
        if self.pages is not None:
            out["pages"] = format_pages(self.pages)
        if self.include != INCLUDE_KINDS:
            out["include"] = list(self.include)
        if self.colors is not None:
            out["colors"] = list(self.colors)
        if self.tags is not None:
            out["tags"] = list(self.tags)
        if self.appendix:
            out["appendix"] = True
        return out


def _string_list(raw, name: str, allowed: tuple[str, ...] | None, limit: int) -> tuple[str, ...]:
    if not isinstance(raw, list) or len(raw) > limit or not all(isinstance(v, str) for v in raw):
        raise OptionsError(name, f"`{name}` must be a short list of strings.")
    if allowed is not None:
        bad = sorted({v for v in raw if v not in allowed})
        if bad:
            raise OptionsError(name, f"Unknown value in `{name}`.")
    return tuple(dict.fromkeys(raw))


def validate_options(raw, page_count: int) -> ExportOptions:
    """Checks the options against the file's page count and returns them in canonical form. Raises `OptionsError`."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise OptionsError("options", "`options` must be an object.")
    unknown = sorted(set(raw) - KNOWN_OPTIONS)
    if unknown:
        raise OptionsError("options", "Unknown option.")
    pages = None
    if raw.get("pages") not in (None, ""):
        if not isinstance(raw["pages"], str):
            raise OptionsError("pages", "Use pages like 1-40,50.")
        try:
            pages = tuple(parse_pages(raw["pages"], page_count))
        except PageSpecError as exc:
            raise OptionsError("pages", str(exc)) from exc
        if len(pages) == page_count:
            pages = None  # "everything" is the same as no selection: one canonical form
    include = INCLUDE_KINDS
    if raw.get("include") is not None:
        chosen = _string_list(raw["include"], "include", INCLUDE_KINDS, len(INCLUDE_KINDS))
        if not chosen:
            raise OptionsError("include", "Choose at least one kind of mark.")
        include = tuple(k for k in INCLUDE_KINDS if k in chosen)
    colors = None
    if raw.get("colors") is not None:
        colors = tuple(c for c in ALL_COLORS if c in _string_list(raw["colors"], "colors", ALL_COLORS, len(ALL_COLORS)))
        if not colors:
            raise OptionsError("colors", "Choose at least one colour.")
    tags = None
    if raw.get("tags") is not None:
        tags = tuple(sorted(_string_list(raw["tags"], "tags", None, MAX_TAGS)))
    appendix = raw.get("appendix", False)
    if not isinstance(appendix, bool):
        raise OptionsError("appendix", "`appendix` must be true or false.")
    return ExportOptions(pages, include, colors, tags, appendix)


def export_block_reason(
    *, status: str, is_encrypted: bool, page_count: int | None, can_copy: bool | None, can_modify: bool | None
) -> str | None:
    """`locked`, `not_ready`, `restricted`, or None when a flattened copy may be made."""
    if status == "needs_password" or (is_encrypted and page_count is None):
        return "locked"
    if status != "ready" or not page_count:
        return "not_ready"
    if can_copy is False or can_modify is False:
        return "restricted"
    return None
