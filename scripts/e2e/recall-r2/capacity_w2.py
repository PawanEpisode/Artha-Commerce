"""
Indicative capacity numbers for the living-deck paths (R2-W2; see "Capacity note" in docs/F-15-ROLLOUT.md). Same machine and
method as `capacity.py`. It measures, against a local PostgreSQL:

  1. one subscription of 500 cards with 50 substantive changes: the update preview (HTTP, 20 calls), the apply (HTTP) and the
     same sync called in-process on a second identical student;
  2. a deck published to 1,000 followers: the fan-out through `recall.sync_subscribers` (chunks of 200) and the per-subscription
     retry jobs, driven by `jobs.tick()` exactly as the 5-minute tick does, with the PRD target "within 15 minutes" checked
     against the number of ticks that were needed.

    DATABASE_URL=postgres://... python scripts/e2e/recall-r2/capacity_w2.py [--cards 500] [--changes 50] [--followers 1000] [--strict]

Students are created in bulk and erased at the end. No card text is printed.
"""

from __future__ import annotations

import argparse
import math
import os
import platform
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "recall-r1"))
import capacity as base_capacity  # noqa: E402
import run  # noqa: E402

pct, line, client_for, timed = base_capacity.pct, base_capacity.line, base_capacity.client_for, base_capacity.timed
TARGET_PREVIEW_MS = 300  # read path
TARGET_APPLY_MS = 2000  # one subscription of 500 cards with 50 changes: interactive, under two seconds
TARGET_FANOUT_MINUTES = 15  # FR-F15-47: a follower is synced within 15 minutes of the publish
TICK_MINUTES = 5


def boot():
    os.environ.update(run.ENV)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(run.API))
    import django

    django.setup()


def studied(user: uuid.UUID) -> None:
    from django.utils import timezone

    from modules.recall.models import RecallCard

    now = timezone.now()
    RecallCard.objects.filter(user_id=user).update(
        state=2, stability=20.0, difficulty=5.0, reps=3, last_review_at=now - timedelta(days=3),
        due_scheduled_at=now + timedelta(days=15), due_at=now + timedelta(days=15),
    )  # fmt: skip


def edits(items, n: int) -> None:
    from modules.recall.tests.w22 import edit, pointer

    for item in items[:n]:
        edit(item, pointer(f"{run.MARK} changed {uuid.uuid4().hex[:6]}?"), "substantive")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", type=int, default=500)
    ap.add_argument("--changes", type=int, default=50)
    ap.add_argument("--followers", type=int, default=1000)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    run.ENV["DJANGO_DEBUG"] = "false"
    procs, base = run.start()
    missed: list[str] = []
    try:
        boot()
        from core.models import Job
        from modules.recall import jobs as recall_jobs
        from modules.recall.models import RecallDeck, RecallSubscription
        from modules.recall.services import erasure, subscriptions
        from modules.recall.services import sync as sync_service
        from modules.recall.tests.w11 import published_deck
        from modules.recall.tests.w22 import publish_next

        with run.pg() as conn:
            pgv = conn.execute("SHOW server_version").fetchone()[0]
        line(
            "machine",
            f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, Python {platform.python_version()}",
        )
        line("database", f"PostgreSQL {pgv} on the same machine; API: Django server, one process")

        # 1. One subscription: 500 cards, 50 substantive changes.
        deck, items, _ = published_deck(args.cards, importances=["mandatory", "important", "bullet"], title="cap-w2-a")
        via_http, in_process = uuid.uuid4(), uuid.uuid4()
        subs = {u: subscriptions.subscribe(u, deck.id).subscription for u in (via_http, in_process)}
        for u in subs:
            studied(u)
        edits(items, args.changes)
        publish_next(deck, changelog="Capacity run.")
        Job.objects.all().delete()  # the fan-out job of this publish is not what step 1 measures
        c = client_for(base, str(via_http))
        previews = [timed(c, "GET", f"/recall/subscriptions/{subs[via_http].id}/update/")[0] for _ in range(20)]
        ms_apply, r = timed(c, "POST", f"/recall/subscriptions/{subs[via_http].id}/apply-update/")
        ok_http = r.status_code == 200 and r.json()["result"]["cards_reset"] == args.changes
        again_ms, again = timed(c, "POST", f"/recall/subscriptions/{subs[via_http].id}/apply-update/")
        t0 = time.perf_counter()
        result = sync_service.sync_subscription(in_process, subs[in_process].id)
        direct_ms = (time.perf_counter() - t0) * 1000
        line(f"\nOne subscription: {args.cards} cards, {args.changes} substantive changes", "")
        line("  update preview (20 calls)", f"p50 {pct(previews, 50):.0f} ms  p95 {pct(previews, 95):.0f} ms")
        line(
            "  apply over HTTP (first call)",
            f"{ms_apply:.0f} ms, {args.changes} cards reset: {'yes' if ok_http else 'NO'}",
        )
        line("  apply again (no change)", f"{again_ms:.0f} ms, changed: {again.json()['result']['changed']}")
        line("  same sync in-process", f"{direct_ms:.0f} ms, {result.cards_reset} cards reset")
        for name, value, limit in (
            ("preview", pct(previews, 95), TARGET_PREVIEW_MS),
            ("apply", ms_apply, TARGET_APPLY_MS),
        ):
            line(f"  {name} under {limit} ms", f"{'MET' if value <= limit else 'MISSED'}  ({value:.0f} ms)")
            if value > limit:
                missed.append(name)
        if not ok_http:
            missed.append("apply result")

        # 2. Fan-out to followers.
        small, small_items, _ = published_deck(30, title="cap-w2-b")
        t0 = time.perf_counter()
        users = [uuid.uuid4() for _ in range(args.followers)]
        for u in users:
            subscriptions.subscribe(u, small.id)
        for u in users:
            studied(u)
        line(f"\n{args.followers} followers of a 30 card deck seeded", f"{time.perf_counter() - t0:.0f} s")
        edits(small_items, 5)
        t0 = time.perf_counter()
        version = publish_next(small, changelog="Capacity run.")
        queued = Job.objects.filter(
            type=sync_service.JOB_SYNC_SUBSCRIBERS, payload__deck_version_id=str(version.id)
        ).count()
        ticks, stats = 0, {}
        while True:
            ticks += 1
            recall_jobs.tick()
            stats = sync_service.fanout_stats(version.id)
            if stats["queued"] == 0 and stats["running"] == 0 or ticks >= 50:
                break
        wall = time.perf_counter() - t0
        left = RecallSubscription.objects.filter(deck=small).exclude(synced_version=version).count()
        chunks = Job.objects.filter(
            type=sync_service.JOB_SYNC_SUBSCRIBERS, payload__deck_version_id=str(version.id)
        ).count()
        line(
            "  jobs queued by the publish",
            f"{queued} (the first chunk); {chunks} chunk jobs in all, each queues the next",
        )
        line(
            "  fan-out wall time",
            f"{wall:.1f} s in {ticks} tick call(s); per subscription {wall / args.followers * 1000:.0f} ms",
        )
        line("  job outcome", f"{stats}; subscriptions not yet on the new version: {left}")
        # A tick has a time budget, so a real 5-minute cron needs one tick per budget's worth of work.
        needed = max(1, math.ceil(wall / recall_jobs.TICK_BUDGET_SECONDS))
        minutes = needed * TICK_MINUTES
        met = left == 0 and minutes <= TARGET_FANOUT_MINUTES
        line(
            f"  within {TARGET_FANOUT_MINUTES} minutes (5-minute tick, {recall_jobs.TICK_BUDGET_SECONDS} s budget)",
            f"{'MET' if met else 'MISSED'}  ({needed} tick(s) of work, about {minutes} minutes)",
        )
        if not met:
            missed.append("fan-out")
        for u in [via_http, in_process, *users]:
            erasure.delete_all_for_user(u)
        gone = sum(len(run.rows_left(str(u))) for u in (via_http, in_process, users[0], users[-1]))
        line("test students erased", "yes" if gone == 0 else f"NO, {gone} tables still hold rows")
        RecallDeck.objects.filter(title__startswith="cap-w2-").update(status="withdrawn")
    finally:
        for p in procs:
            p.terminate()
    if missed:
        print(f"\nMISSED: {', '.join(missed)}")
    return 1 if (missed and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
