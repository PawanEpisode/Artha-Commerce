import io
import uuid

import pytest
from django.core.management import CommandError, call_command

from modules.notifications.tests.helpers import register

pytestmark = pytest.mark.django_db
USER = uuid.uuid4()


def run(*args):
    out = io.StringIO()
    call_command("send_test_push", *args, stdout=out)
    return out.getvalue()


def test_sends_a_test_to_each_active_device(fake_push):
    a, b = register(USER).device, register(USER).device
    text = run("--user", str(USER))
    assert f"{a.id}: sent" in text and f"{b.id}: sent" in text and len(fake_push.sent) == 2


def test_device_option_limits_it_and_no_match_is_an_error(fake_push):
    a = register(USER).device
    register(USER)
    assert f"{a.id}: sent" in run("--user", str(USER), "--device", str(a.id)) and len(fake_push.sent) == 1
    with pytest.raises(CommandError):
        run("--user", str(USER), "--device", str(uuid.uuid4()))
    with pytest.raises(CommandError):
        run("--user", str(uuid.uuid4()))
