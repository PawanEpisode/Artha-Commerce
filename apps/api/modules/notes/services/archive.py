"""
"Download my notes" (PRD FR-F03-54): a zip of the student's notes as Markdown and, when `notes_pdf` is on for them, a digest of
the marks of every document as Markdown and CSV. Built by the worker into a temp file, entry by entry (streamed: memory holds
one batch of notes, never the archive), stored as `note_export` and linked for 24 hours on demand.

    notes/0001-<slug>.md       front matter (title, chapter, subject, tags, created, updated) and the note's Markdown as is
    documents/001-digest.md    page, kind, colour NAME (the student's own legend), quote, comment, chapter, tags
    documents/001-digest.csv   the same rows, one per mark (cells that a spreadsheet would run as a formula are defused)
    README.md                  what is in the zip

File names come from a counter and the title's ASCII slug, never from an uploaded file name, so there are no collisions and
no path tricks. At most the plan's note count of notes goes in. It is a data-portability feature: it needs the `notes` flag,
not `notes_pdf`, and it is not charged to the monthly export quota (the throttle is its brake).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import tempfile
import zipfile
from datetime import UTC, datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from core import jobs as core_jobs
from core.feature_flags import flag_enabled
from modules.media import services as media

from .. import events
from ..domain.legend import DEFAULT_LEGEND
from ..media_kinds import EXPORT_RETENTION_DAYS, ZIP_MIME
from ..models import Document, ExportJob, Settings
from ..selectors import exports as export_selectors
from . import quota

logger = logging.getLogger(__name__)

JOB_EXPORT_ARCHIVE = "notes.export_archive"  # same string as `notes.jobs.JOB_EXPORT_ARCHIVE`
KIND = "note_export"
PDF_FLAG = "notes_pdf"
DIGEST_KINDS = ("highlight", "underline", "area", "sticky", "textbox", "bookmark")
INK_NAMES = {"i1": "Black pen", "i2": "Red pen", "i3": "Blue pen", "i4": "Green pen", "i5": "Purple pen"}
CSV_COLUMNS = ("page", "kind", "colour", "quote", "comment", "chapter", "tags")
SLUG_MAX = 40
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


# --- Pure helpers -------------------------------------------------------------------------------------------------------
def note_slug(title: str) -> str:
    """ASCII slug of a title for a file name; `note` when nothing usable is left (Hindi titles, empty titles)."""
    return slugify(title or "")[:SLUG_MAX].strip("-") or "note"


def front_matter(fields: dict) -> str:
    """A YAML block. Strings and lists are written as JSON, which is valid YAML and escapes everything that could break it."""
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def colour_name(key: str | None, legend: dict) -> str:
    """The student's name for a highlight colour, a fixed name for a pen colour, empty for no colour."""
    if not key:
        return ""
    return legend.get(key) or INK_NAMES.get(key) or DEFAULT_LEGEND.get(key, key)


def defuse_cell(value: str) -> str:
    """A spreadsheet runs a cell that starts with = + - @ as a formula: a leading apostrophe makes it plain text."""
    return "'" + value if value.startswith(_FORMULA_STARTS) else value


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Request ------------------------------------------------------------------------------------------------------------
def request_archive(user_id, *, client_id) -> tuple[ExportJob, bool]:
    """
    Queues the archive. A replayed `client_id`, or an archive that is still being built, returns that job (False: not new).
    """
    existing = ExportJob.objects.filter(user_id=user_id, client_id=client_id).first()
    if existing is not None:
        return existing, False
    running = ExportJob.objects.filter(user_id=user_id, kind="archive", status__in=["queued", "running"]).first()
    if running is not None:
        return running, False
    try:
        with transaction.atomic():
            job = ExportJob.objects.create(user_id=user_id, kind="archive", client_id=client_id, options={})
            core_jobs.enqueue(
                JOB_EXPORT_ARCHIVE, {"export_id": str(job.id)}, dedupe_key=f"{JOB_EXPORT_ARCHIVE}:{job.id}"
            )
    except IntegrityError:
        winner = ExportJob.objects.filter(user_id=user_id, client_id=client_id).first()
        if winner is None:
            raise
        return winner, False
    return job, True


# --- Worker -------------------------------------------------------------------------------------------------------------
def _progress(job_id, value: int) -> None:
    ExportJob.objects.filter(pk=job_id, status="running").update(progress=min(value, 95), updated_at=timezone.now())


def _write_notes(zf: zipfile.ZipFile, job: ExportJob, limit: int) -> int:
    count = 0
    for batch in export_selectors.note_cards(job.user_id, limit=limit):
        for card in batch:
            count += 1
            note = card.note
            head = front_matter(
                {
                    "title": note.title,
                    "chapter": card.link.chapter_name,
                    "subject": card.link.subject_name,
                    "tags": [t.name for t in card.tags],
                    "created": _iso(note.created_at),
                    "updated": _iso(note.updated_at),
                }
            )
            zf.writestr(f"notes/{count:04d}-{note_slug(note.title)}.md", head + "\n" + note.body_md + "\n")
        core_jobs.heartbeat()
        _progress(job.id, 5 + int(60 * count / max(limit, 1)))
    return count


def _digest_markdown(title: str, rows: list[list[str]]) -> str:
    out = [f"# {title or 'Untitled document'}\n"]
    for page, kind, colour, quote, comment, chapter, tags in rows:
        label = f"p. {page} · {kind}" + (f" · {colour}" if colour else "")
        out.append(f"- **{label}**" + (f" ({chapter})" if chapter else "") + (f" [{tags}]" if tags else ""))
        if quote:
            out.append("  > " + quote.replace("\n", "\n  > "))
        if comment:
            out.append("  " + comment.replace("\n", "\n  "))
    return "\n".join(out) + "\n"


def _write_digests(zf: zipfile.ZipFile, job: ExportJob, legend: dict) -> int:
    written = 0
    documents = Document.objects.filter(user_id=job.user_id, deleted_at__isnull=True).order_by("created_at", "id")
    for number, document in enumerate(documents.iterator(), start=1):
        rows: list[list[str]] = []
        for batch in export_selectors.mark_rows(job.user_id, document.id, DIGEST_KINDS):
            for item in batch:
                mark = item.mark
                rows.append(
                    [
                        str(mark.page),
                        mark.kind,
                        colour_name(mark.color, legend),
                        mark.quote_exact or "",
                        mark.comment or "",
                        item.link.chapter_name or "",
                        ", ".join(item.tags),
                    ]
                )
            core_jobs.heartbeat()
        if not rows:
            continue
        written += 1
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow([row[0], row[1], *(defuse_cell(cell) for cell in row[2:])])
        zf.writestr(f"documents/{number:03d}-digest.csv", buffer.getvalue())
        zf.writestr(f"documents/{number:03d}-digest.md", _digest_markdown(document.title, rows))
    return written


def _readme(notes: int, digests: int, built: datetime) -> str:
    lines = [
        "# Your notes from ArthaCommerce",
        "",
        f"Built on {built.astimezone(UTC):%d %B %Y}. Nothing here is shared with anyone.",
        "",
        f"- `notes/`: {notes} note(s) as Markdown. The block between the `---` lines at the top of each file is the "
        "title, chapter, subject, tags and the dates the note was created and last changed (UTC).",
    ]
    if digests:
        lines.append(
            f"- `documents/`: a digest of your highlights, notes and bookmarks for {digests} PDF(s), as Markdown to read "
            "and CSV to open in a spreadsheet. Colours carry the names you gave them in your legend."
        )
    lines += ["", "The PDFs themselves are not included; download them from your library."]
    return "\n".join(lines) + "\n"


def run_archive(export_id) -> dict:
    """The `notes.export_archive` handler body. Idempotent: anything but a queued or running archive is left alone."""
    job = ExportJob.objects.filter(pk=export_id, kind="archive").first()
    if job is None or job.status not in ("queued", "running"):
        return {"skipped": True}
    ExportJob.objects.filter(pk=job.pk).update(status="running", progress=2, updated_at=timezone.now())
    limit = quota.limits_for(job.user_id).max_notes
    legend = dict(
        Settings.objects.filter(pk=job.user_id).values_list("color_legend", flat=True).first() or DEFAULT_LEGEND
    )
    with_documents = flag_enabled(PDF_FLAG, job.user_id)
    built = timezone.now()
    with tempfile.TemporaryDirectory(prefix="archive-") as tmp:
        path = os.path.join(tmp, "notes.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            notes = _write_notes(zf, job, limit)
            digests = _write_digests(zf, job, legend) if with_documents else 0
            zf.writestr("README.md", _readme(notes, digests, built))
        _progress(job.id, 90)
        with open(path, "rb") as handle:
            attachment = media.store_generated(job.user_id, KIND, mime=ZIP_MIME, data=handle.read())
    finished = timezone.now()
    done = ExportJob.objects.filter(pk=job.pk, status="running").update(
        status="done",
        progress=100,
        attachment=attachment,
        error_code=None,
        expires_at=finished + timedelta(days=EXPORT_RETENTION_DAYS),
        updated_at=finished,
    )
    if not done:
        media.queue_delete([attachment.id])
        return {"skipped": True}
    events.announce_export_ready(job.user_id, job.id, kind="archive")
    return {"notes": notes, "documents": digests}


def give_up(export_id) -> dict:
    changed = ExportJob.objects.filter(pk=export_id, status__in=["queued", "running"]).update(
        status="failed", error_code="failed", updated_at=timezone.now()
    )
    return {"failed": bool(changed)}
