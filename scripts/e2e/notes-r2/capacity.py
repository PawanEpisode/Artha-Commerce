"""
Indicative capacity numbers on this machine (see the capacity runbook in docs/F-03-ROLLOUT.md): a 1,000-page PDF through the
worker, a file near the 50 MB limit, in-document and library search latency (p50/p95) and a concurrent write load on one
document. Same stack as `run.py` (Django dev server, fake storage, real worker). The numbers are a baseline for comparing
runs, not a production forecast: the dev server, one CPU and a local database are kinder or harsher than the real host.

    DATABASE_URL=postgres://... python scripts/e2e/notes-r2/capacity.py
"""

from __future__ import annotations

import os
import statistics
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pikepdf

import run


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


def line(name: str, value: str) -> None:
    print(f"{name:<52}{value}", flush=True)


def big_pdf(path: Path, megabytes: int) -> bytes:
    """A valid one-page PDF padded with an unused random stream to about `megabytes`."""
    with pikepdf.new() as pdf:
        page = pdf.add_blank_page(page_size=(595, 842))
        page.obj["/Padding"] = pdf.make_stream(os.urandom(megabytes * 1024 * 1024))
        pdf.save(path)
    return path.read_bytes()


def timed_upload(client: httpx.Client, data: bytes, name: str) -> tuple[str, float]:
    start = time.monotonic()
    doc = run.upload(client, data, name)
    return doc, time.monotonic() - start


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    procs, base = run.start()
    try:
        client = httpx.Client(base_url=base, headers={"authorization": f"Bearer {run.token()}"}, timeout=120)

        # 1. A 1,000-page PDF: upload, inspect, extract every page.
        pdf = run.mk.many_pages_pdf(tmp / "big.pdf", 1000).read_bytes()
        line("1,000-page PDF size", f"{len(pdf) / 1e6:.1f} MB")
        doc, up = timed_upload(client, pdf, "thousand.pdf")
        t0 = time.monotonic()
        run.wait_for(client, doc, "status", "ready", tries=6)
        inspected = time.monotonic() - t0
        state = run.wait_for(client, doc, "text_status", "done", tries=20)
        total = time.monotonic() - t0
        line("  upload (reserve, PUT, complete)", f"{up:.1f} s")
        line("  inspect, then readable", f"{inspected:.1f} s")
        line(
            "  every page searchable",
            f"{total:.1f} s  ({state.get('text_pages_done')}/{state.get('page_count')} pages)",
        )

        # 2. A file near the 50 MB limit.
        data = big_pdf(tmp / "fifty.pdf", 48)
        line("large PDF size", f"{len(data) / 1e6:.1f} MB")
        fdoc, up = timed_upload(client, data, "fifty.pdf")
        t0 = time.monotonic()
        s = run.wait_for(client, fdoc, "status", "ready", tries=8)
        line("  upload", f"{up:.1f} s")
        line("  inspect to ready", f"{time.monotonic() - t0:.1f} s  (status {s.get('status')})")
        part = httpx.get(client.get(f"/notes/documents/{fdoc}/").json()["file_url"], headers={"range": "bytes=0-1023"})
        line("  first-kilobyte range read", f"{part.status_code}, {len(part.content)} bytes")

        # 3. Search latency (single caller, sequential).
        words = ["lorem", "ipsum dolor", "page 500", "row 7", "amet"]
        in_doc = []
        for i in range(50):
            t = time.monotonic()
            r = client.get(f"/notes/documents/{doc}/search/", params={"q": words[i % 5]})
            in_doc.append((time.monotonic() - t) * 1000)
            assert r.status_code == 200, r.status_code
        line(
            "in-document search, 1,000 pages (50 calls)", f"p50 {pct(in_doc, 50):.0f} ms  p95 {pct(in_doc, 95):.0f} ms"
        )
        time.sleep(
            62
        )  # the search throttle is 60 a minute per student: part of what is being checked, not worked around
        lib = []
        for i in range(50):
            t = time.monotonic()
            r = client.get("/notes/search/", params={"q": words[i % 5], "scope": "pdf"})
            lib.append((time.monotonic() - t) * 1000)
            assert r.status_code == 200, r.status_code
        line("library PDF search (50 calls)", f"p50 {pct(lib, 50):.0f} ms  p95 {pct(lib, 95):.0f} ms")

        # 4. Write load: 8 writers send batches of 25 marks to one document; the sequence must stay gap free.
        def writer(n: int) -> tuple[float, int]:
            c = httpx.Client(base_url=base, headers={"authorization": f"Bearer {run.token()}"}, timeout=120)
            ops = [
                {
                    "op": "upsert",
                    "id": str(uuid.uuid4()),
                    "document_id": doc,
                    "kind": "highlight",
                    "page": 1 + (n * 25 + i) % 1000,
                    "color": "y",
                    "quote_exact": "lorem ipsum",
                    "geometry": {"quads": [[0.1, 0.1, 0.3, 0.02]]},
                    "device_id": f"load-{n}",
                }
                for i in range(25)
            ]
            t = time.monotonic()
            res = c.post("/notes/annotations/batch/", json={"document_id": doc, "ops": ops}).json()
            return (time.monotonic() - t) * 1000, sum(r["status"] == "ok" for r in res["results"])

        t0 = time.monotonic()
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(writer, range(8)))
        wall = time.monotonic() - t0
        lat = [r[0] for r in results]
        line("write load: 8 writers x 25 marks", f"{sum(r[1] for r in results)}/200 ok in {wall:.1f} s")
        line("  batch latency", f"p50 {statistics.median(lat):.0f} ms  max {max(lat):.0f} ms")
        feed = client.get(f"/notes/documents/{doc}/annotations/", params={"since_seq": 0, "limit": 500}).json()
        seqs = sorted(a["seq"] for a in feed["items"])
        line("  change_seq is gap free", str(seqs == list(range(1, len(seqs) + 1))))
        usage = client.get("/notes/usage/").json()
        line(
            "usage after the run",
            f"{usage['used']['documents']} documents, {usage['used']['storage_bytes'] / 1e6:.0f} MB",
        )
        print(
            "\nNot measured here (manual, see the runbook): real devices, a production host with gunicorn, Render worker memory\n"
            "under a real 50 MB scan, OCR of a scanned 1,000-page file, ClamAV scan time."
        )
    finally:
        for p in procs:
            p.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
