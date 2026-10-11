"""
Indicative capacity numbers for recall R1 on this machine (see "Capacity note" in docs/F-15-ROLLOUT.md): reviews per minute,
queue, today and pack latency (p50 and p95) for students holding 5,000 cards, with 8 of them reviewing at the same time. Same
stack as `run.py` (Django dev server with the flag answered locally, a real PostgreSQL). The numbers are a baseline for comparing
runs, not a production forecast: the dev server is one process, and a laptop database is kinder or harsher than the real one.

    DATABASE_URL=postgres://... python scripts/e2e/recall-r1/capacity.py [--cards 5000] [--reviewers 8] [--rounds 10] [--strict] [--debug]

Each reviewer is its own student with `--cards` cards (bulk inserted; they are erased at the end). Targets come from PRD section 12
(performance): queue and today p95 under 300 ms, a review p95 under 200 ms, a batch of 100 under 800 ms, a pack of 300 under
500 ms and 400 KB gzip. `--strict` exits 1 when one is missed; without it the script always exits 0. No card text is printed.
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
from datetime import UTC, datetime

import httpx
import run

TARGETS_MS = {"queue": 300, "today": 300, "review": 200, "batch of 100": 800, "pack of 300": 500}
PACK_GZIP_KB = 400


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


def line(name: str, value: str) -> None:
    print(f"{name:<44}{value}", flush=True)


def client_for(base: str, user: str) -> httpx.Client:
    return httpx.Client(base_url=base, headers={"authorization": f"Bearer {run.token(user)}"}, timeout=120)


def timed(client: httpx.Client, method: str, url: str, **kwargs) -> tuple[float, httpx.Response]:
    start = time.perf_counter()
    response = client.request(method, url, **kwargs)
    return (time.perf_counter() - start) * 1000, response


def seed_students(users: list[str], cards: int) -> None:
    """Bulk insert `cards` cards per student (a quarter each due, new, later and in learning) with the test helper."""
    os.environ.update(run.ENV)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(run.API))
    import django

    django.setup()
    import uuid as _uuid

    from modules.recall.tests.w6 import library

    for user in users:
        library(cards, user=_uuid.UUID(user), chapter_id=None)


def reviewer(base: str, user: str, rounds: int) -> dict:
    """One student studying: fetch the queue, rate every card Good, ask for Today now and then. Returns the latencies."""
    c = client_for(base, user)
    out: dict = {"queue": [], "review": [], "today": [], "limited": 0, "failed": 0, "reviews": 0}
    for i in range(rounds):
        ms, r = timed(c, "GET", "/recall/queue/", params={"limit": 20})
        out["queue"].append(ms)
        if r.status_code != 200:
            out["failed" if r.status_code != 429 else "limited"] += 1
            continue
        for card in r.json()["cards"]:
            ev = run.event(card["id"], 3, datetime.now(UTC), "capacity")
            ms, res = timed(c, "POST", "/recall/reviews/", json=ev)
            out["review"].append(ms)
            if res.status_code in (200, 201):
                out["reviews"] += 1
            else:
                out["limited" if res.status_code == 429 else "failed"] += 1
        if i % 3 == 0:
            ms, res = timed(c, "GET", "/recall/today/")
            out["today"].append(ms)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", type=int, default=5000)
    ap.add_argument("--reviewers", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=10, help="queue fetches per reviewer, 20 reviews each")
    ap.add_argument("--strict", action="store_true", help="exit 1 when a target is missed")
    ap.add_argument(
        "--debug", action="store_true", help="run the API with DJANGO_DEBUG=true (slower: Django keeps every query)"
    )
    args = ap.parse_args()
    run.ENV["DJANGO_DEBUG"] = "true" if args.debug else "false"  # closer to production, which never runs with DEBUG on
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

        # 1. One student, nothing else running: sequential latency.
        c = client_for(base, users[0])
        today = [timed(c, "GET", "/recall/today/")[0] for _ in range(40)]
        queue = [timed(c, "GET", "/recall/queue/", params={"limit": 20})[0] for _ in range(40)]
        packs, sizes = [], []
        for _ in range(15):
            ms, r = timed(c, "GET", "/recall/pack/", params={"limit": 300})
            packs.append(ms)
            sizes.append(len(gzip.compress(r.content)) / 1024)
        n_pack = len(r.json()["cards"])
        ids: list[str] = []
        cursor = None
        while len(ids) < 540:  # 5 batches of 100 and 40 single reviews, all on different cards
            params = {"limit": 100, **({"cursor": cursor} if cursor else {})}
            page = c.get("/recall/cards/", params=params).json()
            ids += [x["id"] for x in page["items"]]
            cursor = page.get("next_cursor")
            if not cursor:
                break
        batches, singles = [], []
        for k in range(5):
            events = [run.event(i, 3, datetime.now(UTC), "capacity") for i in ids[k * 100 : k * 100 + 100]]
            ms, r = timed(c, "POST", "/recall/reviews/batch/", json={"events": events})
            batches.append(ms if r.status_code == 200 else float("inf"))
        for i in ids[500:540]:
            singles.append(timed(c, "POST", "/recall/reviews/", json=run.event(i, 3, datetime.now(UTC), "capacity"))[0])
        line("\nOne student, one request at a time", "")
        for name, vals in (
            ("today (40 calls)", today),
            ("queue, 20 cards (40 calls)", queue),
            ("pack of 300 (15 calls)", packs),
            ("one review (40 calls)", singles),
        ):
            line(f"  {name}", f"p50 {pct(vals, 50):.0f} ms  p95 {pct(vals, 95):.0f} ms")
        line("  pack size", f"{n_pack} cards, {statistics_mean(sizes):.0f} KB gzip")
        line("  batch of 100 reviews (5 calls)", f"p50 {pct(batches, 50):.0f} ms  max {max(batches):.0f} ms")

        # 2. Every reviewer at once, each on its own student.
        t0 = time.perf_counter()
        with ThreadPoolExecutor(args.reviewers) as pool:
            results = list(pool.map(lambda u: reviewer(base, u, args.rounds), users))
        wall = time.perf_counter() - t0
        q = [x for r in results for x in r["queue"]]
        rv = [x for r in results for x in r["review"]]
        td = [x for r in results for x in r["today"]]
        done = sum(r["reviews"] for r in results)
        line(f"\n{args.reviewers} reviewers at once", f"{done} reviews in {wall:.1f} s")
        line(
            "  throughput",
            f"{done / wall * 60:.0f} reviews per minute ({done / wall / args.reviewers * 60:.0f} per reviewer)",
        )
        line("  queue, 20 cards", f"p50 {pct(q, 50):.0f} ms  p95 {pct(q, 95):.0f} ms  ({len(q)} calls)")
        line("  one review", f"p50 {pct(rv, 50):.0f} ms  p95 {pct(rv, 95):.0f} ms  ({len(rv)} calls)")
        line("  today", f"p50 {pct(td, 50):.0f} ms  p95 {pct(td, 95):.0f} ms  ({len(td)} calls)")
        line(
            "  throttled (429) or failed", f"{sum(r['limited'] for r in results)} / {sum(r['failed'] for r in results)}"
        )

        # 3. Verdict against the targets: alone, then with every reviewer running.
        print("\nTargets (PRD section 12), p95", flush=True)
        verdicts = {
            "queue": (pct(queue, 95), pct(q, 95)),
            "today": (pct(today, 95), pct(td, 95)),
            "review": (pct(singles, 95), pct(rv, 95)),
            "batch of 100": (max(batches), None),
            "pack of 300": (pct(packs, 95), None),
        }
        for name, (alone, busy) in verdicts.items():
            limit = TARGETS_MS[name]
            parts = [f"alone {alone:.0f} ms {'MET' if alone <= limit else 'MISSED'}"]
            if busy is not None:
                parts.append(f"{args.reviewers} reviewers {busy:.0f} ms {'MET' if busy <= limit else 'MISSED'}")
            line(f"  {name}, under {limit} ms", ";  ".join(parts))
            if alone > limit or (busy is not None and busy > limit):
                missed.append(name)
        gz_ok = max(sizes) <= PACK_GZIP_KB
        line(f"  pack under {PACK_GZIP_KB} KB gzip", f"{'MET' if gz_ok else 'MISSED'}  ({max(sizes):.0f} KB)")
        if not gz_ok:
            missed.append("pack size")
        print(
            "\nNot measured here: a production host, network latency, pgbouncer, the web client, real student behaviour (a student\n"
            "reviews about one card every few seconds, so 8 reviewers without think time are far busier than 8 students)."
        )

        # 4. Take the test students away again (also exercises erase at this size).
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


def statistics_mean(values: list[float]) -> float:
    return sum(values) / len(values)


if __name__ == "__main__":
    raise SystemExit(main())
