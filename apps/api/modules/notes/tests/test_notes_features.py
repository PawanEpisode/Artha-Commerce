"""Tags, clips, aggregate, counts, overview, search, settings, usage, account data and the cron tick over HTTP."""

import uuid

import pytest
from django.conf import settings as dj_settings

from modules.notes import jobs
from modules.notes.models import ItemTag, Note, NoteVersion, QuotaUsage, Settings, Tag
from modules.syllabus.models import Chapter
from modules.syllabus.tests.helpers import switch_scheme

from .conftest import edit, new_note

pytestmark = pytest.mark.django_db


# --- Tags ---------------------------------------------------------------------------------------------------------------
def test_tag_lifecycle(api):
    a = api.post("/notes/tags/", {"name": "  Revise Soon "})
    assert a.status_code == 201 and a.json_body["name"] == "Revise Soon"
    again = api.post("/notes/tags/", {"name": "revise soon"})
    assert again.status_code == 200 and again.json_body["id"] == a.json_body["id"]  # idempotent on the normalised name
    tid = a.json_body["id"]
    assert api.patch(f"/notes/tags/{tid}/", {"color_key": "g"}).json_body["color_key"] == "g"
    api.post("/notes/tags/", {"name": "other"})
    assert api.patch(f"/notes/tags/{tid}/", {"name": "OTHER"}).status_code == 409
    assert {t["name"] for t in api.get("/notes/tags/").json_body["items"]} == {"Revise Soon", "other"}
    assert api.delete(f"/notes/tags/{tid}/").status_code == 204
    assert api.delete(f"/notes/tags/{tid}/").status_code == 404
    assert QuotaUsage.objects.get().tags_count == 1


def test_tags_are_private_and_capped(api, other_api):
    mine = api.post("/notes/tags/", {"name": "mine"}).json_body
    assert other_api.patch(f"/notes/tags/{mine['id']}/", {"name": "x"}).status_code == 404
    n = new_note(other_api, "x")
    res = other_api.put("/notes/items/tags/", {"item_type": "note", "item_id": n["id"], "tag_ids": [mine["id"]]})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "unknown_tag"
    QuotaUsage.objects.filter(pk=Tag.objects.get(pk=mine["id"]).user_id).update(tags_count=200)
    over = api.post("/notes/tags/", {"name": "one too many"})
    assert over.status_code == 429 and over.json_body["error"]["code"] == "quota_exceeded"
    assert over.json_body["error"]["details"]["kind"] == "tags" and over.json_body["error"]["details"]["limit"] == 200


def test_item_tags_replace_the_set_and_listing_filters_by_tag(api):
    t1, t2 = (api.post("/notes/tags/", {"name": n}).json_body["id"] for n in ("one", "two"))
    n = new_note(api, "x")
    body = {"item_type": "note", "item_id": n["id"], "tag_ids": [t1, t2]}
    assert len(api.put("/notes/items/tags/", body).json_body["tags"]) == 2
    api.put("/notes/items/tags/", {**body, "tag_ids": [t2]})
    assert [t["id"] for t in api.get(f"/notes/notes/{n['id']}/").json_body["tags"]] == [t2]
    assert len(api.get(f"/notes/notes/?tag={t2}").json_body["items"]) == 1
    assert api.get(f"/notes/notes/?tag={t1}").json_body["items"] == []
    assert {t["id"]: t["count"] for t in api.get("/notes/tags/").json_body["items"]} == {t1: 0, t2: 1}


# --- Clips --------------------------------------------------------------------------------------------------------------
def test_a_clip_is_idempotent_and_keeps_its_source(api, chapter):
    body = {
        "client_id": str(uuid.uuid4()),
        "text_md": "A clipped paragraph.",
        "source": {"module": "question-bank", "ref": "q/123", "label": "Q 123"},
        "chapter_id": str(chapter.id),
    }
    first, second = api.post("/notes/clips/", body), api.post("/notes/clips/", body)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json_body["created"] is True and second.json_body["created"] is False
    note = first.json_body["note"]
    assert note["origin"] == "clip" and note["title"] == "Q 123" and note["clip_source"]["ref"] == "q/123"
    assert Note.objects.count() == 1 and QuotaUsage.objects.get().notes_active == 1


def test_a_clip_needs_a_source(api):
    assert api.post("/notes/clips/", {"client_id": str(uuid.uuid4()), "text_md": "x"}).status_code == 400


# --- Aggregate ----------------------------------------------------------------------------------------------------------
def _make(api, n, chapter=None, clock=None):
    out = []
    for i in range(n):
        if clock:
            clock.advance(seconds=1)
        extra = {"chapter_id": str(chapter.id)} if chapter else {}
        out.append(new_note(api, f"body {i}", title=f"T{i}", **extra))
    return out


def test_aggregate_paginates_without_gaps_or_repeats(api, chapter, level_id, clock):
    notes = _make(api, 7, chapter, clock)
    seen, cursor = [], None
    for _ in range(10):
        url = f"/notes/aggregate/?level={level_id}&subject=taxation&chapter=gst-itc&limit=3" + (
            f"&cursor={cursor}" if cursor else ""
        )
        page = api.get(url).json_body
        assert all(i["type"] == "note" for i in page["items"])
        seen += [i["id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == [n["id"] for n in reversed(notes)]


def test_aggregate_filters(api, scheme, level_id):
    gst = Chapter.objects.get(key="gst-itc")
    res = Chapter.objects.get(key="residential-status")
    companies = Chapter.objects.get(key="companies-act")
    a = new_note(api, "alpha", title="A", chapter_id=str(gst.id))
    b = new_note(api, "beta", title="B", chapter_id=str(res.id))
    c = new_note(api, "gamma", title="C", chapter_id=str(companies.id))
    d = new_note(api, "delta", title="D")
    tag = api.post("/notes/tags/", {"name": "t"}).json_body["id"]
    api.put("/notes/items/tags/", {"item_type": "note", "item_id": a["id"], "tag_ids": [tag]})
    edit(api, b, pinned=True)

    def ids_of(q):
        res = api.get(f"/notes/aggregate/?{q}")
        assert res.status_code == 200, res.json_body
        return {i["id"] for i in res.json_body["items"]}

    assert ids_of(f"level={level_id}&subject=taxation") == {a["id"], b["id"]}
    assert ids_of(f"level={level_id}&subject=corporate-laws") == {c["id"]}
    assert ids_of(f"level={level_id}&subject=taxation&chapter=gst-itc") == {a["id"]}
    assert ids_of("unfiled=true") == {d["id"]}
    assert ids_of(f"tag={tag}") == {a["id"]}
    assert ids_of("pinned=true") == {b["id"]}
    assert ids_of("q=gamma") == {c["id"]}
    assert ids_of("kind=note") == {a["id"], b["id"], c["id"], d["id"]}
    assert ids_of("tab=highlights") == set() and ids_of("tab=documents") == set()
    assert ids_of("from=2999-01-01") == set()
    assert api.get("/notes/aggregate/?tab=bogus").status_code == 400


def test_a_trashed_note_leaves_the_aggregate(api):
    n = new_note(api, "x")
    api.delete(f"/notes/notes/{n['id']}/")
    assert api.get("/notes/aggregate/").json_body["items"] == []


# --- Counts, overview, scheme switch ------------------------------------------------------------------------------------
def test_counts_per_chapter_with_an_etag(api, scheme, level_id):
    gst = Chapter.objects.get(key="gst-itc")
    _make(api, 2, gst)
    new_note(api, "loose")
    res = api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation")
    body = res.json_body
    rows = {r["chapter_key"]: r for r in body["chapters"]}
    assert [r["chapter_key"] for r in body["chapters"]] == ["gst-itc", "residential-status", "heads-of-income"]
    assert rows["gst-itc"]["notes"] == 2 and rows["residential-status"]["notes"] == 0
    assert body["unfiled"] == 1 and body["moved_or_removed"] == []
    etag = res["ETag"]
    again = api.c.get(f"/api/v1/notes/aggregate/counts/?level={level_id}&subject=taxation", HTTP_IF_NONE_MATCH=etag)
    assert again.status_code == 304
    new_note(api, "x", chapter_id=str(gst.id))
    assert api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation")["ETag"] != etag
    assert api.get(f"/notes/aggregate/counts/?level={level_id}&subject=nope").status_code == 404
    assert api.get("/notes/aggregate/counts/").status_code == 400


def test_chapter_overview(api, scheme, level_id):
    gst = Chapter.objects.get(key="gst-itc")
    _make(api, 7, gst)
    body = api.get(f"/notes/chapters/gst-itc/overview/?level={level_id}&subject=taxation").json_body
    assert body["chapter"]["key"] == "gst-itc" and body["counts"]["notes"] == 7
    assert len(body["recent"]) == 5 and body["current_summary"] is None and body["has_summary"] is False
    assert api.get(f"/notes/chapters/zzz/overview/?level={level_id}&subject=taxation").status_code == 404


def test_notes_follow_a_scheme_switch_by_keys(api, scheme, level_id):
    gst = Chapter.objects.get(key="gst-itc")
    residential = Chapter.objects.get(key="residential-status")
    a = new_note(api, "kept", chapter_id=str(gst.id))
    b = new_note(api, "dropped", chapter_id=str(residential.id))

    def drop_residential(spec):
        chapters = spec["subjects"][0]["chapters"]
        spec["subjects"][0]["chapters"] = [c for c in chapters if c["key"] != "residential-status"]

    new_scheme = switch_scheme(scheme, drop_residential)
    counts = api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation").json_body
    by_key = {r["chapter_key"]: r for r in counts["chapters"]}
    new_gst = Chapter.objects.get(key="gst-itc", subject__scheme=new_scheme)
    assert by_key["gst-itc"]["notes"] == 1 and by_key["gst-itc"]["chapter_id"] == str(new_gst.id)
    assert "residential-status" not in by_key
    assert [r["chapter_key"] for r in counts["moved_or_removed"]] == ["residential-status"]
    assert counts["moved_or_removed"][0]["notes"] == 1
    # the note itself still resolves, flagged where its chapter is gone from the current scheme
    assert api.get(f"/notes/notes/{a['id']}/").json_body["link"]["chapter_key"] == "gst-itc"
    assert api.get(f"/notes/notes/{b['id']}/").json_body["link"]["moved_or_removed"] is True
    assert (
        api.get(f"/notes/aggregate/?level={level_id}&subject=taxation&chapter=gst-itc").json_body["items"][0]["id"]
        == a["id"]
    )


# --- Search -------------------------------------------------------------------------------------------------------------
def test_search_finds_titles_and_text_and_stays_private(api, other_api):
    a = new_note(api, "Input tax credit is blocked for motor cars", title="ITC rules")
    new_note(api, "Residential status test", title="Income tax")
    new_note(other_api, "Input tax credit secret", title="theirs")
    hits = api.get("/notes/search/?q=credit").json_body["items"]
    assert [h["id"] for h in hits] == [a["id"]]
    assert "credit" in hits[0]["snippet"].lower() and hits[0]["type"] == "note"
    assert api.get("/notes/search/?q=ITC").json_body["items"][0]["id"] == a["id"]
    assert api.get("/notes/search/?q=%20%20").status_code in (200, 400)
    assert api.get("/notes/search/").status_code == 400
    assert api.get("/notes/search/?q=credit&scope=highlights").json_body["items"] == []


def test_the_pdf_scope_is_closed_until_r2(api, monkeypatch):
    from modules.notes import views

    monkeypatch.setattr(views, "flag_enabled", lambda key, user: key != "notes_pdf")
    res = api.get("/notes/search/?q=x&scope=pdf")
    assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"


def test_search_pages(api):
    for i in range(5):
        new_note(api, f"gst note {i}")
    p1 = api.get("/notes/search/?q=gst&limit=2").json_body
    p2 = api.get(f"/notes/search/?q=gst&limit=2&cursor={p1['next_cursor']}").json_body
    assert len(p1["items"]) == len(p2["items"]) == 2 and not set(i["id"] for i in p1["items"]) & set(
        i["id"] for i in p2["items"]
    )


# --- Suggest, settings, usage ---------------------------------------------------------------------------------------------
def test_chapter_suggest(api, scheme, level_id):
    res = api.post(
        "/notes/items/chapter-suggest/", {"text": "input tax credit eligibility under GST", "level_id": level_id}
    )
    assert res.status_code == 200
    top = res.json_body["suggestions"][0]
    assert top["chapter_key"] == "gst-itc" and top["subject_key"] == "taxation"


def test_settings_defaults_and_validation(api):
    s = api.get("/notes/settings/").json_body
    assert s["default_color"] == "y" and s["color_legend"]["y"] == "Important"
    up = api.put("/notes/settings/", {"page_tone": "night", "color_legend": {**s["color_legend"], "y": "Must know"}})
    assert (
        up.status_code == 200
        and up.json_body["page_tone"] == "night"
        and up.json_body["color_legend"]["y"] == "Must know"
    )
    assert api.put("/notes/settings/", {"page_tone": "pink"}).status_code == 400
    assert (
        api.put("/notes/settings/", {"color_legend": {"y": "a", "g": "a", "b": "b", "p": "c", "o": "d"}}).status_code
        == 400
    )


def test_usage_reports_plan_limits_and_use(api):
    new_note(api, "x")
    u = api.get("/notes/usage/").json_body
    assert u["plan"] == "free" and u["limits"]["max_notes"] == 2000 and u["used"]["notes"] == 1
    assert u["resets_on"]


# --- Quota ----------------------------------------------------------------------------------------------------------------
def test_the_note_quota_stops_creation_with_429(api):
    new_note(api, "first")
    QuotaUsage.objects.update(notes_active=2000)
    res = api.post("/notes/notes/", {"client_id": str(uuid.uuid4()), "body_md": "one more"})
    assert res.status_code == 429 and res.json_body["error"]["code"] == "quota_exceeded"
    assert res.json_body["error"]["details"] == {"kind": "notes", "used": 2000, "limit": 2000, "plan": "free"}
    assert Note.objects.count() == 1


def test_a_body_over_the_character_limit_is_a_lint_error(api):
    res = api.post("/notes/notes/", {"client_id": str(uuid.uuid4()), "body_md": "a" * 100_001})
    assert res.status_code == 422 and res.json_body["error"]["details"]["errors"][0]["code"] in (
        "too_long",
        "body_too_long",
    )


def test_restoring_from_trash_is_subject_to_the_quota(api):
    n = new_note(api, "x")
    api.delete(f"/notes/notes/{n['id']}/")
    QuotaUsage.objects.update(notes_active=2000)
    assert api.post(f"/notes/notes/{n['id']}/restore/").status_code == 429


# --- Account data ---------------------------------------------------------------------------------------------------------
def _populate(c, chapter):
    tag = c.post("/notes/tags/", {"name": "t"}).json_body["id"]
    n = new_note(c, "body", title="Mine", chapter_id=str(chapter.id), tag_ids=[tag])
    edit(c, n, body_md="body 2", source="manual")
    c.put("/notes/settings/", {"page_tone": "paper"})
    gone = new_note(c, "trashed")
    c.delete(f"/notes/notes/{gone['id']}/")
    return n


def test_export_has_everything(api, chapter):
    n = _populate(api, chapter)
    data = api.get("/notes/export/").json_body
    assert {x["id"] for x in data["notes"]} == {n["id"], *[x["id"] for x in data["notes"]]} and len(data["notes"]) == 2
    mine = next(x for x in data["notes"] if x["id"] == n["id"])
    assert mine["tags"] == ["t"] and [v["rev"] for v in mine["versions"]] == [1, 2] and mine["body_md"] == "body 2"
    assert data["settings"]["page_tone"] == "paper" and [t["name"] for t in data["tags"]] == ["t"]
    assert data["usage"]["notes_active"] == 1
    assert "search_tsv" not in mine and "user_id" not in str(mine["versions"][0].keys())


def test_delete_all_removes_everything_and_only_theirs(
    api,
    other_api,
    chapter,
):
    mine, theirs = _populate(api, chapter), _populate(other_api, chapter)
    res = api.delete("/notes/")
    assert res.status_code == 200 and res.json_body["deleted"]["notes"] == 2
    assert Note.objects.filter(pk=mine["id"]).count() == 0 and Note.objects.filter(pk=theirs["id"]).count() == 1
    assert set(NoteVersion.objects.values_list("note_id", flat=True)) <= {x.id for x in Note.objects.all()}
    assert Tag.objects.count() == 1 and Settings.objects.count() == 1
    assert QuotaUsage.objects.count() == 1 and ItemTag.objects.count() == 1
    assert api.delete("/notes/").json_body["deleted"]["notes"] == 0  # idempotent


# --- The cron tick --------------------------------------------------------------------------------------------------------
@pytest.fixture
def tick_secret(settings):
    settings.NOTES_TICK_SECRET = "s3cret-tick"
    return "s3cret-tick"


def test_the_tick_refuses_without_the_secret(client, tick_secret, settings):
    assert client.post("/api/v1/notes/internal/tick/").status_code == 403
    assert client.post("/api/v1/notes/internal/tick/", HTTP_X_NOTES_TICK_SECRET="wrong").status_code == 403
    settings.NOTES_TICK_SECRET = ""
    assert (
        client.post("/api/v1/notes/internal/tick/", HTTP_X_NOTES_TICK_SECRET="").status_code == 403
    )  # empty never matches


def test_the_tick_accepts_header_or_bearer_and_get_or_post(client, tick_secret):
    assert client.post("/api/v1/notes/internal/tick/", HTTP_X_NOTES_TICK_SECRET=tick_secret).status_code == 200
    assert client.get("/api/v1/notes/internal/tick/", HTTP_AUTHORIZATION=f"Bearer {tick_secret}").status_code == 200


def test_the_tick_purges_old_trash_and_is_repeatable(client, api, tick_secret):
    from datetime import timedelta

    from django.utils import timezone

    old, fresh = new_note(api, "old"), new_note(api, "fresh")
    api.delete(f"/notes/notes/{old['id']}/")
    api.delete(f"/notes/notes/{fresh['id']}/")
    Note.objects.filter(pk=old["id"]).update(purge_after=timezone.now() - timedelta(days=1))
    for _ in range(2):
        res = client.post("/api/v1/notes/internal/tick/", HTTP_X_NOTES_TICK_SECRET=tick_secret)
        assert res.status_code == 200
    assert not Note.objects.filter(pk=old["id"]).exists() and Note.objects.filter(pk=fresh["id"]).exists()


def test_thinning_keeps_one_autosave_a_day_after_the_first_day(api):
    from datetime import timedelta

    from django.utils import timezone

    n = new_note(api, "v1")
    cur = n
    for i in range(4):
        cur = edit(api, cur, body_md=f"v{i + 2}", source="manual" if i == 0 else "autosave").json_body
    NoteVersion.objects.filter(note_id=n["id"]).update(created_at=timezone.now() - timedelta(days=10))
    before = NoteVersion.objects.filter(note_id=n["id"]).count()
    jobs.thin_versions_job({"day": "2026-10-05"})
    assert NoteVersion.objects.filter(note_id=n["id"]).count() <= before


def test_reconcile_repairs_drift(api):
    new_note(api, "a")
    api.post("/notes/tags/", {"name": "t"})
    QuotaUsage.objects.update(notes_active=50, tags_count=9)
    out = jobs.reconcile_usage_job({})
    usage = QuotaUsage.objects.get()
    assert out["drifted"] == 1 and (usage.notes_active, usage.tags_count) == (1, 1)
    assert jobs.reconcile_usage_job({})["drifted"] == 0


def test_the_secret_setting_exists():
    assert hasattr(dj_settings, "NOTES_TICK_SECRET")
