"""
End-to-end check of recall R2 over real HTTP, one section per wave. It reuses the R1 harness (server with `recall_system`
answered locally, generated seed deck, JWT helper) and a throwaway student. Usage, from the repo root with the API's virtualenv
active and a local PostgreSQL running:

    DATABASE_URL=postgres://... python scripts/e2e/recall-r2/run.py

W3 (Recall x Coverage, Tracker and Today): the strength read of a chapter, paste import (preview, atomic real call, replay, row cap),
the chapter recall pass (80% of a set of at least 5 in 7 days counts ONE revision in coverage, once per week, replays add nothing)
and the opt-in tracker session (off by default, one `auto` revision session per finished recall session, replays add nothing).

W2 (living decks): a new deck version reaches a follower through the job queue (cards whose meaning changed come back softened with
a re-check note, typo fixes change nothing), a pinned subscription only records the pending version until she applies it, the
amendment port flags platform items, "Still correct" clears a note, and export and erase cover the new columns and tables.

W1 (exam awareness): the exam date comes from the enrolment, the horizon pulls late cards in front of the exam, quick revision
and cram answer, the unlock by coverage holds back new cards of chapters not started, and rebalance stops at the exam.
Only counts and ids are printed: no card text. Run it against a local or scratch database, never production.
"""

from __future__ import annotations

import sys
import tempfile
import time
import uuid
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


SHELL_PRELUDE = (
    "import uuid\n"
    "from modules.recall.models import RecallDeck, RecallDeckVersionItem, RecallItem\n"
    "from modules.recall.services import decks as d\n"
    "E = uuid.uuid4()\n"
    f"deck = RecallDeck.objects.get(slug='{SLUG}')\n"
)


def publish_version(changes: dict[str, list[str]], added: int = 0, note: str = "Changes.") -> str:
    """Publishes a new live version of the generated deck as staff would: edits, additions, removals, then the publish."""
    code = SHELL_PRELUDE + (
        f"changes = {changes!r}\n"
        "for kind in ('substantive', 'typo'):\n"
        "    for item_id in changes.get(kind, []):\n"
        "        item = RecallItem.objects.get(pk=item_id)\n"
        f"        d.new_item_version(E, item, {{'prompt_md': '{MARK} ' + kind + ' ' + item_id[:6] + '?', 'answer_md': '{MARK} answer.'}}, change_kind=kind)\n"
        "draft = d.start_draft_version(E, deck)\n"
        "rows = list(RecallDeckVersionItem.objects.filter(deck_version=draft).select_related('item').order_by('position'))\n"
        "gone = set(changes.get('removed', []))\n"
        "keep = [r.item for r in rows if str(r.item_id) not in gone]\n"
        f"for n in range({added}):\n"
        f"    keep.append(d.create_platform_item(E, kind='pointer', fields={{'prompt_md': '{MARK} new ' + uuid.uuid4().hex[:6] + '?', 'answer_md': '{MARK} answer.'}}, importance='mandatory', rights_status='original', external_ref='{SLUG}-new-' + uuid.uuid4().hex[:6], chapter_id=None))\n"
        "d.set_draft_rows(draft, [(i, None) for i in keep])\n"
        f"v = d.publish_deck_version(E, deck.id, draft.id, changelog_md={note!r})\n"
        "print('VERSION', v.version_no)\n"
    )
    out = r1.manage("shell", "-c", code)
    assert out.returncode == 0 and "VERSION" in out.stdout, out.stderr[-500:]
    return out.stdout.strip().splitlines()[-1].split()[-1]


def run_tick(base: str, times: int = 3) -> None:
    for _ in range(times):
        httpx.post(f"{base}/recall/internal/tick/", headers={"X-Recall-Tick-Secret": r1.TICK}, timeout=120)


def study_age(client: httpx.Client, ids: list[str], first_review_days_ago: int, rating: int = 3) -> None:
    """One review long ago per card, so each card has a memory and a due date of its own."""
    start = datetime.now(UTC) - timedelta(days=first_review_days_ago)
    for i, card_id in enumerate(ids):
        ev = r1.event(card_id, rating, start + timedelta(minutes=i), "r2-dev")
        client.post("/recall/reviews/", json=ev)


def other_chapter_id(scheme: str, not_id: str) -> str:
    out = r1.manage(
        "shell",
        "-c",
        "from modules.syllabus.models import Chapter; "
        f"print(Chapter.objects.filter(subject__scheme_id='{scheme}', is_active=True).exclude(id='{not_id}')"
        ".order_by('id').values_list('id', flat=True).first())",
    )
    return out.stdout.strip().splitlines()[-1]


def session_review(client: httpx.Client, card_ids: list[str], seconds_each: int = 20, wall_seconds: int = 0) -> str:
    """
    One closed recall session in which each card was answered Good, claiming `seconds_each` seconds a card. The tracker never
    records more time than really passed since the session opened, so a check that needs a recorded minute waits `wall_seconds`.
    Returns the session id.
    """
    sid = client.post("/recall/sessions/", json={"client_id": str(uuid.uuid4()), "source": "today"}).json()["id"]
    time.sleep(wall_seconds)
    now = datetime.now(UTC) - timedelta(seconds=len(card_ids) + 1)  # answered a moment ago, never in the server's future
    for i, card_id in enumerate(card_ids):
        ev = r1.event(card_id, 3, now + timedelta(seconds=i), "w3-dev", session=sid)
        ev["duration_ms"] = seconds_each * 1000
        res = client.post("/recall/reviews/", json=ev)
        assert res.status_code in (200, 201), res.text[:200]
    closed = client.post(f"/recall/sessions/{sid}/close/", json={})
    assert closed.status_code == 200, closed.text[:200]
    return sid


def revisions_of(client: httpx.Client, chapter: str) -> int:
    d = client.get(f"/coverage/chapters/{chapter}/").json()
    return (d.get("chapter") or d).get("revision_count", -1)


def revision_events(user: str, chapter: str) -> int:
    """The same fact from the database: `revision_done` events of the system, for the student and chapter."""
    with r1.pg() as conn:
        return conn.execute(
            "SELECT count(*) FROM coverage_event WHERE user_id = %s AND chapter_id = %s AND type = 'revision_done'",
            [user, chapter],
        ).fetchone()[0]


def auto_revision_sessions(client: httpx.Client) -> list[dict]:
    rows = client.get("/tracking/sessions/", params={"limit": 100}).json()["results"]
    return [r for r in rows if r["source"] == "auto" and r["activity_type"] == "revision"]


def w3(client: httpx.Client, base: str, ch: str, scheme: str) -> None:
    """R2 wave W3, over HTTP, on the student of the earlier sections."""
    # B. Recall strength of a chapter: one read, numbers only, a chapter she has no cards in is zeros and never a 404.
    t0 = time.perf_counter()
    res = client.get(f"/recall/chapters/{ch}/strength/")
    strength_ms = (time.perf_counter() - t0) * 1000
    body = res.json()
    check(
        "the strength of a chapter answers with cards, due and a percent",
        res.status_code == 200
        and body["cards"] > 0
        and isinstance(body["due"], int)
        and (body["percent"] is None or 0 <= body["percent"] <= 100),
        body,
    )
    empty = client.get(f"/recall/chapters/{uuid.uuid4()}/strength/")
    check(
        "a chapter without cards is zeros, not a 404",
        empty.status_code == 200 and empty.json()["cards"] == 0 and empty.json()["percent"] is None,
        empty.text[:160],
    )

    # F. Paste import: a preview writes nothing, the real call creates only the valid rows, a replay creates nothing.
    before = len(r1.all_cards(client))
    text = f"{r1.MARK} import one? :: yes\n{r1.MARK} no back here\n{r1.MARK} import two? :: yes"
    batch = str(uuid.uuid4())
    dry = client.post("/recall/cards/import/", json={"client_id": batch, "dry_run": True, "text": text}).json()
    check(
        "the import preview judges every row and writes nothing",
        [r["status"] for r in dry["rows"]] == ["ok", "error", "ok"]
        and dry["rows"][1]["issues"][0]["code"] == "missing_back"
        and dry["quota"]["fits"]
        and len(r1.all_cards(client)) == before,
        dry,
    )
    real = client.post("/recall/cards/import/", json={"client_id": batch, "dry_run": False, "text": text})
    rb = real.json()
    check(
        "the real import creates only the valid rows",
        real.status_code == 201 and rb["created"] == 2 and rb["invalid"] == 1 and len(r1.all_cards(client)) == before + 2,
        (real.status_code, rb.get("created"), rb.get("invalid")),
    )
    again = client.post("/recall/cards/import/", json={"client_id": batch, "dry_run": False, "text": text})
    check(
        "replaying the same import creates and reserves nothing",
        again.status_code == 200
        and again.json()["created"] == 0
        and again.json()["existing"] == 2
        and len(r1.all_cards(client)) == before + 2,
        again.text[:200],
    )
    big = "\n".join(f"{r1.MARK} bulk {i}? :: a" for i in range(201))
    over = client.post("/recall/cards/import/", json={"client_id": str(uuid.uuid4()), "dry_run": True, "text": big})
    check(
        "more than 200 rows is refused",
        over.status_code == 422 and over.json()["error"]["code"] == "import_too_large",
        over.text[:160],
    )

    # A. The chapter recall pass. Five of her own mandatory cards in a second chapter: 4 of 5 (80%) within 7 days passes.
    ch2 = other_chapter_id(scheme, ch)
    own: list[str] = []
    for i in range(5):
        made = client.post(
            "/recall/cards/",
            json={
                "client_id": str(uuid.uuid4()),
                "kind": "pointer",
                "fields": {"prompt_md": f"{r1.MARK} pass {i}?", "answer_md": f"{r1.MARK} a."},
                "importance": "mandatory",
                "chapter_id": ch2,
            },
        )
        own.append(made.json()["cards"][0]["id"])
    before_rev = revision_events(r1.USER, ch2)
    revisions = lambda: revision_events(r1.USER, ch2)  # noqa: E731
    session_review(client, own[:3])  # 3 of 5 = 60%
    run_tick(base)
    check("60% of a set is not a pass", revisions() == before_rev, (revisions(), before_rev))
    session_review(client, own[3:4])  # 4 of 5 = 80% within the 7 days
    run_tick(base)
    check(
        "80% of a set of five, over two sessions in a week, counts one revision",
        revisions() == before_rev + 1,
        (revisions(), before_rev, revisions_of(client, ch2)),
    )
    session_review(client, own[4:5])  # 5 of 5, but a pass was already announced this week
    run_tick(base)
    run_tick(base)
    check(
        "a second pass in the same week and a replayed job add nothing",
        revisions() == before_rev + 1 and revisions_of(client, ch2) in (1, before_rev + 1),
        (revisions(), revisions_of(client, ch2)),
    )

    # E. The tracker: off by default, so the sessions above left nothing; with auto capture on, one `auto` revision session each.
    check("auto capture is off by default: no tracker session from recall yet", auto_revision_sessions(client) == [])
    on = client.put("/tracking/settings/", json={"auto_capture_enabled": True})
    check("auto capture can be switched on", on.status_code == 200, on.text[:160])
    sid = session_review(client, [own[0], own[1], own[2]], seconds_each=30, wall_seconds=65)
    forwarded = auto_revision_sessions(client)
    check(
        "a finished recall session becomes one auto revision session in the tracker",
        len(forwarded) == 1 and forwarded[0]["focus_seconds"] >= 60,
        forwarded,
    )
    replay = client.post(f"/recall/sessions/{sid}/close/", json={})
    run_tick(base)
    check(
        "closing again or replaying adds no second tracker session",
        replay.status_code == 200 and len(auto_revision_sessions(client)) == 1,
        len(auto_revision_sessions(client)),
    )
    client.put("/tracking/settings/", json={"auto_capture_enabled": False})
    print(f"INFO  W3 strength read: {strength_ms:.0f} ms", flush=True)


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

        # W1.3 Give 60 cards a memory from 25 days ago (the server refuses older single reviews as late_unapplied) whose own due date lies after the exam: the horizon pulls them in.
        cards = r1.all_cards(client)
        ids = [c["id"] for c in cards if c["importance"] in ("mandatory", "important")][:60]
        study_age(client, ids, 25, rating=4)
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
        check(
            "the studied cards really have a memory (the check above is not vacuous)",
            sum(1 for i in ids if cards_after[i]["state_name"] != "new") >= 55,
        )

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

        # W2 Living decks. She holds the whole deck (320 cards, 60 of them studied above), following updates by default.
        warm = ids[:12]
        study_age(client, warm, 5)  # a recent review each (the server refuses events older than 30 days)
        by_id = {c["id"]: c for c in r1.all_cards(client)}
        pool = [by_id[i]["item_id"] for i in warm]
        check("twelve cards are in review before the update", all(by_id[i]["state_name"] != "new" for i in warm))
        sub_id = client.get(f"/recall/decks/{deck['id']}/").json()["deck"]["subscription"]["id"]
        t0 = time.perf_counter()
        v2 = publish_version(
            {"substantive": pool[:3], "typo": pool[3:5], "removed": pool[5:6]}, added=2, note="Reworded three cards."
        )
        preview = client.get(f"/recall/subscriptions/{sub_id}/update/")
        pv = preview.json()
        check(
            "the update preview counts the changes by kind and the cards that return",
            preview.status_code == 200
            and pv["update_available"]
            and pv["counts"]["substantive"] == 3
            and pv["counts"]["typo"] == 2
            and pv["counts"]["added"] == 2
            and pv["counts"]["removed"] == 1
            and pv["returning_today"] == 3,
            (pv.get("counts"), pv.get("returning_today")),
        )
        check(
            "the preview is read only (still on version 1)",
            pv["from_version_no"] == 1 and pv["to_version_no"] == int(v2),
        )
        run_tick(base)
        sync_s = time.perf_counter() - t0
        d2 = client.get(f"/recall/decks/{deck['id']}/").json()["deck"]
        check(
            "a follower is brought to the new version by the job queue",
            d2["subscription"]["update_available"] is False and d2["subscription"]["version_no"] == int(v2),
            (d2["subscription"], round(sync_s, 1)),
        )
        after = {c["id"]: c for c in r1.all_cards(client)}
        changed = [c for c in pool[:3]]
        flagged = [c for c in after.values() if c["item_id"] in changed and c["needs_recheck"]]
        check(
            "cards whose meaning changed carry the re-check note",
            len(flagged) == 3 and all(c["recheck_reason"] == "content_changed" and c["updated"] for c in flagged),
            [(c["needs_recheck"], c["recheck_reason"]) for c in after.values() if c["item_id"] in changed],
        )
        typos = [c for c in after.values() if c["item_id"] in pool[3:5] and c["needs_recheck"]]
        check("typo fixes change nothing for the student", typos == [], len(typos))
        check("today counts the cards to re-check", client.get("/recall/today/").json()["recheck"]["count"] == 3)
        pack = client.get("/recall/pack/").json()
        check(
            "the offline pack carries the re-check fields",
            any(c.get("needs_recheck") for c in pack["cards"]) and all("recheck_reason" in c for c in pack["cards"]),
        )
        again = client.post(f"/recall/subscriptions/{sub_id}/apply-update/")
        check(
            "apply after the job ran is a no-op",
            again.status_code == 200 and again.json()["result"]["changed"] is False,
            again.text[:160],
        )

        # Still correct clears one note and leaves the memory alone.
        card = flagged[0]
        ok = client.post(f"/recall/cards/{card['id']}/recheck-ok/", json={})
        check(
            "Still correct clears the note",
            ok.status_code == 200 and ok.json()["needs_recheck"] is False,
            ok.text[:160],
        )
        check("one note fewer on today", client.get("/recall/today/").json()["recheck"]["count"] == 2)

        # Pin: a new version only records the pending version until she applies it.
        pin = client.patch(f"/recall/subscriptions/{sub_id}/", json={"follow_updates": False})
        check(
            "she can pin the deck",
            pin.status_code == 200 and pin.json()["deck"]["subscription"]["follow_updates"] is False,
        )
        v3 = publish_version({"substantive": pool[6:7]}, note="One more.")
        run_tick(base)
        d3 = client.get(f"/recall/decks/{deck['id']}/").json()["deck"]["subscription"]
        check(
            "a pinned subscription is not moved and shows the update",
            d3["version_no"] == int(v2) and d3["update_available"] is True and d3["pending_version_no"] == int(v3),
            d3,
        )
        t1 = time.perf_counter()
        applied = client.post(f"/recall/subscriptions/{sub_id}/apply-update/")
        apply_ms = (time.perf_counter() - t1) * 1000
        check(
            "apply moves the pinned subscription to the live version",
            applied.status_code == 200
            and applied.json()["result"]["changed"]
            and applied.json()["deck"]["subscription"]["version_no"] == int(v3),
            applied.text[:200],
        )
        print(
            f"INFO  sync of version 2 through the queue: {sync_s:.1f} s; apply of version 3: {apply_ms:.0f} ms",
            flush=True,
        )
        back = client.patch(f"/recall/subscriptions/{sub_id}/", json={"follow_updates": True})
        check(
            "she can follow again",
            back.status_code == 200 and back.json()["deck"]["subscription"]["follow_updates"] is True,
        )

        # Amendment port: F-14 is not built, so the event is emitted the way it would: by name, from another process.
        key = f"s{uuid.uuid4().hex[:6]}"
        keyed = pool[10:12]
        r1.manage(
            "shell",
            "-c",
            "from modules.recall.models import RecallItem\n"
            f"RecallItem.objects.filter(pk__in={keyed!r}).update(reference_keys=['{key}'])\n"
            "from core import events\n"
            f"events.emit('amendment_published', amendment_id='{uuid.uuid4()}', revision_id='{uuid.uuid4()}', provision_keys=['{key}'])\n",
        )
        run_tick(base)
        items = client.get(f"/recall/decks/{deck['id']}/").json()["items"]
        flagged_items = {i["item_id"] for i in items if i["under_review"]}
        check(
            "an amendment marks the matching platform items as under review",
            flagged_items == set(keyed),
            len(flagged_items),
        )
        check(
            "an amendment changes no student memory",
            all(
                a["due_at"] == after[a["id"]]["due_at"]
                for a in r1.all_cards(client)
                if a["id"] in after and not a["needs_recheck"] and a["item_id"] not in pool[6:7]
            ),
        )

        # W3 (runs here: the student has studied cards, an enrolment and the deck).
        w3(client, base, ch, scheme_id())

        # Export and erase cover what W2 added.
        export = client.get("/recall/export/")
        body = export.json() if export.status_code == 200 else {}
        card_cols = (body.get("cards") or [{}])[0]
        check(
            "export carries the new columns and tables",
            "chapter_remaps" in body
            and "needs_recheck" in card_cols
            and "follow_updates" in (body.get("subscriptions") or [{}])[0]
            and any("chapter_passes" in x for x in body.get("sessions") or []),
            sorted(body)[:12],
        )

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
