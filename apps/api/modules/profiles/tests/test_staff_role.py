import uuid
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from modules.profiles import selectors, services
from modules.profiles.models import Profile

pytestmark = pytest.mark.django_db


def profile(email="Ed@Example.com", role="student"):
    return Profile.objects.create(id=uuid.uuid4(), email=email, role=role)


def run(*args):
    out = StringIO()
    call_command("grant_staff_role", *args, stdout=out)
    return out.getvalue()


def test_role_for_email_ignores_case_and_is_none_when_missing_or_ambiguous():
    p = profile(role="editor")
    assert (
        selectors.role_for_email("ed@example.com") == "editor"
        and selectors.role_for_email(" ED@example.COM ") == "editor"
    )
    assert selectors.role_for_email("nobody@example.com") is None and selectors.role_for_email("") is None
    profile("ed@example.com", role="admin")
    assert selectors.role_for_email("ed@example.com") is None  # two profiles: never guess
    assert p.pk


def test_set_staff_role_rejects_bad_roles_and_missing_or_duplicate_profiles():
    with pytest.raises(services.StaffRoleError):
        services.set_staff_role("a@b.c", "editor")
    profile("a@b.c")
    with pytest.raises(services.StaffRoleError):
        services.set_staff_role("a@b.c", "superuser")
    profile("A@B.C")
    with pytest.raises(services.StaffRoleError):
        services.set_staff_role("a@b.c", "editor")


def test_the_command_sets_the_role_and_creates_a_matching_staff_login(monkeypatch):
    p = profile("ed@example.com")
    monkeypatch.setenv("NEW_PW", "correct-horse-battery")
    run("--email", "ed@example.com", "--role", "editor", "--admin-login", "--password-env", "NEW_PW")
    p.refresh_from_db()
    user = get_user_model().objects.get(email__iexact="ed@example.com")
    assert (
        p.role == "editor" and user.is_staff and not user.is_superuser and user.check_password("correct-horse-battery")
    )


def test_the_command_without_a_password_leaves_it_unusable():
    profile("ed@example.com")
    run("--email", "ed@example.com", "--role", "admin", "--admin-login")
    assert not get_user_model().objects.get(email__iexact="ed@example.com").has_usable_password()


def test_student_takes_the_access_away_but_never_from_a_superuser():
    profile("ed@example.com", role="editor")
    profile("boss@example.com", role="admin")
    get_user_model().objects.create_user("ed", email="ed@example.com", password="x", is_staff=True)
    get_user_model().objects.create_superuser("boss", email="boss@example.com", password="x")
    run("--email", "ed@example.com", "--role", "student")
    run("--email", "boss@example.com", "--role", "student")
    assert not get_user_model().objects.get(username="ed").is_staff
    assert get_user_model().objects.get(username="boss").is_staff
    assert Profile.objects.get(email="ed@example.com").role == "student"


def test_the_command_fails_clearly_for_someone_who_never_signed_in():
    with pytest.raises(CommandError, match="sign in"):
        run("--email", "ghost@example.com", "--role", "editor")
