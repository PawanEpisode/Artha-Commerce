"""
From the Markdown a student sent to what is stored: sanitise, lint under the `note` profile and the plan's limits, check the
images, and derive plain text and language. `prepare_body` refuses (422 `invalid_body`); `derive_body` is the lenient twin used
when an old version is restored, where the text was valid when it was saved.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import richtext
from modules.media import services as media

from ..domain.quota import Limits
from ..domain.search_query import detect_lang
from ..errors import InvalidBody

IMAGE_KIND = "note_image"


@dataclass(frozen=True)
class Body:
    md: str
    text: str
    chars: int
    lang: str
    refs: tuple[richtext.ImageRef, ...]


def clean_title(title: str) -> str:
    """One line, no control characters (a title is never multi-line)."""
    return " ".join(richtext.sanitise(title).split())


def derive_body(md: str, title: str = "") -> Body:
    md = richtext.sanitise(md)
    text = richtext.plain_text(md)
    return Body(md, text, len(md), detect_lang(f"{title} {text}"), tuple(richtext.attachment_refs(md)))


def _issue(code: str, message: str, line: int | None = None) -> dict:
    return {"code": code, "message": message, "line": line}


def prepare_body(user_id, md: str, title: str, limits: Limits) -> Body:
    body = derive_body(md, title)
    errors = [_issue(i.code, i.message, i.line) for i in richtext.errors_of(richtext.lint(body.md, richtext.NOTE))]
    if limits.max_note_chars < body.chars <= richtext.NOTE.max_chars:
        errors.append(_issue("too_long", f"The text can have at most {limits.max_note_chars:,} characters."))
    unique = {r.attachment_id: r for r in body.refs}
    if len(unique) > limits.max_note_images and not any(e["code"] == "too_many_images" for e in errors):
        errors.append(_issue("too_many_images", f"At most {limits.max_note_images} images are allowed."))
    clean = media.clean_attachment_ids(user_id, unique, IMAGE_KIND)
    errors += [
        _issue("unknown_attachment", "This image is not one of your uploaded images.", ref.line)
        for attachment_id, ref in unique.items()
        if attachment_id not in clean
    ]
    if errors:
        raise InvalidBody(extra={"errors": errors})
    return body
