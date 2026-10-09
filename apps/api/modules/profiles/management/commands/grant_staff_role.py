"""
Give a person the platform staff role and, if wanted, a Django admin login: `grant_staff_role --email a@b.c --role editor|admin|student [--admin-login]`.

The role lives on the student's `profiles` row (they must have signed in once). Django admin logins are separate accounts, so
`--admin-login` also creates or updates a staff user with the SAME e-mail address; the recall admin matches the two by that
address (D44). `editor` writes decks, `admin` also publishes. `--role student` takes the role and the admin access away. The
password is read from the environment variable named by `--password-env`, never from the command line; without it the login is
created with an unusable password and the person is given one with `changepassword`.
"""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from modules.profiles import services


class Command(BaseCommand):
    help = "Set profiles.role for a person and optionally create their Django admin login."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--role", required=True, choices=["student", "editor", "admin"])
        parser.add_argument("--admin-login", action="store_true", help="Also create or update the Django staff login.")
        parser.add_argument("--password-env", help="Name of an environment variable holding the initial password.")

    def handle(self, *args, email, role, admin_login=False, password_env=None, **options):
        try:
            profile = services.set_staff_role(email, role)
        except services.StaffRoleError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"profile {profile.id}: role is now {role}")
        User = get_user_model()
        existing = User.objects.filter(email__iexact=email.strip()).order_by("id")
        if role == "student":
            n = existing.filter(is_superuser=False).update(is_staff=False)
            self.stdout.write(f"admin access removed from {n} login(s)" if n else "no admin login to remove")
            return
        if not admin_login:
            self.stdout.write("no admin login touched (add --admin-login to create one)")
            return
        user = existing.first()
        created = user is None
        if created:
            user = User(username=email.strip().lower(), email=email.strip())
        user.is_staff, user.is_active = True, True
        password = os.environ.get(password_env or "") if password_env else None
        if password:
            user.set_password(password)
        elif created:
            user.set_unusable_password()
        user.save()
        self.stdout.write(f"admin login {'created' if created else 'updated'}: {user.username}")
        if created and not password:
            self.stdout.write("it has no password yet: run `python manage.py changepassword " + user.username + "`")
