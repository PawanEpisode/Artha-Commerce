"""R2-W2: a scheme switch carries her own cards through the chapter map (FR-F15-50)."""

from __future__ import annotations

import pytest

from core import events
from core import jobs as core_jobs
from modules.coverage.tests.conftest import USER as ME
from modules.recall import jobs as recall_jobs
from modules.recall import subscribers
from modules.recall.adapters import syllabus as syllabus_adapter
from modules.recall.domain import remap as dm
from modules.recall.models import RecallChapterRemap, RecallItem
from modules.recall.services import remap as remap_service
from modules.syllabus.models import Chapter, ChapterMap
from modules.syllabus.tests.helpers import switch_scheme

from .factories import make_card, make_item, reviewed_fields

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------------------------------ pure rules
def row(to, rel="same", review=False):
    return dm.MapRow(to, rel, review)


def test_one_confirmed_row_maps_and_a_split_or_several_rows_choose():
    assert dm.decide([row("a")]) == dm.Decision(dm.MAP, "same", "a")
    assert dm.decide([row("a", "merged")]).action == dm.MAP
    assert dm.decide([row("a", "partial")]).action == dm.MAP
    split = dm.decide([row("b", "split"), row("a", "split")])
    assert split.action == dm.CHOOSE and split.relation == "split" and split.candidates == ("a", "b")
    assert dm.decide([row("a", "same"), row("b", "same")]).action == dm.CHOOSE
    assert dm.decide([row("a", "split")]).action == dm.CHOOSE


def test_unconfirmed_rows_are_suggestions_only():
    assert dm.decide([row("a", "same", True)]) == dm.Decision(dm.PARK, "none", None, ("a",))
    d = dm.decide([row("a"), row("b", "same", True)])
    assert d.action == dm.MAP and d.to_chapter_id == "a"
    assert dm.decide([]) == dm.Decision(dm.PARK, "none", None, ())
    d = dm.decide([row("a", "split"), row("c", "split"), row("b", "same", True)])
    assert d.candidates == ("a", "c", "b")


# ---------------------------------------------------------------------------------------------- service
@pytest.fixture
def two(scheme):
    new = switch_scheme(scheme)
    old = {c.key: c for c in Chapter.objects.filter(subject__scheme=scheme)}
    nw = {c.key: c for c in Chapter.objects.filter(subject__scheme=new)}
    return scheme, new, old, nw


def own(chapter):
    item = make_item(ME)
    RecallItem.objects.filter(pk=item.pk).update(**syllabus_adapter.link_columns(chapter.id))
    return make_card(item, ME, chapter_id=chapter.id, **reviewed_fields(10.0)), item


def mapping(a, b, rel="same", review=False):
    ChapterMap.objects.update_or_create(
        from_chapter=a, to_chapter=b, defaults={"relation": rel, "needs_review": review}
    )


def test_a_single_confirmed_row_moves_the_card_and_keeps_its_memory(two):
    scheme, new, old, nw = two
    card, item = own(old["gst-itc"])
    ChapterMap.objects.filter(from_chapter=old["gst-itc"]).delete()
    mapping(old["gst-itc"], nw["gst-itc"])
    before = (card.stability, card.due_at, card.state)
    res = remap_service.remap_student(ME, new.id)
    assert res.moved == 1 and res.waiting == 0
    card.refresh_from_db()
    assert card.chapter_id == nw["gst-itc"].id and (card.stability, card.due_at, card.state) == before
    assert card.rev >= 1
    assert RecallItem.objects.get(pk=item.pk).scheme_id == new.id
    again = remap_service.remap_student(ME, new.id)
    assert again.moved == 0 and again.unchanged == 1  # idempotent


def test_a_split_waits_for_her_choice_and_choosing_is_safe_to_repeat(two, api):
    scheme, new, old, nw = two
    card, item = own(old["residential-status"])
    ChapterMap.objects.filter(from_chapter=old["residential-status"]).delete()
    mapping(old["residential-status"], nw["residential-status"], "split")
    mapping(old["residential-status"], nw["heads-of-income"], "split")
    res = remap_service.remap_student(ME, new.id)
    assert res.waiting == 1 and res.moved == 0
    card.refresh_from_db()
    assert card.chapter_id == old["residential-status"].id  # not moved
    screen = api.get("/recall/chapter-remaps/").json_body
    assert len(screen["items"]) == 1 and screen["items"][0]["relation"] == "split"
    assert {c["key"] for c in screen["items"][0]["candidates"]} == {"residential-status", "heads-of-income"}
    todo = RecallChapterRemap.objects.get(item=item)
    waiting = api.get("/recall/cards/?state=needs_chapter")
    assert waiting.status_code == 200 and len(waiting.json_body["items"]) == 1
    body = {"chapter_id": str(nw["heads-of-income"].id)}
    assert api.post(f"/recall/chapter-remaps/{todo.id}/choose/", body).status_code == 200
    assert api.post(f"/recall/chapter-remaps/{todo.id}/choose/", body).status_code == 200
    card.refresh_from_db()
    assert card.chapter_id == nw["heads-of-income"].id
    assert api.get("/recall/chapter-remaps/").json_body["items"] == []


def test_a_chapter_of_another_scheme_is_refused_and_another_students_row_is_404(two, api, other_api):
    scheme, new, old, nw = two
    card, item = own(old["gst-itc"])
    ChapterMap.objects.filter(from_chapter=old["gst-itc"]).delete()
    remap_service.remap_student(ME, new.id)  # no map: parked
    todo = RecallChapterRemap.objects.get(item=item)
    assert todo.relation == "none"
    res = api.post(f"/recall/chapter-remaps/{todo.id}/choose/", {"chapter_id": str(old["gst-itc"].id)})
    assert res.status_code == 422
    assert (
        other_api.post(f"/recall/chapter-remaps/{todo.id}/choose/", {"chapter_id": str(nw["gst-itc"].id)}).status_code
        == 404
    )
    assert api.post(f"/recall/chapter-remaps/{todo.id}/choose/", {}).status_code == 400


def test_an_unconfirmed_row_is_ignored_for_the_decision(two):
    scheme, new, old, nw = two
    card, item = own(old["gst-itc"])
    ChapterMap.objects.filter(from_chapter=old["gst-itc"]).delete()
    mapping(old["gst-itc"], nw["gst-itc"], review=True)
    res = remap_service.remap_student(ME, new.id)
    assert res.waiting == 1
    todo = RecallChapterRemap.objects.get(item=item)
    assert todo.candidate_chapter_ids == [str(nw["gst-itc"].id)]


def test_the_scheme_event_queues_a_job_that_remaps(two):
    scheme, new, old, nw = two
    events.clear()
    subscribers.register()
    card, _ = own(old["gst-itc"])
    ChapterMap.objects.filter(from_chapter=old["gst-itc"]).delete()
    mapping(old["gst-itc"], nw["gst-itc"])
    events.emit("enrollment_scheme_changed", user_id=ME, old_scheme_id=scheme.id, new_scheme_id=new.id)
    events.emit("enrollment_scheme_changed", user_id=ME, old_scheme_id=scheme.id, new_scheme_id=new.id)
    core_jobs.run_pending(types=recall_jobs.LIGHT_TYPES, budget_seconds=20, worker="t")
    card.refresh_from_db()
    assert card.chapter_id == nw["gst-itc"].id
    events.clear()


def test_platform_cards_and_cards_without_a_chapter_are_left_alone(two):
    scheme, new, old, nw = two
    free = make_item(ME)
    make_card(free, ME)
    res = remap_service.remap_student(ME, new.id)
    assert (res.moved, res.waiting) == (0, 0)
