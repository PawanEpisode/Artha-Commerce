import pytest
from django.contrib.auth.models import Group, User

from .helpers import make_scheme


@pytest.fixture
def admin_client(client):
    user = User.objects.create_superuser("root", "root@example.com", "pw")
    client.force_login(user)
    return client


@pytest.fixture
def staff_client(client):
    """An editor: staff in the 'Syllabus editors' group, no publish permission."""
    user = User.objects.create_user("ed", "ed@example.com", "pw", is_staff=True)
    user.groups.add(Group.objects.get(name="Syllabus editors"))
    client.force_login(user)
    return client


@pytest.fixture
def scheme():
    return make_scheme(publish=False)
