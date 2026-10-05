"""Admin: drag-and-drop ordering endpoint, chapter targets in the list, and the chapter-map review queue."""

import json
import re
from decimal import Decimal

import pytest
from django.contrib.admin.models import LogEntry
from django.urls import reverse

from modules.syllabus import services
from modules.syllabus.models import Chapter, ChapterMap, Scheme, Subject, Topic

from .helpers import make_scheme

pytestmark = pytest.mark.django_db


def post_order(client, model: str, ids):
    return client.post(
        reverse(f"admin:syllabus_{model}_reorder"),
        data=json.dumps({"ids": [str(i) for i in ids]}),
        content_type="application/json",
    )


def order_of(model, **filters):
    return [o.key for o in model.objects.filter(**filters).order_by("sort_order", "key")]


# --- reorder endpoint -------------------------------------------------------------------------


def test_papers_can_be_reordered(admin_client, scheme):
    taxation = Subject.objects.get(scheme=scheme, key="taxation")
    laws = Subject.objects.get(scheme=scheme, key="corporate-laws")
    assert order_of(Subject, scheme=scheme) == ["taxation", "corporate-laws"]

    res = post_order(admin_client, "subject", [laws.id, taxation.id])

    assert res.status_code == 200
    body = res.json()
    assert body["orders"] == {str(laws.id): 0, str(taxation.id): 1} and body["published"] is False
    assert order_of(Subject, scheme=scheme) == ["corporate-laws", "taxation"]


def test_chapters_and_topics_can_be_reordered(admin_client, scheme):
    gst, residential, heads = (Chapter.objects.get(key=k) for k in ("gst-itc", "residential-status", "heads-of-income"))
    assert post_order(admin_client, "chapter", [heads.id, gst.id, residential.id]).status_code == 200
    assert order_of(Chapter, subject=gst.subject) == ["heads-of-income", "gst-itc", "residential-status"]

    topics = list(gst.topics.order_by("sort_order"))
    assert post_order(admin_client, "topic", [t.id for t in reversed(topics)]).status_code == 200
    assert order_of(Topic, chapter=gst) == [t.key for t in reversed(topics)]


def test_reordering_a_page_slice_keeps_the_rows_that_were_not_on_the_page_in_place(admin_client, scheme):
    gst, residential, heads = (Chapter.objects.get(key=k) for k in ("gst-itc", "residential-status", "heads-of-income"))
    # only the first and last chapter are on the page: they swap slots, the one between stays between
    assert post_order(admin_client, "chapter", [heads.id, gst.id]).status_code == 200
    assert order_of(Chapter, subject=gst.subject) == ["heads-of-income", "residential-status", "gst-itc"]


def test_reordering_renumbers_siblings_that_shared_a_sort_order(admin_client, scheme):
    Chapter.objects.filter(subject__key="taxation").update(sort_order=0)  # every sibling tied, as after a bulk add
    gst, residential, heads = (Chapter.objects.get(key=k) for k in ("gst-itc", "residential-status", "heads-of-income"))
    assert post_order(admin_client, "chapter", [heads.id, residential.id, gst.id]).status_code == 200
    assert sorted(Chapter.objects.filter(subject=gst.subject).values_list("sort_order", flat=True)) == [0, 1, 2]
    assert order_of(Chapter, subject=gst.subject) == ["heads-of-income", "residential-status", "gst-itc"]


def test_reorder_refuses_rows_from_different_parents(admin_client, scheme):
    gst = Chapter.objects.get(key="gst-itc")
    companies = Chapter.objects.get(key="companies-act")
    res = post_order(admin_client, "chapter", [gst.id, companies.id])
    assert res.status_code == 400 and "paper" in res.json()["error"].lower()


def test_reorder_rejects_bad_input_and_missing_rows(admin_client, scheme):
    url = reverse("admin:syllabus_chapter_reorder")
    assert admin_client.get(url).status_code == 405
    assert admin_client.post(url, "not json", content_type="application/json").status_code == 400
    assert admin_client.post(url, json.dumps({"ids": ["nope"]}), content_type="application/json").status_code == 400
    assert admin_client.post(url, json.dumps({"ids": []}), content_type="application/json").status_code == 400
    gst = Chapter.objects.get(key="gst-itc")
    assert post_order(admin_client, "chapter", [gst.id, gst.id]).status_code == 400  # duplicates
    assert post_order(admin_client, "chapter", ["3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11"]).status_code == 404


def test_reorder_needs_a_staff_login_and_the_change_permission(client, staff_client, scheme):
    gst = Chapter.objects.get(key="gst-itc")
    # editors may change chapters
    assert post_order(staff_client, "chapter", [gst.id]).status_code == 200
    # a staff user without any syllabus permission may not
    from django.contrib.auth.models import User

    client.force_login(User.objects.create_user("nobody", "n@example.com", "pw", is_staff=True))
    assert post_order(client, "chapter", [gst.id]).status_code == 403


def test_anonymous_visitors_cannot_reorder(client, scheme):
    gst = Chapter.objects.get(key="gst-itc")
    res = post_order(client, "chapter", [gst.id])
    assert res.status_code == 302 and "login" in res["Location"]


def test_reordering_is_logged_and_flags_a_published_scheme(admin_client, scheme):
    services.publish_scheme(scheme)
    taxation = Subject.objects.get(scheme=scheme, key="taxation")
    laws = Subject.objects.get(scheme=scheme, key="corporate-laws")
    res = post_order(admin_client, "subject", [laws.id, taxation.id])
    assert res.json()["published"] is True
    assert LogEntry.objects.filter(object_id=str(laws.pk), change_message__contains="Moved to position 1").exists()


def test_changelists_tell_the_page_whether_dragging_is_available(admin_client, scheme):
    def config(url, params=None):
        page = admin_client.get(url, params or {})
        raw = re.search(r'<script id="reorder-config" type="application/json">(.*?)</script>', page.content.decode())
        return json.loads(raw.group(1))

    papers = reverse("admin:syllabus_subject_changelist")
    assert config(papers)["enabled"] is False and "scheme" in config(papers)["hint"].lower()
    pinned = config(papers, {"scheme__id__exact": str(scheme.id)})
    assert pinned["enabled"] is True and pinned["url"] == reverse("admin:syllabus_subject_reorder")

    laws = Subject.objects.get(key="corporate-laws")
    chapters = reverse("admin:syllabus_chapter_changelist")
    assert config(chapters, {"subject__scheme__id__exact": str(scheme.id)})["enabled"] is False
    assert config(chapters, {"subject__scheme__id__exact": str(scheme.id), "paper": str(laws.id)})["enabled"] is True


def test_the_ordering_script_and_style_are_served_with_the_admin(client, admin_client, scheme):
    page = admin_client.get(reverse("admin:syllabus_scheme_change", args=[scheme.pk])).content.decode()
    assert "syllabus/admin/reorder.js" in page and "syllabus/admin/reorder.css" in page
    assert client.get("/static/syllabus/admin/reorder.js").status_code == 200
    assert client.get("/static/syllabus/admin/reorder.css").status_code == 200


# --- chapter targets in the list --------------------------------------------------------------


def list_post(chapters, overrides):
    """The POST body of the Chapters list's Save button for `chapters` (every editable column), with `overrides`."""
    data = {
        "form-TOTAL_FORMS": len(chapters),
        "form-INITIAL_FORMS": len(chapters),
        "form-MIN_NUM_FORMS": 0,
        "form-MAX_NUM_FORMS": 1000,
    }
    for i, c in enumerate(chapters):
        row = {
            "id": c.pk,
            "marks_min": c.marks_min if c.marks_min is not None else "",
            "marks_max": c.marks_max if c.marks_max is not None else "",
            "weight_source": c.weight_source,
            "target_practice_sets": c.target_practice_sets,
            "target_revisions": c.target_revisions,
            "target_mocks": c.target_mocks,
            "sort_order": c.sort_order,
            "is_active": "on",
            **overrides.get(c.pk, {}),
        }
        data.update({f"form-{i}-{k}": v for k, v in row.items()})
    data["_save"] = "Save"
    return data


def test_chapter_targets_are_columns_you_can_edit_in_the_list(admin_client, scheme):
    url = reverse("admin:syllabus_chapter_changelist")
    page = admin_client.get(url, {"subject__scheme__id__exact": str(scheme.id)})
    content = page.content.decode()
    for field in ("target_practice_sets", "target_revisions", "target_mocks"):
        assert f"-{field}" in content  # an input per row

    chapters = list(Chapter.objects.filter(subject__scheme=scheme).order_by("pk"))
    gst = next(c for c in chapters if c.key == "gst-itc")
    res = admin_client.post(
        url,
        list_post(chapters, {gst.pk: {"target_practice_sets": 4, "target_revisions": 3, "target_mocks": 2}}),
        follow=True,
    )
    assert res.status_code == 200
    gst.refresh_from_db()
    assert (gst.target_practice_sets, gst.target_revisions, gst.target_mocks) == (4, 3, 2)
    others = Chapter.objects.exclude(pk=gst.pk).filter(subject__scheme=scheme)
    assert {c.target_revisions for c in others} == {2}  # untouched


def test_targets_outside_zero_to_twenty_are_rejected_in_the_list(admin_client, scheme):
    chapters = list(Chapter.objects.filter(subject__scheme=scheme).order_by("pk"))
    gst = next(c for c in chapters if c.key == "gst-itc")
    res = admin_client.post(
        reverse("admin:syllabus_chapter_changelist"),
        list_post(chapters, {gst.pk: {"target_mocks": 21}}),
    )
    assert res.status_code == 200  # the list re-renders with the error
    gst.refresh_from_db()
    assert gst.target_mocks == 1


# --- chapter map review queue -----------------------------------------------------------------


def two_schemes_with_a_doubtful_match():
    old = make_scheme(code="2023", publish=True)
    from copy import deepcopy

    from .helpers import SPEC

    spec = deepcopy(SPEC)
    spec["subjects"][0]["chapters"][2].update(key="income-heads", name="Heads of income: overview and classification")
    new = make_scheme(code="2025", publish=False, spec=spec)
    return old, new


def test_build_chapter_map_action_reports_what_needs_review(admin_client):
    _, new = two_schemes_with_a_doubtful_match()
    res = admin_client.post(
        reverse("admin:syllabus_scheme_changelist"),
        {"action": "build_chapter_map", "_selected_action": [str(new.pk)]},
        follow=True,
    )
    text = " ".join(str(m) for m in res.context["messages"])
    assert "Created 4 chapter maps" in text and "1 need your review" in text
    assert ChapterMap.objects.filter(needs_review=True).count() == 1


def test_review_queue_lists_doubtful_rows_first_and_can_be_filtered(admin_client):
    old, new = two_schemes_with_a_doubtful_match()
    services.build_default_chapter_map(old, new)
    page = admin_client.get(reverse("admin:syllabus_chaptermap_changelist"))
    rows = list(page.context["cl"].result_list)
    assert rows[0].needs_review and not any(r.needs_review for r in rows[1:])
    only = admin_client.get(reverse("admin:syllabus_chaptermap_changelist"), {"needs_review__exact": "1"})
    assert only.context["cl"].result_count == 1


def test_mark_reviewed_action_clears_the_flag(admin_client):
    old, new = two_schemes_with_a_doubtful_match()
    services.build_default_chapter_map(old, new)
    flagged = ChapterMap.objects.get(needs_review=True)
    admin_client.post(
        reverse("admin:syllabus_chaptermap_changelist"),
        {"action": "mark_reviewed", "_selected_action": [str(flagged.pk)]},
    )
    flagged.refresh_from_db()
    assert not flagged.needs_review and flagged.basis == "renamed"  # still records how it was proposed


def test_editing_a_proposed_row_takes_it_out_of_the_queue(admin_client):
    old, new = two_schemes_with_a_doubtful_match()
    services.build_default_chapter_map(old, new)
    flagged = ChapterMap.objects.get(needs_review=True)
    res = admin_client.post(
        reverse("admin:syllabus_chaptermap_change", args=[flagged.pk]),
        {
            "from_chapter": flagged.from_chapter_id,
            "to_chapter": flagged.to_chapter_id,
            "relation": "partial",
            "carry_ratio": "0.50",
        },
    )
    assert res.status_code == 302
    flagged.refresh_from_db()
    assert flagged.relation == "partial" and flagged.carry_ratio == Decimal("0.50") and not flagged.needs_review


def test_publishing_warns_when_maps_into_the_scheme_still_need_review(admin_client):
    old, new = two_schemes_with_a_doubtful_match()
    services.retire_scheme(old)
    services.build_default_chapter_map(old, new)
    res = admin_client.post(
        reverse("admin:syllabus_scheme_changelist"),
        {"action": "publish_selected", "_selected_action": [str(new.pk)]},
        follow=True,
    )
    new.refresh_from_db()
    assert new.status == Scheme.Status.PUBLISHED
    assert any("still need review" in str(m) for m in res.context["messages"])
