"""The data migration that marks existing, enrolled students as having finished onboarding version 1."""

import importlib
import uuid

import pytest
from django.apps import apps as django_apps

from modules.coverage.models import Enrollment
from modules.profiles.models import Onboarding, Profile
from modules.profiles.tests.conftest import USER
from modules.syllabus.models import ExamTerm

migration = importlib.import_module("modules.profiles.migrations.0004_backfill_onboarding")

pytestmark = pytest.mark.django_db


def make_enrolment(profile, scheme, status="active"):
    term = ExamTerm.objects.filter(level=scheme.level).first()
    return Enrollment.objects.create(
        user_id=profile.id, scheme=scheme, level=scheme.level, target_term=term, status=status, daily_minutes=120
    )


def make_user(scheme, *, enrolled: bool, status="active"):
    profile = Profile.objects.create(email=f"{uuid.uuid4().hex[:6]}@example.com")
    if enrolled:
        make_enrolment(profile, scheme, status)
    return profile


@pytest.fixture
def three_kinds(scheme):
    return {
        "enrolled": make_user(scheme, enrolled=True),
        "new": make_user(scheme, enrolled=False),
        "archived_only": make_user(scheme, enrolled=True, status="archived"),
    }


def test_only_students_with_an_active_enrolment_are_marked(three_kinds):
    migration.backfill(django_apps, None)
    row = Onboarding.objects.get(pk=three_kinds["enrolled"].id)
    assert row.completed_version == 1 and row.backfilled is True and row.completed_at is not None
    assert not Onboarding.objects.filter(pk=three_kinds["new"].id).exists()
    assert not Onboarding.objects.filter(pk=three_kinds["archived_only"].id).exists()


def test_running_twice_changes_nothing(three_kinds):
    migration.backfill(django_apps, None)
    first = list(Onboarding.objects.values_list("pk", "completed_at"))
    migration.backfill(django_apps, None)
    assert list(Onboarding.objects.values_list("pk", "completed_at")) == first


def test_an_existing_row_is_never_overwritten(three_kinds):
    mine = three_kinds["enrolled"]
    Onboarding.objects.create(user_id=mine.id, completed_version=2, completed_at=mine.created_at)
    migration.backfill(django_apps, None)
    row = Onboarding.objects.get(pk=mine.id)
    assert row.completed_version == 2 and row.backfilled is False


def test_reversing_removes_only_the_rows_it_created(three_kinds):
    migration.backfill(django_apps, None)
    organic = three_kinds["new"]
    Onboarding.objects.create(user_id=organic.id, completed_version=2, completed_at=organic.created_at)
    migration.unbackfill(django_apps, None)
    assert list(Onboarding.objects.values_list("pk", flat=True)) == [organic.id]


def test_a_backfilled_student_is_asked_only_for_what_is_new(api, scheme):
    profile = Profile.objects.create(id=uuid.UUID(USER), email="a@example.com", full_name="Aarav")
    make_enrolment(profile, scheme)
    migration.backfill(django_apps, None)

    body = api.get("/me/onboarding/").json_body

    assert body["mode"] == "update" and body["status"] == "in_progress"
    states = {s["key"]: s["state"] for s in body["steps"]}
    assert states["course"] == "done" and states["targets"] == "todo"
