"""
End-to-end check of notes R2 over real HTTP: a Django server, the real worker (`run_worker --once`, real Tesseract and
pikepdf) and a fake Supabase Storage. Usage (from the repo root, with the API's virtualenv active and Postgres running):

    DATABASE_URL=postgres://... python scripts/e2e/notes-r2/run.py

It creates its own database objects under a throwaway user and prints one PASS/FAIL line per step. Exit code 1 on any failure.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

import httpx
import jwt
import pikepdf

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api"
sys.path.insert(0, str(API))
from modules.notes.tests.worker.fixtures import make_pdfs as mk  # noqa: E402

PORT_API, PORT_STORE = 18000, 54321
SECRET = "e2e-secret-e2e-secret-e2e-secret-32b"
TICK = "e2e-tick"
USER = str(uuid.uuid4())
ENV = {
    **os.environ,
    "DJANGO_SECRET_KEY": "e2e",
    "DJANGO_DEBUG": "true",
    "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
    "SUPABASE_URL": f"http://127.0.0.1:{PORT_STORE}",
    "SUPABASE_JWT_SECRET": SECRET,
    "SUPABASE_SERVICE_ROLE_KEY": "e2e-service-key",
    "POSTHOG_API_KEY": "",
    "NOTES_TICK_SECRET": TICK,
    "MEDIA_SCANNER": "null",
}
# The Noto fonts the export embeds live in the worker image; here use the test cache when the image path is absent.
_cache = Path.home() / ".cache" / "artha-test-fonts"
if "WORKER_FONTS_DIR" not in ENV and not Path("/usr/share/fonts/truetype/artha").is_dir() and _cache.is_dir():
    ENV["WORKER_FONTS_DIR"] = str(_cache)
failures: list[str] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    print(
        f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if not ok else ""),
        flush=True,
    )
    if not ok:
        failures.append(name)


def token() -> str:
    return jwt.encode(
        {
            "sub": USER,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
            "email": "e2e@example.com",
        },
        SECRET,
        algorithm="HS256",
    )


def worker() -> str:
    out = subprocess.run(
        [sys.executable, "manage.py", "run_worker", "--once", "--sleep", "0.2"],
        cwd=API,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if out.returncode != 0:
        print(out.stdout[-2000:], out.stderr[-2000:])
    return out.stdout + out.stderr


def wait_for(client: httpx.Client, doc_id: str, key: str, want: str, tries: int = 12) -> dict:
    body: dict = {}
    for _ in range(tries):
        worker()
        body = client.get(f"/notes/documents/{doc_id}/processing/").json()
        if body.get(key) == want:
            break
    return body


def upload(client: httpx.Client, data: bytes, name: str) -> str:
    res = client.post(
        "/notes/documents/",
        json={
            "client_id": str(uuid.uuid4()),
            "filename": name,
            "bytes": len(data),
            "mime": "application/pdf",
        },
    )
    check(f"reserve {name}", res.status_code == 201, res.text[:300])
    doc = res.json()["document"]
    up = res.json().get("upload") or doc.get("upload") or {}
    put = httpx.put(
        up["url"],
        content=data,
        headers={"content-type": "application/pdf", "authorization": "Bearer t"},
    )
    check(f"PUT {name} to the signed URL", put.status_code == 200, put.text[:200])
    done = client.post(f"/notes/documents/{doc['id']}/complete/")
    check(f"complete {name}", done.status_code == 200, done.text[:300])
    return doc["id"]


def start() -> tuple[list[subprocess.Popen], str]:
    """Starts the fake storage and the API server on a freshly migrated database. Returns the processes and the API base URL."""
    procs: list[subprocess.Popen] = [
        subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).parent / "fake_supabase.py"),
                str(PORT_STORE),
            ]
        )
    ]
    subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput", "-v", "0"],
        cwd=API,
        env=ENV,
        check=True,
    )
    procs.append(
        subprocess.Popen(
            [
                sys.executable,
                "manage.py",
                "runserver",
                f"127.0.0.1:{PORT_API}",
                "--noreload",
            ],
            cwd=API,
            env=ENV,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    )
    base = f"http://127.0.0.1:{PORT_API}/api/v1"
    for _ in range(60):
        try:
            httpx.get(f"{base}/notes/usage/", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.5)
    return procs, base


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    procs: list[subprocess.Popen] = []
    try:
        procs, base = start()
        client = httpx.Client(base_url=base, headers={"authorization": f"Bearer {token()}"}, timeout=60)

        # 1. A text PDF: upload, inspect, extract, search.
        text = mk.text_pdf(tmp / "text.pdf", 3).read_bytes()
        doc = upload(client, text, "GST notes.pdf")
        p = wait_for(client, doc, "text_status", "done")
        check(
            "text PDF is readable and searchable",
            p.get("status") == "ready" and p.get("page_count") == 3,
            p,
        )
        hits = client.get(f"/notes/documents/{doc}/search/", params={"q": "input tax credit"}).json()
        check(
            "in-document search finds all 3 pages",
            [h["page"] for h in hits.get("items", [])] == [1, 2, 3],
            hits,
        )
        shown = client.get(f"/notes/documents/{doc}/").json()
        check("the signed file URL serves a Range read", bool(shown.get("file_url")))
        part = httpx.get(shown["file_url"], headers={"range": "bytes=0-4"})
        check(
            "range read returns %PDF",
            part.status_code == 206 and part.content == b"%PDF-",
            part.status_code,
        )
        pg = client.get(f"/notes/documents/{doc}/pages/text/", params={"from": 1, "to": 2}).json()
        check(
            "page text comes back",
            len(pg.get("pages", [])) == 2 and "Input tax credit" in pg["pages"][0]["text"],
            pg,
        )

        # 2. Marks: create, edit, batch, delta feed, delete and restore.
        ann = str(uuid.uuid4())
        body = {
            "document_id": doc,
            "kind": "highlight",
            "page": 1,
            "color": "y",
            "comment": "check ITC rule",
            "quote_exact": "Input tax credit",
            "geometry": {"quads": [[0.1, 0.1, 0.3, 0.02]]},
            "device_id": "e2e-a",
        }
        r = client.put(f"/notes/annotations/{ann}/", json=body)
        check("create a highlight", r.status_code == 201, r.text[:300])
        rev = r.json()["annotation"]["rev"]
        r = client.put(
            f"/notes/annotations/{ann}/",
            json={**body, "color": "g", "base_rev": rev, "base": {"color": "y"}},
        )
        check(
            "edit its colour with a base revision",
            r.status_code == 200 and r.json()["annotation"]["color"] == "g",
            r.text[:300],
        )
        ink = str(uuid.uuid4())
        batch = client.post(
            "/notes/annotations/batch/",
            json={
                "document_id": doc,
                "ops": [
                    {
                        "op": "upsert",
                        **body,
                        "id": ink,
                        "kind": "sticky",
                        "geometry": {"pt": [0.5, 0.5]},
                        "comment": "ask sir",
                    },
                    {
                        "op": "upsert",
                        **body,
                        "id": str(uuid.uuid4()),
                        "kind": "underline",
                        "page": 2,
                    },
                ],
            },
        ).json()
        check(
            "a batch of two marks is accepted",
            [x["status"] for x in batch.get("results", [])] == ["ok", "ok"],
            batch,
        )
        feed = client.get(f"/notes/documents/{doc}/annotations/", params={"since_seq": 0}).json()
        check("the delta feed lists 3 marks", len(feed.get("items", [])) == 3, list(feed))
        check(
            "delete a mark",
            client.delete(f"/notes/annotations/{ink}/").status_code == 200,
        )
        check(
            "restore it",
            client.post(f"/notes/annotations/{ink}/restore/").status_code == 200,
        )
        agg = client.get("/notes/aggregate/", params={"type": "highlight"}).json()
        check("the aggregate view lists the marks", len(agg.get("items", [])) >= 2, agg)
        card = client.post(f"/notes/annotations/{ann}/card/", json={"client_id": str(uuid.uuid4())})
        check(
            "recall card is 503 recall_unavailable with no provider",
            card.status_code == 503,
            card.text[:200],
        )

        # 3. Export the marked PDF and check the real file.
        ex = client.post(
            f"/notes/documents/{doc}/exports/",
            json={"client_id": str(uuid.uuid4()), "options": {"appendix": True}},
        )
        check("export accepted", ex.status_code == 202, ex.text[:300])
        eid = ex.json()["export"]["id"]
        job = {}
        for _ in range(8):
            worker()
            job = client.get(f"/notes/exports/{eid}/").json()
            if job.get("status") in ("done", "failed"):
                break
        check("export finished", job.get("status") == "done", job)
        if job.get("download_url"):
            pdf = httpx.get(job["download_url"]).content
            with (
                pikepdf.open(io.BytesIO(pdf)) as f,
                pikepdf.open(io.BytesIO(text)) as orig,
            ):

                def size(page) -> int:
                    contents = page.obj.get("/Contents")
                    streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
                    return sum(len(c.read_bytes()) for c in streams)

                check(
                    "export burns the marks into pages 1 and 2 (flattened)",
                    size(f.pages[0]) > size(orig.pages[0])
                    and size(f.pages[1]) > size(orig.pages[1])
                    and size(f.pages[2]) == size(orig.pages[2]),
                    [size(p) for p in f.pages],
                )
                check("export appends an appendix page", len(f.pages) == 4, len(f.pages))
            import pypdfium2

            appendix = pypdfium2.PdfDocument(pdf)[3].get_textpage().get_text_range()
            check(
                "the appendix lists the comment",
                "check ITC rule" in appendix,
                appendix[:200],
            )

        # 4. A scanned PDF: Tesseract through the worker, then search the OCR text.
        scan = mk.scanned_pdf(tmp / "scan.pdf", 2).read_bytes()
        sdoc = upload(client, scan, "scan.pdf")
        wait_for(client, sdoc, "status", "ready")
        s = client.get(f"/notes/documents/{sdoc}/processing/").json()
        check("scanned PDF is detected as scanned", s.get("is_scanned") is True, s)
        o = client.post(f"/notes/documents/{sdoc}/ocr/", json={"mode": "tesseract", "lang": "eng"})
        check(
            "OCR request accepted and charged",
            o.status_code == 202 and o.json()["charged_pages"] == 2,
            o.text[:300],
        )
        s = wait_for(client, sdoc, "ocr_status", "done", tries=20)
        check("OCR finished", s.get("ocr_status") == "done", s)
        hits = client.get(f"/notes/documents/{sdoc}/search/", params={"q": "goods and services"}).json()
        check("OCR text is searchable", len(hits.get("items", [])) >= 1, hits)
        usage = client.get("/notes/usage/").json()
        check(
            "usage shows 2 OCR pages and 1 export",
            usage["used"]["ocr_pages"] == 2 and usage["used"]["exports"] == 1,
            usage["used"],
        )

        # 5. Library-wide search, archive, tick, trash and flags.
        lib = client.get("/notes/search/", params={"q": "tax", "scope": "all"})
        check("library search answers", lib.status_code == 200, lib.text[:200])
        ar = client.post("/notes/export/archive/", json={"client_id": str(uuid.uuid4())})
        check("archive accepted", ar.status_code == 202, ar.text[:200])
        aid = ar.json()["export"]["id"]
        for _ in range(8):
            worker()
            a = client.get(f"/notes/exports/{aid}/").json()
            if a.get("status") in ("done", "failed"):
                break
        check("archive done", a.get("status") == "done", a)
        if a.get("download_url"):
            names = zipfile.ZipFile(io.BytesIO(httpx.get(a["download_url"]).content)).namelist()
            check(
                "archive holds a digest per document",
                any(n.endswith(".csv") for n in names),
                names[:8],
            )
        t = httpx.post(f"{base}/notes/internal/tick/", headers={"X-Notes-Tick-Secret": TICK})
        check("tick with the secret works", t.status_code == 200, t.text[:200])
        t = httpx.post(f"{base}/notes/internal/tick/")
        check(
            "tick without the secret is refused",
            t.status_code in (401, 403),
            t.status_code,
        )
        check(
            "trash a document",
            client.delete(f"/notes/documents/{sdoc}/").status_code in (200, 204),
        )
        check(
            "restore it",
            client.post(f"/notes/documents/{sdoc}/restore/").status_code == 200,
        )
        check(
            "export of everything stays open",
            client.get("/notes/export/").status_code == 200,
        )
        check(
            "delete all removes the student's notes",
            client.delete("/notes/").status_code in (200, 204),
        )
        left = httpx.get(f"http://127.0.0.1:{PORT_STORE}/__objects").json()
        worker()  # queued storage deletes
        left2 = httpx.get(f"http://127.0.0.1:{PORT_STORE}/__objects").json()
        check(
            "stored files are removed after delete all",
            len(left2) < len(left) or not left2,
            (len(left), len(left2)),
        )
    finally:
        for p in procs:
            p.terminate()
    print(f"\n{'ALL PASSED' if not failures else f'{len(failures)} FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
