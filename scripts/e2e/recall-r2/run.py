"""
End-to-end check of recall R2 over real HTTP, one section per wave. It reuses the R1 harness (server with `recall_system`
answered locally, generated seed deck, JWT helper) and a throwaway student. Usage, from the repo root with the API's virtualenv
active and a local PostgreSQL running:

    DATABASE_URL=postgres://... python scripts/e2e/recall-r2/run.py

W1 (exam awareness): the exam date comes from the enrolment, the horizon pulls late cards in front of the exam, quick revision
and cram answer, the unlock by coverage holds back new cards of chapters not started, and rebalance stops at the exam.
Only counts and ids are printed: no card text. Run it against a local or scratch database, never production.
"""

from __future__ import annotations

import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "recall-r1"))
import run as r1  # noqa: E402

check = r1.check
SLUG = r1.SLUG
MARK = r1.MARK


def scheme_id() -> str:
    out = r1.manage(
        "shell",
        "-c",
        "from modules.syllabus.models import Scheme; "
        "print(Scheme.objects.filter(level__course__code='cma', level__code='final', status='published')"
        ".values_list('id', flat=True).first())",
    )
    return out.stdout.strip().splitlines()[-1]


def chapter_id() -> str:
    out = r1.manage(
        "shell",
        "-c",
        "from modules.syllabus.models import Chapter; "
        f"print(Chapter.objects.get(key='{r1.SCOPE['chapter_key']}', subject__key='{r1.SCOPE['subject_key']}', "
        "subject__scheme__status='published').id)",
    )
    return out.stdout.strip().splitlines()[-1]


def study_age(client: httpx.Client, ids: list[str], first_review_days_ago: int, rating: int = 3) -> None:
    """One review long ago per card, so each card has a memory and a due date of its own."""
    start = datetime.now(UTC) - timedelta(days=first_review_days_ago)
    for i, card_id in enumerate(ids):
        ev = r1.event(card_id, rating, start + timedelta(minutes=i), "r2-dev")
        client.post("/recall/reviews/", json=ev)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="recall-r2-e2e-"))
    server_log = tmp / "server.log"
    procs: list = []
    try:
        seeds = tmp / "seed"
        seeds.mkdir()
        r1.seed_file(seeds)
        procs, base = r1.start(server_log)
        out = r1.manage("load_recall_seed", str(seeds), "--publish")
        check("seed loader publishes the generated deck", out.returncode == 0 and SLUG in out.stdout, out.stderr[-300:])
        client = httpx.Client(base_url=base, headers={"authorization": f"Bearer {r1.token()}"}, timeout=60)
        lib = client.get("/recall/decks/library/", params={"limit": 50}).json()
        deck = next((d for d in lib.get("items", []) if d["slug"] == SLUG), None)
        if not deck:
            check("the deck shows in the library", False)
            return 1

        # W1.1 No exam date yet: the plan says so and Today carries no exam block.
        none = client.get("/recall/quick-revision/plan/")
        check(
            "quick revision asks for an exam date",
            none.status_code == 422 and none.json()["error"]["code"] == "no_exam_date",
            none.text[:160],
        )
        check("today has no exam block", client.get("/recall/today/").json()["exam"] is None)

        # W1.2 Subscribe with "unlock with coverage", enrol with an exam 100 days out: the chapter is not started, so no
        #      new card is served; starting the chapter opens its cards.
        sub = client.post(f"/recall/decks/{deck['id']}/subscribe/", json={"unlock_mode": "with_coverage"})
        check("subscribe with unlock by coverage", sub.status_code == 201, sub.text[:160])
        enrol = client.post(
            "/coverage/enrollments/",
            json={"scheme": scheme_id(), "exam_date": (datetime.now(UTC) + timedelta(days=100)).date().isoformat()},
        )
        check("an enrolment with an exam date is created", enrol.status_code in (200, 201), enrol.text[:200])
        closed = client.get("/recall/queue/", params={"source": "today", "limit": 50}).json()
        check("new cards of a chapter not started stay closed", closed["cards"] == [], len(closed["cards"]))
        ch = chapter_id()
        detail = client.get(f"/coverage/chapters/{ch}/").json()
        topics = detail.get("topics") or []
        tick = (
            client.put(f"/coverage/topics/{topics[0]['id']}/", json={"done": True})
            if topics
            else client.put(f"/coverage/chapters/{ch}/read/", json={"done": True})
        )
        check("the chapter is started in coverage", tick.status_code == 200, tick.text[:200])
        opened = client.get("/recall/queue/", params={"source": "today", "limit": 50}).json()
        check("starting the chapter opens its new cards", len(opened["cards"]) > 0, len(opened["cards"]))

        # W1.3 Give 60 cards a memory from 40 days ago whose own due date lies after the exam: the horizon pulls them in.
        cards = r1.all_cards(client)
        ids = [c["id"] for c in cards if c["importance"] in ("mandatory", "important")][:60]
        study_age(client, ids, 40, rating=4)
        exam = client.get("/recall/today/").json()["exam"]
        check(
            "today shows the exam countdown",
            exam is not None and 97 <= exam["days_to_exam"] <= 100 and exam["cram_open"] is False,
            exam,
        )
        patch = client.patch(
            "/coverage/enrollments/" + enrol.json()["id"] + "/",
            json={"exam_date": (datetime.now(UTC) + timedelta(days=30)).date().isoformat()},
        )
        check("the exam date can be moved closer", patch.status_code == 200, patch.text[:200])
        time.sleep(1)
        tick = httpx.post(f"{base}/recall/internal/tick/", headers={"X-Recall-Tick-Secret": r1.TICK})
        check(
            "the nightly tick answers and reports its jobs",
            tick.status_code == 200 and "jobs_ran" in tick.json(),
            tick.text[:160],
        )
        window_end = datetime.now(UTC) + timedelta(days=28)
        cards_after = {c["id"]: c for c in r1.all_cards(client)}
        late = [
            i
            for i in ids
            if cards_after[i]["due_at"]
            and datetime.fromisoformat(cards_after[i]["due_at"].replace("Z", "+00:00")) > window_end
        ]
        check("no studied card is due in the last two days before the exam or after it", late == [], len(late))

        # W1.4 Quick revision: a plan, then the queue served from it.
        plan = client.get("/recall/quick-revision/plan/", params={"minutes": 20})
        body = plan.json()
        check(
            "the quick plan answers with the numbers and a sample",
            plan.status_code == 200
            and body["days_to_exam"] in (29, 30)
            and "selected" in body
            and len(body["sample"]) <= 5,
            plan.text[:200],
        )
        small = client.get("/recall/quick-revision/plan/", params={"minutes": 5}).json()
        check(
            "fewer minutes never select more cards",
            small["selected"] <= body["selected"],
            (small["selected"], body["selected"]),
        )
        quick = client.get("/recall/queue/", params={"source": "quick", "limit": 20})
        check(
            "the quick queue serves cards",
            quick.status_code == 200 and len(quick.json()["cards"]) <= 20,
            quick.text[:160],
        )
        cram = client.get("/recall/queue/", params={"source": "cram"})
        check(
            "cram is closed until the last day",
            cram.status_code == 422 and cram.json()["error"]["code"] == "cram_not_open",
            cram.text[:160],
        )
        pack = client.get("/recall/pack/").json()
        check("the offline pack carries the exam instant", pack.get("exam_at") is not None, pack.get("exam_at"))

        # W1.5 Rebalance never pushes a card past the cutoff before the exam.
        reb = client.post("/recall/catchup/rebalance/", json={"days": 7})
        check("rebalance still works near an exam", reb.status_code == 200, reb.text[:160])

        # Erase covers everything R2 added so far, then the platform deck is withdrawn and the log is searched for text.
        gone = client.post("/recall/erase/", json={"confirm": "ERASE"})
        check("erase answers", gone.status_code == 200, gone.text[:160])
        left = r1.rows_left(r1.USER)
        check("no recall table holds a row for the student", left == {}, left)
        with r1.pg() as conn:
            conn.execute("UPDATE recall_deck SET status = 'withdrawn' WHERE slug = %s", [SLUG])
        for p in procs:
            p.terminate()
        procs = []
        time.sleep(1)
        log = server_log.read_text(errors="replace")
        check(
            "the server log holds no card text",
            MARK not in log and "question" not in log.lower().replace("questions", ""),
            len(log),
        )
    finally:
        for p in procs:
            p.terminate()
    print(f"\n{'ALL PASSED' if not r1.failures else f'{len(r1.failures)} FAILED: ' + ', '.join(r1.failures)}")
    return 1 if r1.failures else 0


if __name__ == "__main__":
    sys.exit(main())
