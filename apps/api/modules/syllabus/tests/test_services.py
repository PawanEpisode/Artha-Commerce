from copy import deepcopy

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client

from modules.profiles.models import Profile
from modules.syllabus import services
from modules.syllabus.models import Chapter, ChapterMap, ExamTerm, Scheme, Subject, Topic
from modules.syllabus.tests.helpers import SPEC, make_scheme

pytestmark = pytest.mark.django_db


def counts():
    return tuple(m.objects.count() for m in (Scheme, Subject, Chapter, Topic))


def test_seed_loader_is_idempotent():
    make_scheme(publish=False)
    first = counts()
    make_scheme(publish=False)
    assert counts() == first == (1, 2, 4, 4)


def test_seed_loader_deactivates_nodes_missing_from_the_file():
    make_scheme(publish=False)
    spec = deepcopy(SPEC)
    spec["subjects"][0]["chapters"] = spec["subjects"][0]["chapters"][:1]
    spec["subjects"][0]["chapters"][0]["topics"] = spec["subjects"][0]["chapters"][0]["topics"][:2]
    make_scheme(publish=False, spec=spec)
    assert Chapter.objects.filter(is_active=True, subject__key="taxation").count() == 1
    assert Topic.objects.filter(is_active=True).count() == 2
    assert counts()[2:] == (4, 4)  # nothing deleted


def test_publish_requires_a_subject():
    empty = deepcopy(SPEC)
    empty["subjects"] = []
    scheme = make_scheme(publish=False, spec=empty)
    with pytest.raises(services.SchemeStateError):
        services.publish_scheme(scheme)


def test_two_open_ended_schemes_cannot_both_be_published():
    make_scheme(code="2023")
    other = make_scheme(publish=False, code="2025")
    with pytest.raises(services.SchemeStateError, match="overlapping"):
        services.publish_scheme(other)


def test_schemes_with_disjoint_term_windows_can_both_be_published():
    first = make_scheme(publish=False, code="2023", to_term="2027-05")
    second = make_scheme(publish=False, code="2025", from_term="2027-11")
    services.publish_scheme(first)
    services.publish_scheme(second)
    assert Scheme.objects.filter(status="published").count() == 2


def test_retire_keeps_data_and_allows_a_new_publish():
    old = make_scheme(code="2023")
    services.retire_scheme(old)
    old.refresh_from_db()
    assert old.status == "retired" and old.subjects.count() == 2
    services.publish_scheme(make_scheme(publish=False, code="2025"))
    with pytest.raises(services.SchemeStateError):
        services.publish_scheme(old)  # a retired scheme cannot return


def test_only_published_can_be_retired():
    draft = make_scheme(publish=False)
    with pytest.raises(services.SchemeStateError):
        services.retire_scheme(draft)


def test_default_chapter_map_matches_on_subject_and_chapter_keys():
    old = make_scheme(code="2023")
    spec = deepcopy(SPEC)
    spec["subjects"][0]["chapters"].append({"key": "new-chapter", "name": "Brand new"})
    new = make_scheme(publish=False, code="2025", spec=spec)
    assert services.build_default_chapter_map(old, new) == 4
    assert services.build_default_chapter_map(old, new) == 0  # idempotent
    assert ChapterMap.objects.filter(relation="same").count() == 4


def test_check_constraints_reject_bad_rows():
    make_scheme(publish=False)
    chapter = Chapter.objects.get(key="gst-itc")
    chapter.marks_min, chapter.marks_max = 20, 10
    with pytest.raises(IntegrityError), transaction.atomic():
        chapter.save()


def test_term_codes_exist_per_course():
    assert ExamTerm.objects.filter(course__code="ca", code="2027-05").exists()


def test_load_command_loads_every_seed_file_as_draft(capsys):
    call_command("load_syllabus_seed")
    assert Scheme.objects.count() >= 10
    assert not Scheme.objects.filter(status="published").exists()
    call_command("load_syllabus_seed")  # idempotent
    assert Scheme.objects.filter(level__course__code="ca", level__code="intermediate").count() == 2
    assert Chapter.objects.filter(subject__key="taxation", is_active=True).count() == 17
    call_command("load_syllabus_seed", "--publish")
    published = Scheme.objects.filter(level__course__code="ca", level__code="intermediate", status="published")
    assert published.count() == 1  # the second one is refused (overlap), the first stays published
    assert "not published" in capsys.readouterr().err


def test_publish_endpoint_requires_an_editor(auth_client):
    scheme = make_scheme(publish=False)
    url = f"/api/v1/admin/syllabus/schemes/{scheme.id}/publish/"
    assert Client().post(url).status_code == 401  # `client` and `auth_client` share one object, so use a fresh one
    assert auth_client.post(url).status_code == 403  # a student, even with a valid token

    sub = "3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11"
    Profile.objects.update_or_create(pk=sub, defaults={"role": "editor", "email": "e@example.com"})
    res = auth_client.post(url)
    assert res.status_code == 200 and res.json()["status"] == "published"
    assert auth_client.post(f"/api/v1/admin/syllabus/schemes/{scheme.id}/retire/").json()["status"] == "retired"
    assert auth_client.post(f"/api/v1/admin/syllabus/schemes/{scheme.id}/retire/").status_code == 400
