import json

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse

from modules.syllabus import services
from modules.syllabus.models import Chapter, ChapterMap, Scheme, Subject, SyllabusReport, Topic

from .helpers import SPEC, make_scheme

pytestmark = pytest.mark.django_db


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


def test_every_changelist_opens(admin_client, scheme):
    for name in [
        "course",
        "level",
        "examterm",
        "scheme",
        "subject",
        "chapter",
        "topic",
        "chaptermap",
        "syllabusreport",
    ]:
        assert admin_client.get(reverse(f"admin:syllabus_{name}_changelist")).status_code == 200, name
    for name in ["coverage_enrollment", "coverage_coverageevent", "profiles_profile"]:
        assert admin_client.get(reverse(f"admin:{name}_changelist")).status_code == 200, name


def test_admin_pages_need_a_staff_login(client, scheme):
    response = client.get(reverse("admin:syllabus_scheme_changelist"))
    assert response.status_code == 302 and "login" in response["Location"]


def test_static_assets_are_served(client):
    assert client.get("/static/admin/css/base.css").status_code == 200


def test_scheme_and_paper_forms_open(admin_client, scheme):
    subject = Subject.objects.get(scheme=scheme, key="taxation")
    chapter = Chapter.objects.get(subject=subject, key="gst-itc")
    assert admin_client.get(reverse("admin:syllabus_scheme_change", args=[scheme.pk])).status_code == 200
    assert admin_client.get(reverse("admin:syllabus_subject_change", args=[subject.pk])).status_code == 200
    assert admin_client.get(reverse("admin:syllabus_chapter_change", args=[chapter.pk])).status_code == 200


def test_publish_and_retire_actions_need_the_publish_permission(staff_client, scheme):
    url = reverse("admin:syllabus_scheme_changelist")
    staff_client.post(url, {"action": "publish_selected", "_selected_action": [str(scheme.pk)]})
    scheme.refresh_from_db()
    assert scheme.status == Scheme.Status.DRAFT  # editors cannot publish


def test_publisher_can_publish_then_retire(client, scheme):
    user = User.objects.create_user("pub", "p@example.com", "pw", is_staff=True)
    user.groups.add(Group.objects.get(name="Syllabus publishers"))
    client.force_login(user)
    url = reverse("admin:syllabus_scheme_changelist")
    client.post(url, {"action": "publish_selected", "_selected_action": [str(scheme.pk)]})
    scheme.refresh_from_db()
    assert scheme.status == Scheme.Status.PUBLISHED
    client.post(url, {"action": "retire_selected", "_selected_action": [str(scheme.pk)]})
    scheme.refresh_from_db()
    assert scheme.status == Scheme.Status.RETIRED


def test_status_cannot_be_edited_directly(admin_client, scheme):
    from modules.syllabus.admin import SchemeAdmin

    assert "status" in SchemeAdmin.readonly_fields


def test_nodes_of_a_published_scheme_cannot_be_deleted(admin_client, scheme):
    services.publish_scheme(scheme)
    chapter = Chapter.objects.get(subject__scheme=scheme, key="gst-itc")
    response = admin_client.get(reverse("admin:syllabus_chapter_delete", args=[chapter.pk]))
    assert response.status_code == 403
    # a draft scheme's nodes can be deleted
    draft = make_scheme(code="2099", publish=False)
    other = Chapter.objects.get(subject__scheme=draft, key="heads-of-income")
    assert admin_client.get(reverse("admin:syllabus_chapter_delete", args=[other.pk])).status_code == 200


def test_bulk_add_topics_and_chapters(admin_client, scheme):
    chapter = Chapter.objects.get(subject__scheme=scheme, key="residential-status")
    n = services.add_topics_from_text(
        chapter, "Basic rules\nDeemed residence | rule\nBasic rules\n\nSection 6 | section"
    )
    assert n == 3
    assert set(chapter.topics.values_list("key", flat=True)) == {"basic-rules", "deemed-residence", "section-6"}
    assert chapter.topics.get(key="deemed-residence").kind == Topic.Kind.RULE
    subject = Subject.objects.get(scheme=scheme, key="corporate-laws")
    assert services.add_chapters_from_text(subject, "Contracts | 5-8\nAgency | 6\nBad marks | x\nContracts") == 3
    assert Chapter.objects.get(subject=subject, key="contracts").marks_min == 5
    assert Chapter.objects.get(subject=subject, key="agency").marks_max == 6
    assert Chapter.objects.get(subject=subject, key="bad-marks").marks_max is None


def test_bulk_add_through_the_admin_form(admin_client, scheme):
    chapter = Chapter.objects.get(subject__scheme=scheme, key="heads-of-income")
    url = reverse("admin:syllabus_chapter_change", args=[chapter.pk])
    form = admin_client.get(url).context["adminform"].form
    data = {n: (f.value() if f.value() is not None else "") for n, f in ((n, form[n]) for n in form.fields)}
    data = {k: v for k, v in data.items() if v != "" or k in {"add_topics"}}
    data["add_topics"] = "Salary\nHouse property"
    data.update(
        {
            "topics-TOTAL_FORMS": "0",
            "topics-INITIAL_FORMS": "0",
            "topics-MIN_NUM_FORMS": "0",
            "topics-MAX_NUM_FORMS": "1000",
        }
    )
    response = admin_client.post(url, data)
    assert response.status_code == 302, getattr(response, "context", None) and response.context["adminform"].form.errors
    assert chapter.topics.count() == 2


def test_export_then_import_round_trips(admin_client, scheme):
    export = admin_client.post(
        reverse("admin:syllabus_scheme_changelist"), {"action": "export_json", "_selected_action": [str(scheme.pk)]}
    )
    body = json.loads(export.content)
    assert body["scheme"]["code"] == "2023" and body["subjects"][0]["chapters"]
    body["scheme"]["code"] = "2030"
    body["scheme"]["name"] = "2030 Scheme"
    response = admin_client.post(reverse("admin:syllabus_scheme_import"), {"text": json.dumps(body)})
    assert response.status_code == 302
    imported = Scheme.objects.get(code="2030")
    assert imported.status == Scheme.Status.DRAFT
    assert (
        Chapter.objects.filter(subject__scheme=imported).count()
        == Chapter.objects.filter(subject__scheme=scheme).count()
    )


def test_import_rejects_bad_input_and_published_targets(admin_client, scheme):
    url = reverse("admin:syllabus_scheme_import")
    assert b"not valid JSON" in admin_client.post(url, {"text": "{oops"}).content
    assert b"top level" in admin_client.post(url, {"text": "{}"}).content
    services.publish_scheme(scheme)
    again = admin_client.post(url, {"text": json.dumps(SPEC)})
    assert again.status_code == 200 and b"Only draft schemes" in again.content


def test_chapter_map_must_cross_schemes_of_one_level(admin_client, scheme):
    new = make_scheme(code="2025", publish=False)
    a = Chapter.objects.get(subject__scheme=scheme, key="gst-itc")
    b = Chapter.objects.get(subject__scheme=new, key="gst-itc")
    url = reverse("admin:syllabus_chaptermap_add")
    same = admin_client.post(url, {"from_chapter": a.pk, "to_chapter": a.pk, "relation": "same", "carry_ratio": "1.00"})
    assert same.status_code == 200 and ChapterMap.objects.count() == 0
    ok = admin_client.post(url, {"from_chapter": a.pk, "to_chapter": b.pk, "relation": "same", "carry_ratio": "1.00"})
    assert ok.status_code == 302 and ChapterMap.objects.count() == 1


def test_build_chapter_map_action(admin_client, scheme):
    services.publish_scheme(scheme)
    new = make_scheme(code="2025", publish=False)
    admin_client.post(
        reverse("admin:syllabus_scheme_changelist"), {"action": "build_chapter_map", "_selected_action": [str(new.pk)]}
    )
    assert ChapterMap.objects.filter(to_chapter__subject__scheme=new).count() >= 3


def test_reports_inbox(admin_client, scheme):
    chapter = Chapter.objects.get(subject__scheme=scheme, key="gst-itc")
    report = services.create_report(node_type="chapter", node_id=chapter.id, message="Wrong marks", user_id=None)
    assert b"gst-itc" in admin_client.get(reverse("admin:syllabus_syllabusreport_changelist")).content
    admin_client.post(
        reverse("admin:syllabus_syllabusreport_changelist"),
        {"action": "mark_fixed", "_selected_action": [str(report.pk)]},
    )
    report.refresh_from_db()
    assert report.status == SyllabusReport.Status.FIXED
    assert admin_client.get(reverse("admin:syllabus_syllabusreport_add")).status_code == 403


def test_staff_groups_exist_with_the_right_permissions():
    editors = Group.objects.get(name="Syllabus editors")
    publishers = Group.objects.get(name="Syllabus publishers")
    assert not editors.permissions.filter(codename="publish_scheme").exists()
    assert publishers.permissions.filter(codename="publish_scheme").exists()
    assert editors.permissions.filter(codename="change_chapter").exists()


def test_topic_list_filters_by_scheme_then_paper_then_chapter(admin_client, scheme):
    url = reverse("admin:syllabus_topic_changelist")
    taxation = Subject.objects.get(key="taxation")
    gst = Chapter.objects.get(key="gst-itc")
    base = {"chapter__subject__scheme__id__exact": str(scheme.id)}

    page = admin_client.get(url, base)
    assert page.status_code == 200 and "Taxation" in page.content.decode()
    # Only a scheme is picked: the paper filter is offered, the chapter filter is not yet.
    assert "By paper" in page.content.decode() and "By chapter" not in page.content.decode()

    page = admin_client.get(url, {**base, "paper": str(taxation.id)})
    assert "By chapter" in page.content.decode()
    assert {t.chapter.subject.key for t in page.context["cl"].result_list} == {"taxation"}

    page = admin_client.get(url, {**base, "paper": str(taxation.id), "chapter": str(gst.id)})
    assert {t.chapter.key for t in page.context["cl"].result_list} == {"gst-itc"}
    assert page.context["cl"].result_count == 4


def test_paper_filter_ignores_a_paper_of_another_scheme(admin_client, scheme):
    other = make_scheme(publish=False, code="2030")
    stale = Subject.objects.get(scheme=other, key="taxation")
    page = admin_client.get(
        reverse("admin:syllabus_topic_changelist"),
        {"chapter__subject__scheme__id__exact": str(scheme.id), "paper": str(stale.id)},
    )
    assert (
        page.status_code == 200
        and page.context["cl"].result_count == Topic.objects.filter(chapter__subject__scheme=scheme).count()
    )


def test_chapter_list_filters_by_paper(admin_client, scheme):
    laws = Subject.objects.get(scheme=scheme, key="corporate-laws")
    page = admin_client.get(
        reverse("admin:syllabus_chapter_changelist"),
        {"subject__scheme__id__exact": str(scheme.id), "paper": str(laws.id)},
    )
    assert {c.key for c in page.context["cl"].result_list} == {"companies-act"}
