"""
Runs the API for the R3 end-to-end check with PostHog answered locally: `notes_ai` is ON for everyone, which is the only way a
fail-closed flag can be opened without a PostHog project. Usage: `python serve.py 127.0.0.1:18000` (from `apps/api`).
"""

import os
import sys

sys.path.insert(0, os.getcwd())  # run from apps/api: the script's own folder is what Python puts on the path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["POSTHOG_API_KEY"] = "e2e"

import django  # noqa: E402
from django.core.management import call_command  # noqa: E402

from core import feature_flags  # noqa: E402


class On:
    def get_feature_flag(self, key, distinct_id, **kwargs):
        return True


django.setup()
feature_flags._client = On()
call_command("runserver", sys.argv[1], "--noreload")
