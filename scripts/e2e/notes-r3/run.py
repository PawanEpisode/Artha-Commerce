"""
End-to-end check of notes R3 over real HTTP: Replace edition (marks follow a newer PDF) and Unlock for search (a locked PDF's text
becomes searchable, and the password is gone from the queue afterwards), with a Django server, the real worker and a fake
Supabase Storage. Gemini is not involved (AI summary and page reading are covered by the unit tests with a scripted model).
Usage, from the repo root with the API's virtualenv active:

    python scripts/e2e/notes-r3/run.py

Needs `reportlab`, `pikepdf` and `pypdfium2` (the worker requirements). Exit code 1 on any failure.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("notes_r2_e2e", HERE.parent / "notes-r2" / "run.py")
r2 = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(r2)  # type: ignore[union-attr]

r2.ENV["NOTES_UNLOCK_FERNET_KEYS"] = Fernet.generate_key().decode()
r2.PORT_API = 18100
LINE_A = "Input tax credit under GST is available on inward supplies used for business."
LINE_B = "Place of supply decides whether IGST or CGST and SGST are charged on the sale."
check = r2.check


def pdf(path: Path, pages: list[list[str]]) -> bytes:
    c = canvas.Canvas(str(path), pagesize=A4)
    for lines in pages:
        c.setFont("Helvetica", 14)
        for i, line in enumerate(lines):
            c.drawString(72, 760 - 40 * i, line)
        c.showPage()
    c.save()
    return path.read_bytes()


def serve(procs: list[subprocess.Popen]) -> str:
    procs.append(subprocess.Popen([sys.executable, str(HERE.parent / "notes-r2" / "fake_supabase.py"), str(r2.PORT_STORE)]))
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput", "-v", "0"], cwd=r2.API, env=r2.ENV, check=True)
    procs.append(
        subprocess.Popen(
            [sys.executable, str(HERE / "serve.py"), f"127.0.0.1:{r2.PORT_API}"],
            cwd=r2.API,
            env=r2.ENV,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    )
    base = f"http://127.0.0.1:{r2.PORT_API}/api/v1"
    for _ in range(60):
        try:
            httpx.get(f"{base}/notes/usage/", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.5)
    return base


def put_file(client: httpx.Client, url: str, data: bytes, name: str, doc_id: str, upload: dict) -> None:
    put = httpx.put(upload["url"], content=data, headers={"content-type": "application/pdf", "authorization": "Bearer t"})
    check(f"PUT {name}", put.status_code == 200, put.text[:200])
    check(f"complete {name}", client.post(f"/notes/documents/{doc_id}/complete/").status_code == 200)


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    procs: list[subprocess.Popen] = []
    try:
        base = serve(procs)
        client = httpx.Client(base_url=base, headers={"authorization": f"Bearer {r2.token()}"}, timeout=60)

        # 1. Replace edition: the old edition has a highlight and a sticky note; the new one starts with a new page.
        old_id = r2.upload(client, pdf(tmp / "old.pdf", [[LINE_A], [LINE_B], ["Closing remarks."]]), "GST 2025.pdf")
        r2.wait_for(client, old_id, "text_status", "done")
        high = str(uuid.uuid4())
        res = client.put(
            f"/notes/annotations/{high}/",
            json={
                "document_id": old_id,
                "kind": "highlight",
                "page": 1,
                "color": "y",
                "geometry": {"quads": [[0.1, 0.1, 0.3, 0.02]]},
                "quote_exact": "tax credit under GST",
                "comment": "exam favourite",
            },
        )
        check("highlight on the old edition", res.status_code == 201, res.text[:300])
        sticky = str(uuid.uuid4())
        res = client.put(
            f"/notes/annotations/{sticky}/",
            json={
                "document_id": old_id,
                "kind": "sticky",
                "page": 1,
                "color": "y",
                "geometry": {"pt": [0.5, 0.5]},
                "comment": "ask sir",
            },
        )
        check("sticky on the old edition", res.status_code == 201, res.text[:300])

        new_bytes = pdf(tmp / "new.pdf", [["Preface of the new edition."], [LINE_A], [LINE_B], ["Closing remarks."]])
        rep = client.post(
            f"/notes/documents/{old_id}/replace/",
            json={
                "client_id": str(uuid.uuid4()),
                "filename": "GST 2026.pdf",
                "bytes": len(new_bytes),
                "mime": "application/pdf",
                "edition_label": "2026",
            },
        )
        check("replace reserves a newer edition", rep.status_code == 201, rep.text[:300])
        new_id = rep.json()["document"]["id"]
        put_file(client, "", new_bytes, "GST 2026.pdf", new_id, rep.json()["upload"])
        for _ in range(10):
            r2.worker()
            att = client.get(f"/notes/documents/{new_id}/attention/").json()
            if att.get("status") == "done":
                break
        check("marks were carried over", att.get("status") == "done" and att["stats"]["moved"] == 1, att)
        check("the sticky waits for the student", att["stats"]["needs_attention"] == 1 and len(att["items"]) == 1, att)
        marks = client.get(f"/notes/documents/{new_id}/annotations/", params={"since_seq": 0}).json()
        moved = [m for m in marks.get("items", marks.get("annotations", [])) if m["kind"] == "highlight"]
        check("the highlight is on page 2 of the new edition", bool(moved) and moved[0]["page"] == 2, marks)
        item = att["items"][0]["id"]
        kept = client.post(f"/notes/documents/{new_id}/attention/{item}/", json={"action": "note"})
        check("the sticky is saved as a note", kept.status_code == 200 and kept.json()["status"] == "noted", kept.text[:200])
        old_marks = client.get(f"/notes/documents/{old_id}/annotations/", params={"since_seq": 0}).json()
        check("the old edition keeps its marks", len(old_marks.get("items", old_marks.get("annotations", []))) == 2)

        # 2. Unlock for search: a PDF with a user password is accepted, then readable by its password, which is never kept.
        plain = tmp / "plain.pdf"
        pdf(plain, [[LINE_A], [LINE_B]])
        import pikepdf

        locked = tmp / "locked.pdf"
        with pikepdf.open(plain) as src:
            src.save(locked, encryption=pikepdf.Encryption(user="s3cret", owner="owner"))
        lid = r2.upload(client, locked.read_bytes(), "Locked notes.pdf")
        for _ in range(6):
            r2.worker()
            doc = client.get(f"/notes/documents/{lid}/").json()
            if doc["status"] == "needs_password":
                break
        check("the locked PDF waits for its password", doc["status"] == "needs_password", doc["status"])
        wrong = client.post(f"/notes/documents/{lid}/unlock/", json={"password": "nope"})
        check("a wrong password is accepted for trying", wrong.status_code == 202, wrong.text[:200])
        r2.worker()
        doc = client.get(f"/notes/documents/{lid}/").json()
        check("and reported as wrong", doc["unlock_status"] == "failed" and doc["unlock_reason"] == "wrong_password", doc)
        right = client.post(f"/notes/documents/{lid}/unlock/", json={"password": "s3cret"})
        check("the right password is queued", right.status_code == 202, right.text[:200])
        for _ in range(6):
            r2.worker()
            doc = client.get(f"/notes/documents/{lid}/").json()
            if doc["unlock_status"] == "done":
                break
        check("the PDF is readable and unlocked", doc["status"] == "ready" and doc["unlock_status"] == "done", doc)
        hits = client.get(f"/notes/documents/{lid}/search/", params={"q": "place of supply"}).json()
        check("its text is searchable", [h["page"] for h in hits.get("items", [])] == [2], hits)
        library = client.get("/notes/search/", params={"q": "place of supply", "scope": "pdf"}).json()
        check("the library search finds it too", bool(library), library)
    finally:
        for p in procs:
            p.terminate()
    print(f"\n{'ALL PASSED' if not r2.failures else f'{len(r2.failures)} FAILED: ' + ', '.join(r2.failures)}")
    return 1 if r2.failures else 0


if __name__ == "__main__":
    sys.exit(main())
