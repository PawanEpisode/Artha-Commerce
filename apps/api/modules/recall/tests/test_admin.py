import uuid
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from modules.profiles.models import Profile
from modules.recall.domain import staff
from modules.recall.models import (
    RecallAuditLog,
    RecallItem,
    RecallQuotaPlan,
    RecallReport,
    RecallReviewLog,
)

from .factories import USER, make_card, make_item
from .w11 import draft_deck, platform_item, published_deck

pytestmark = pytest.mark.django_db


def login(role=None, *, superuser=False, staff_flag=True, email=None):
    email = email or f"{uuid.uuid4().hex[:6]}@example.com"
    if role:
        Profile.objects.create(id=uuid.uuid4(), email=email, role=role)
    user = get_user_model().objects.create_user(
        username=email, email=email, password="x", is_staff=staff_flag, is_superuser=superuser
    )
    c = Client()
    c.force_login(user)
    return c


def url(name):
    return f"/admin/recall/{name}/"


def test_scopes_come_from_the_profile_role():
    assert staff.scopes_for("editor") == {staff.AUTHOR}
    assert staff.scopes_for("admin") == {staff.AUTHOR, staff.PUBLISH}
    assert staff.scopes_for("student") == frozenset() and staff.scopes_for(None) == frozenset()
    assert staff.scopes_for(None, is_superuser=True) == {staff.AUTHOR, staff.PUBLISH}


def test_a_staff_login_without_a_matching_role_sees_nothing():
    c = login(None)
    assert c.get(url("recallitem")).status_code == 403
    assert c.get(url("recalldeck")).status_code == 403


def test_a_student_role_and_a_non_staff_login_get_nothing():
    assert login("student").get(url("recallitem")).status_code == 403
    assert login("editor", staff_flag=False).get(url("recallitem")).status_code == 302  # to the admin login


def test_an_editor_sees_platform_items_only_and_never_a_students_card_text():
    platform = platform_item("Platform question")
    mine = make_item(USER, text="My secret card text")
    page = login("editor").get(url("recallitem")).content.decode()
    assert platform.external_ref in page
    assert mine.pk.hex[:8] not in page and str(mine.pk) not in page and "My secret card text" not in page
    assert login("editor").get(f"{url('recallitem')}{mine.pk}/change/").status_code == 302  # not in the queryset


def test_an_editor_can_open_but_not_see_student_state():
    c = login("editor")
    assert c.get(url("recallcard")).status_code == 403
    assert c.get(url("recallauditlog")).status_code == 403
    assert c.get(url("recallquotaplan")).status_code == 403


def test_an_admin_sees_cards_as_ids_and_numbers_and_cannot_edit_them():
    card = make_card(make_item(USER, text="Top secret wording"), owner=USER)
    c = login("admin")
    listing = c.get(url("recallcard")).content.decode()
    assert str(card.id) in listing and "Top secret wording" not in listing
    detail = c.get(f"{url('recallcard')}{card.id}/change/")
    assert detail.status_code == 200 and "Top secret wording" not in detail.content.decode()
    assert c.get(f"{url('recallcard')}add/").status_code == 403
    assert c.post(f"{url('recallcard')}{card.id}/delete/", {"post": "yes"}).status_code == 403


def test_the_review_log_is_a_read_only_page_of_facts():
    now = timezone.now()
    RecallReviewLog.objects.create(
        user_id=USER, id=uuid.uuid4(), card_id=uuid.uuid4(), item_id=uuid.uuid4(), item_version_id=uuid.uuid4(),
        rating=3, reviewed_at=now, received_at=now, local_date=date(2026, 10, 1),
    )  # fmt: skip
    c = login("admin")
    res = c.get(f"{url('recallcard')}review-log/?user={USER}")
    assert res.status_code == 200 and str(USER) in res.content.decode()
    assert c.get(f"{url('recallcard')}review-log/?user=nonsense").status_code == 200
    assert login("editor").get(f"{url('recallcard')}review-log/").status_code in (403, 404)


def test_publishing_from_the_admin_needs_the_publish_scope():
    deck, items, v1 = published_deck(2)
    d2, draft = draft_deck([platform_item("X")], slug="second")
    body = {"changelog_md": "go", "item_refs": "", "_publish": "1"}
    editor = login("editor")
    editor.post(f"{url('recalldeckversion')}{draft.pk}/change/", body)
    d2.refresh_from_db()
    assert d2.live_version_id is None
    admin_client = login("admin")
    res = admin_client.post(f"{url('recalldeckversion')}{draft.pk}/change/", body)
    assert res.status_code == 302
    d2.refresh_from_db()
    assert d2.live_version_id == draft.pk
    assert RecallAuditLog.objects.filter(action="deck_publish", target_id=str(d2.id)).exists()


def test_a_blocked_publish_from_the_admin_changes_nothing():
    d, draft = draft_deck([platform_item("X", rights="unknown")], slug="blocked")
    res = login("admin").post(
        f"{url('recalldeckversion')}{draft.pk}/change/",
        {"changelog_md": "", "item_refs": "", "_publish": "1"},
        follow=True,
    )
    d.refresh_from_db()
    assert d.live_version_id is None and "Not published" in res.content.decode()


def test_the_item_form_creates_a_platform_item_through_the_service():
    c = login("editor")
    res = c.post(
        f"{url('recallitem')}add/",
        {
            "kind": "pointer", "importance": "mandatory", "rights_status": "original", "source_label": "",
            "fields_json": '{"prompt_md": "Why?", "answer_md": "Because."}', "tags": "[]", "reference_keys": "[]",
        },
    )  # fmt: skip
    assert res.status_code == 302, res.content.decode()[:2000]
    item = RecallItem.objects.get(ownership="platform")
    assert item.live_version is None and item.current_version.state == "draft" and item.external_ref.startswith("ed-")


def test_bad_item_fields_are_refused_in_the_form():
    res = login("editor").post(
        f"{url('recallitem')}add/",
        {"kind": "pointer", "importance": "bullet", "rights_status": "original", "fields_json": '{"prompt_md": ""}'},
    )
    assert res.status_code == 200 and RecallItem.objects.count() == 0


def test_report_actions_close_reports_and_flag_items():
    _, items, _ = published_deck(1)
    r = RecallReport.objects.create(target_kind="item", target_id=items[0].id, reporter_user_id=USER, reason="wrong")
    c = login("editor")
    c.post(url("recallreport"), {"action": "flag_items", "_selected_action": [r.pk]})
    assert RecallItem.objects.get(pk=items[0].id).needs_editor_check
    c.post(url("recallreport"), {"action": "mark_actioned", "_selected_action": [r.pk]})
    r.refresh_from_db()
    assert r.status == "actioned" and r.handled_at


def test_a_quota_plan_change_needs_publish_and_writes_an_audit_row():
    plan = RecallQuotaPlan.objects.first()
    assert plan is not None
    assert login("editor").get(f"{url('recallquotaplan')}{plan.pk}/change/").status_code == 403
    c = login("admin")
    page = c.get(f"{url('recallquotaplan')}{plan.pk}/change/")
    assert page.status_code == 200
    data = {
        f: getattr(plan, f)
        for f in (
            "max_cards",
            "max_cards_per_deck",
            "max_decks",
            "max_active_shares",
            "ai_suggestions_per_day",
            "ai_batches_per_day",
            "share_imports_per_day",
            "pack_size",
        )
    }
    data["max_cards"] += 10
    res = c.post(f"{url('recallquotaplan')}{plan.pk}/change/", data)
    assert res.status_code == 302, res.content.decode()[:2000]
    row = RecallAuditLog.objects.get(action="quota_change")
    assert row.detail["changed"] == {"max_cards": data["max_cards"]}
