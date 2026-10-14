"""Operator tools: the sync command and the admin (PRD section 8)."""

import uuid
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from modules.today import registry
from modules.today.models import DayPlan, ProviderConfig

pytestmark = pytest.mark.django_db


def sync(*args):
    out = StringIO()
    call_command("sync_today_providers", *args, stdout=out)
    return out.getvalue()


def test_sync_creates_a_row_for_every_registered_provider_and_is_repeatable():
    names = {p.name for p in registry.providers()}
    assert {"coverage.revision", "coverage.syllabus", "recall.legacy"} <= names
    first = sync()
    assert set(ProviderConfig.objects.values_list("provider", flat=True)) == names and "Created" in first
    ProviderConfig.objects.filter(provider="recall.legacy").update(enabled=False, weight_pct=40, note="too noisy")
    sync()  # a second run keeps what the operator set
    row = ProviderConfig.objects.get(provider="recall.legacy")
    assert (row.enabled, row.weight_pct, row.note) == (False, 40, "too noisy")


def test_sync_dry_run_changes_nothing():
    assert "Would create" in sync("--dry-run") and ProviderConfig.objects.count() == 0


def test_sync_reports_stale_rows_and_prunes_only_when_asked():
    ProviderConfig.objects.create(provider="gone.provider")
    assert "gone.provider" in sync() and ProviderConfig.objects.filter(provider="gone.provider").exists()
    assert (
        "Would delete" in sync("--dry-run", "--prune")
        and ProviderConfig.objects.filter(provider="gone.provider").exists()
    )
    sync("--prune")
    assert not ProviderConfig.objects.filter(provider="gone.provider").exists()


@pytest.fixture
def staff(client):
    user = get_user_model().objects.create_superuser("ops", "ops@example.com", "pw-ops-12345")
    client.force_login(user)
    return client


def test_the_admin_lists_providers_and_edits_them(staff, settings):
    sync()
    base = f"/{settings.ADMIN_PATH.strip('/')}"
    res = staff.get(f"{base}/today/providerconfig/")
    assert res.status_code == 200 and b"recall.legacy" in res.content
    change = staff.post(
        f"{base}/today/providerconfig/recall.legacy/change/",
        {"provider": "recall.legacy", "enabled": "", "weight_pct": 50, "note": "beta"},
    )
    assert change.status_code == 302
    row = ProviderConfig.objects.get(provider="recall.legacy")
    assert row.enabled is False and row.weight_pct == 50


def test_plans_are_visible_read_only_and_never_show_task_text(staff, settings):
    plan = DayPlan.objects.create(user_id=uuid.uuid4(), local_date="2026-10-14", tz="Asia/Kolkata")
    base = f"/{settings.ADMIN_PATH.strip('/')}"
    assert staff.get(f"{base}/today/dayplan/").status_code == 200
    assert staff.get(f"{base}/today/dayplan/add/").status_code == 403
    assert staff.post(f"{base}/today/dayplan/{plan.pk}/delete/", {"post": "yes"}).status_code == 403
    assert reverse("admin:index")
    from django.contrib import admin

    from modules.today.models import Task

    assert Task not in admin.site._registry  # own task titles are personal data
