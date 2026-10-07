"""'Download my notes': the zip's listing, front matter, digests, privacy and speed."""
# ruff: noqa: F811 - pytest fixtures imported from `ocr_export_support` are redefined as test arguments

import csv
import io
import json
import time
import uuid
import zipfile

import pytest
from django.utils import timezone

from core import events as bus
from modules.coverage.tests.conftest import OTHER, USER
from modules.notes import events
from modules.notes.models import Annotation, ExportJob, ItemTag, Note, QuotaPlan
from modules.notes.services import archive, links
from modules.syllabus.models import Chapter

from .factories import make_annotation, make_attachment, make_document, make_note, make_tag
from .ocr_export_support import fake_storage, run_jobs  # noqa: F401

pytestmark = pytest.mark.django_db
TYPES = ["notes.export_archive"]


# --- Pure ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Input Tax Credit: Section 17(5)", "input-tax-credit-section-175"),
        ("", "note"),
        ("   ", "note"),
        ("आयकर", "note"),  # nothing ASCII left
        ("../../etc/passwd", "etcpasswd"),
        ("CON  /  NUL?*", "con-nul"),
        ("x" * 200, "x" * 40),
        ("a" * 39 + " b" * 5, "a" * 39),
    ],
)
def test_the_slug_is_ascii_short_and_never_a_path(title, slug):
    assert archive.note_slug(title) == slug


def test_front_matter_is_valid_yaml_for_any_text():
    block = archive.front_matter(
        {"title": 'He said "hi"\nand: left', "chapter": None, "tags": ["a", "b: c"], "n": "---"}
    )
    lines = block.splitlines()
    assert lines[0] == lines[-1] == "---"
    assert json.loads(lines[1].split(": ", 1)[1]) == 'He said "hi"\nand: left'  # one line, escaped
    assert lines[2] == "chapter: null" and json.loads(lines[3].split(": ", 1)[1]) == ["a", "b: c"]
    assert len(lines) == 6  # a newline in a value never adds a line that could close the block


def test_colour_names_come_from_the_students_legend():
    legend = {"y": "Important", "g": "My formulas"}
    assert archive.colour_name("g", legend) == "My formulas"
    assert archive.colour_name("i2", legend) == "Red pen"
    assert (
        archive.colour_name("b", legend) == "Section or rule"
    )  # a legend that lacks a key falls back to the default name
    assert archive.colour_name(None, legend) == ""


@pytest.mark.parametrize(
    ("cell", "safe"),
    [("=SUM(A1)", "'=SUM(A1)"), ("+1", "'+1"), ("-1", "'-1"), ("@x", "'@x"), ("fine", "fine"), ("", "")],
)
def test_spreadsheet_formulas_are_defused(cell, safe):
    assert archive.defuse_cell(cell) == safe


# --- The zip ------------------------------------------------------------------------------------------------------------
@pytest.fixture
def chapter(scheme):
    return Chapter.objects.get(key="gst-itc")


def build(api, user=USER):
    job = api.post("/notes/export/archive/", {"client_id": str(uuid.uuid4())}).json_body["export"]
    run_jobs(TYPES)
    return job["id"]


def open_zip(fake, job_id) -> zipfile.ZipFile:
    attachment = ExportJob.objects.get(pk=job_id).attachment
    assert attachment.kind == "note_export" and attachment.mime == "application/zip"
    assert attachment.path == f"{attachment.user_id}/exports/{attachment.id}.zip"
    return zipfile.ZipFile(io.BytesIO(fake.objects[(attachment.bucket, attachment.path)]))


def test_the_zip_holds_notes_digests_and_a_readme_and_nothing_else(api, chapter, fake_storage):
    link = links.link_columns(chapter.id, None)
    one = make_note(USER, title="Input Tax Credit", body_md="# ITC\n\nBlocked credits **17(5)**.", **link)
    make_note(USER, title="Input Tax Credit", body_md="same title, second note")
    make_note(USER, title="आयकर", body_md="Hindi title")
    make_note(USER, title="Trashed", body_md="gone", deleted_at=timezone.now(), purge_after=timezone.now())
    make_note(OTHER, title="Someone else", body_md="not mine")
    tag = make_tag(USER, "revise")
    ItemTag.objects.create(user_id=USER, tag=tag, note=one)
    legend = {"y": "Must know", "g": "Formula", "b": "Section or rule", "p": "Doubt", "o": "Example"}
    api.put("/notes/settings/", {"color_legend": legend})
    doc = make_document(USER, title="GST Study Material", attachment=make_attachment(USER), **link)
    doc.original_filename = "secret-coaching-notes-final.pdf"
    doc.save()
    hl = make_annotation(
        doc, page=3, kind="highlight", color="y", quote_exact="Credit is blocked", comment="check", **link
    )
    make_annotation(
        doc, page=1, kind="sticky", color="g", comment='=HYPERLINK("http://x")', geometry={"pt": [0.5, 0.5]}
    )
    make_annotation(doc, page=2, kind="ink", color="i2", geometry={"strokes": []})  # drawings are not in a digest
    make_annotation(doc, page=1, kind="bookmark", color=None, comment="start here", geometry={"y": 0.1})
    make_annotation(doc, page=1, kind="highlight", color="b", quote_exact="deleted", deleted_at=timezone.now())
    ItemTag.objects.create(user_id=USER, tag=tag, annotation=hl)
    make_document(USER, title="No marks at all", attachment=make_attachment(USER))
    make_document(OTHER, title="Theirs", attachment=make_attachment(OTHER))

    seen = []
    bus.subscribe(events.NOTES_EXPORT_READY, lambda **p: seen.append(p))
    try:
        job_id = build(api)
    finally:
        bus.clear()
    zf = open_zip(fake_storage, job_id)
    names = zf.namelist()
    assert names[0].startswith("notes/") and names[-1] == "README.md"
    assert sorted(n for n in names if n.startswith("notes/")) == [
        "notes/0001-input-tax-credit.md",
        "notes/0002-input-tax-credit.md",
        "notes/0003-note.md",
    ]  # same title twice and a title with no ASCII: unique names from the counter
    assert sorted(n for n in names if n.startswith("documents/")) == [
        "documents/001-digest.csv",
        "documents/001-digest.md",
    ]
    assert len(names) == 6
    blob = " ".join(names) + "".join(zf.read(n).decode() for n in names)
    assert "secret-coaching" not in blob and ".pdf" not in blob  # no uploaded file name anywhere
    assert "Trashed" not in blob and "Someone else" not in blob and "Theirs" not in blob and "deleted" not in blob

    first = zf.read("notes/0001-input-tax-credit.md").decode()
    head, body = first.split("---\n", 2)[1], first.split("---\n", 2)[2]
    fields = {k: json.loads(v) for k, v in (line.split(": ", 1) for line in head.splitlines())}
    assert fields["title"] == "Input Tax Credit" and fields["tags"] == ["revise"]
    assert fields["chapter"] == chapter.name and fields["subject"] and fields["created"].endswith("Z")
    assert set(fields) == {"title", "chapter", "subject", "tags", "created", "updated"}
    assert body == "\n# ITC\n\nBlocked credits **17(5)**.\n"  # the body as it was written
    unfiled = zf.read("notes/0002-input-tax-credit.md").decode()
    assert "chapter: null" in unfiled and "tags: []" in unfiled

    rows = list(csv.reader(io.StringIO(zf.read("documents/001-digest.csv").decode())))
    assert rows[0] == ["page", "kind", "colour", "quote", "comment", "chapter", "tags"]
    assert rows[1:] == [
        ["1", "sticky", "Formula", "", '\'=HYPERLINK("http://x")', "", ""],
        ["1", "bookmark", "", "", "start here", "", ""],
        ["3", "highlight", "Must know", "Credit is blocked", "check", chapter.name, "revise"],
    ]
    digest = zf.read("documents/001-digest.md").decode()
    assert digest.startswith("# GST Study Material") and "Must know" in digest and "> Credit is blocked" in digest
    readme = zf.read("README.md").decode()
    assert "3 note(s)" in readme and "1 PDF(s)" in readme

    done = api.get(f"/notes/exports/{job_id}/").json_body
    assert (done["status"], done["kind"], done["document_id"], done["page_count"]) == ("done", "archive", None, None)
    assert done["download_url"] and done["progress"] == 100
    assert seen == [{"user_id": USER, "export_id": job_id, "kind": "archive", "document_id": None, "page_count": None}]


def test_without_the_pdf_flag_the_zip_has_notes_only(api, fake_storage, monkeypatch):
    from django.conf import settings

    from core import feature_flags

    class Off:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return False if key == "notes_pdf" else None

    make_note(USER, title="Only a note", body_md="text")
    doc = make_document(USER, attachment=make_attachment(USER))
    make_annotation(doc, quote_exact="a quote")
    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", Off())
    feature_flags.clear_flag_cache()
    try:
        job_id = build(api)
    finally:
        feature_flags.clear_flag_cache()
    names = open_zip(fake_storage, job_id).namelist()
    assert names == ["notes/0001-only-a-note.md", "README.md"]
    assert "PDF(s)" not in open_zip(fake_storage, job_id).read("README.md").decode()


def test_an_empty_account_still_gets_a_valid_zip(api, fake_storage):
    zf = open_zip(fake_storage, build(api))
    assert zf.namelist() == ["README.md"] and zf.testzip() is None
    assert "0 note(s)" in zf.read("README.md").decode()


def test_at_most_the_plans_note_count_goes_in(api, fake_storage):
    QuotaPlan.objects.filter(pk="free").update(max_notes=3)
    for n in range(5):
        make_note(USER, title=f"Note {n}", body_md=str(n))
    names = open_zip(fake_storage, build(api)).namelist()
    assert [n for n in names if n.startswith("notes/")] == [
        "notes/0001-note-0.md",
        "notes/0002-note-1.md",
        "notes/0003-note-2.md",
    ]


def test_the_job_is_idempotent_and_a_failure_ends_failed_without_a_charge(api, fake_storage, monkeypatch):
    from core import jobs
    from modules.notes.services import objects  # noqa: F401

    make_note(USER, title="x", body_md="y")
    job_id = build(api)
    attachment_id = ExportJob.objects.get(pk=job_id).attachment_id
    jobs.enqueue("notes.export_archive", {"export_id": job_id}, dedupe_key="again")
    run_jobs(TYPES)
    assert ExportJob.objects.get(pk=job_id).attachment_id == attachment_id
    # a build that cannot finish: retried, then failed on the last attempt
    monkeypatch.setattr(archive, "_write_notes", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk")))
    again = api.post("/notes/export/archive/", {"client_id": str(uuid.uuid4())}).json_body["export"]["id"]
    from core.models import Job

    for _ in range(5):
        Job.objects.filter(status="queued").update(run_after=timezone.now())
        run_jobs(TYPES, limit=1)
    failed = api.get(f"/notes/exports/{again}/").json_body
    assert (failed["status"], failed["error_code"], failed["download_url"]) == ("failed", "failed", None)


def test_500_notes_and_5000_marks_are_ready_in_well_under_a_minute(api, fake_storage):
    Note.objects.bulk_create(
        Note(
            user_id=USER,
            client_id=uuid.uuid4(),
            title=f"Note {n}",
            body_md="Some **markdown** text. " * 40,
            body_text="x",
        )
        for n in range(500)
    )
    docs = [make_document(USER, title=f"Doc {n}", attachment=make_attachment(USER)) for n in range(5)]
    Annotation.objects.bulk_create(
        Annotation(
            user_id=USER,
            document=docs[n % 5],
            page=n % 90 + 1,
            kind="highlight",
            color="yg"[n % 2],
            seq=1,
            geometry={"quads": [[0.1, 0.1, 0.2, 0.02]]},
            quote_exact=f"quote {n}",
            comment=f"comment {n}",
        )
        for n in range(5000)
    )
    started = time.monotonic()
    job_id = build(api)
    elapsed = time.monotonic() - started
    zf = open_zip(fake_storage, job_id)
    assert sum(n.startswith("notes/") for n in zf.namelist()) == 500
    rows = sum(len(list(csv.reader(io.StringIO(zf.read(n).decode())))) - 1 for n in zf.namelist() if n.endswith(".csv"))
    assert rows == 5000
    assert elapsed < 60, f"{elapsed:.1f}s"
    assert elapsed < 20  # an order of magnitude of headroom on the 60 s promise
