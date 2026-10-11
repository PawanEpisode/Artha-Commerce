"""
Indicative capacity numbers for the recall R2 paths (see "Capacity note" in docs/F-15-ROLLOUT.md): the same machine, stack and
method as `scripts/e2e/recall-r1/capacity.py`, for what R2 added. Today and queue for a student with an exam 40 days away, the
quick revision plan and queue, the pack and a batch of 100 (the bulk path), one review with the exam horizon applied, then the
same endpoints with every reviewer at once. Targets come from PRD section 12; the quick plan is held to the queue's 300 ms.

    DATABASE_URL=postgres://... python scripts/e2e/recall-r2/capacity.py [--cards 5000] [--reviewers 8] [--strict] [--debug]

Students are bulk inserted, enrolled with an exam date and erased at the end. No card text is printed.
"""

from __future__ import annotations

import argparse
import gzip
import os
import platform
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "recall-r1"))
import capacity as base_capacity  # noqa: E402
import run  # noqa: E402

pct, line, client_for, timed = base_capacity.pct, base_capacity.line, base_capacity.client_for, base_capacity.timed
TARGETS_MS = {
    "queue": 300,
    "today": 300,
    "quick plan": 300,
    "quick queue": 300,
    "review": 200,
    "batch of 100": 800,
    "pack of 300": 500,
}


def seed_students(users: list[str], cards: int) -> None:
    """Cards as in R1, linked to the CMA scheme, and an enrolment with an exam 40 days out."""
    os.environ.update(run.ENV)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(run.API))
    import django

    django.setup()
    from modules.coverage.models import Enrollment
    from modules.recall.models import RecallItem
    from modules.recall.tests.w6 import library
    from modules.syllabus.models import Scheme

    scheme = Scheme.objects.filter(level__course__code="cma", level__code="final", status="published").first()
    for user in users:
        uid = uuid.UUID(user)
        library(cards, user=uid, chapter_id=None)
        RecallItem.objects.filter(owner_user_id=uid).update(scheme_id=scheme.id)
        Enrollment.objects.create(
            user_id=uid, scheme=scheme, level=scheme.level, exam_date=(datetime.now(UTC) + timedelta(days=40)).date()
        )


def reader(base: str, user: str, rounds: int) -> dict:
    c = client_for(base, user)
    out: dict = {"today": [], "plan": [], "quick": [], "failed": 0}
    for _ in range(rounds):
        for key, url, params in (
            ("today", "/recall/today/", None),
            ("plan", "/recall/quick-revision/plan/", {"minutes": 20}),
            ("quick", "/recall/queue/", {"source": "quick", "limit": 20}),
        ):
            ms, r = timed(c, "GET", url, params=params)
            out[key].append(ms)
            if r.status_code != 200:
                out["failed"] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", type=int, default=5000)
    ap.add_argument("--reviewers", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    run.ENV["DJANGO_DEBUG"] = "true" if args.debug else "false"
    users = [str(uuid.uuid4()) for _ in range(args.reviewers)]
    procs, base = run.start()
    missed: list[str] = []
    try:
        with run.pg() as conn:
            pgv = conn.execute("SHOW server_version").fetchone()[0]
        line(
            "machine",
            f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, Python {platform.python_version()}",
        )
        line("database", f"PostgreSQL {pgv} on the same machine; API: Django dev server (one process, threaded)")
        t0 = time.perf_counter()
        seed_students(users, args.cards)
        line("students and cards seeded", f"{args.reviewers} x {args.cards} in {time.perf_counter() - t0:.0f} s")

        c = client_for(base, users[0])
        today = [timed(c, "GET", "/recall/today/")[0] for _ in range(30)]
        plan = [timed(c, "GET", "/recall/quick-revision/plan/", params={"minutes": 20})[0] for _ in range(30)]
        quick = [timed(c, "GET", "/recall/queue/", params={"source": "quick", "limit": 20})[0] for _ in range(30)]
        queue = [timed(c, "GET", "/recall/queue/", params={"limit": 20})[0] for _ in range(30)]
        packs, sizes = [], []
        for _ in range(10):
            ms, r = timed(c, "GET", "/recall/pack/", params={"limit": 300})
            packs.append(ms)
            sizes.append(len(gzip.compress(r.content)) / 1024)
        ids: list[str] = []
        cursor = None
        while len(ids) < 520:
            page = c.get("/recall/cards/", params={"limit": 100, **({"cursor": cursor} if cursor else {})}).json()
            ids += [x["id"] for x in page["items"]]
            cursor = page.get("next_cursor")
            if not cursor:
                break
        batches = []
        for k in range(4):
            events = [run.event(i, 3, datetime.now(UTC), "capacity") for i in ids[k * 100 : k * 100 + 100]]
            ms, r = timed(c, "POST", "/recall/reviews/batch/", json={"events": events})
            batches.append(ms if r.status_code == 200 else float("inf"))
        singles = [
            timed(c, "POST", "/recall/reviews/", json=run.event(i, 3, datetime.now(UTC), "capacity"))[0]
            for i in ids[400:440]
        ]
        line("\nOne student with an exam in 40 days, one request at a time", "")
        for name, vals in (
            ("today (30 calls)", today),
            ("queue, 20 cards (30 calls)", queue),
            ("quick revision plan (30 calls)", plan),
            ("quick queue, 20 cards (30 calls)", quick),
            ("pack of 300 (10 calls)", packs),
            ("one review with the horizon (40 calls)", singles),
        ):
            line(f"  {name}", f"p50 {pct(vals, 50):.0f} ms  p95 {pct(vals, 95):.0f} ms")
        line("  pack size", f"{sum(sizes) / len(sizes):.0f} KB gzip")
        line("  batch of 100 reviews (4 calls)", f"p50 {pct(batches, 50):.0f} ms  max {max(batches):.0f} ms")

        t0 = time.perf_counter()
        with ThreadPoolExecutor(args.reviewers) as pool:
            results = list(pool.map(lambda u: reader(base, u, args.rounds), users))
        wall = time.perf_counter() - t0
        busy = {k: [x for r in results for x in r[k]] for k in ("today", "plan", "quick")}
        line(f"\n{args.reviewers} students at once", f"{sum(len(v) for v in busy.values())} requests in {wall:.1f} s")
        for name, key in (("today", "today"), ("quick revision plan", "plan"), ("quick queue", "quick")):
            line(
                f"  {name}",
                f"p50 {pct(busy[key], 50):.0f} ms  p95 {pct(busy[key], 95):.0f} ms  ({len(busy[key])} calls)",
            )
        line("  failed", str(sum(r["failed"] for r in results)))

        print("\nTargets (PRD section 12), p95", flush=True)
        verdicts = {
            "queue": (pct(queue, 95), None),
            "today": (pct(today, 95), pct(busy["today"], 95)),
            "quick plan": (pct(plan, 95), pct(busy["plan"], 95)),
            "quick queue": (pct(quick, 95), pct(busy["quick"], 95)),
            "review": (pct(singles, 95), None),
            "batch of 100": (max(batches), None),
            "pack of 300": (pct(packs, 95), None),
        }
        for name, (alone, many) in verdicts.items():
            limit = TARGETS_MS[name]
            parts = [f"alone {alone:.0f} ms {'MET' if alone <= limit else 'MISSED'}"]
            if many is not None:
                parts.append(f"{args.reviewers} students {many:.0f} ms {'MET' if many <= limit else 'MISSED'}")
            line(f"  {name}, under {limit} ms", ";  ".join(parts))
            if alone > limit or (many is not None and many > limit):
                missed.append(name)
        gz_ok = max(sizes) <= base_capacity.PACK_GZIP_KB
        line(
            f"  pack under {base_capacity.PACK_GZIP_KB} KB gzip",
            f"{'MET' if gz_ok else 'MISSED'}  ({max(sizes):.0f} KB)",
        )
        if not gz_ok:
            missed.append("pack size")
        for u in users:
            client_for(base, u).post("/recall/erase/", json={"confirm": "ERASE"})
        left = sum(len(run.rows_left(u)) for u in users)
        line("test students erased", "yes" if left == 0 else f"NO, {left} tables still hold rows")
    finally:
        for p in procs:
            p.terminate()
    if missed:
        print(f"\nMISSED: {', '.join(missed)}")
    return 1 if (missed and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
