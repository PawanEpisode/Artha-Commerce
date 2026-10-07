"""The stable-reference selectors other modules use (F-03 ERD 3.2): ids to refs, keys to the current scheme's chapter."""

import uuid

import pytest

from modules.syllabus import selectors
from modules.syllabus.models import Chapter, Level, Subject, Topic
from modules.syllabus.tests.helpers import make_scheme, switch_scheme

pytestmark = pytest.mark.django_db


def test_chapter_refs_carry_the_stable_keys_and_scheme_status():
    scheme = make_scheme()
    gst = Chapter.objects.get(key="gst-itc")
    ref = selectors.chapter_refs([gst.id, uuid.uuid4()])[gst.id]
    assert (ref.key, ref.subject_key, ref.scheme_id, ref.scheme_status) == (
        "gst-itc",
        "taxation",
        scheme.id,
        "published",
    )
    assert ref.level_id == scheme.level_id and ref.subject_id == gst.subject_id and ref.name == gst.name
    assert selectors.chapter_refs([]) == {}


def test_draft_chapters_are_invisible():
    make_scheme(publish=False)
    gst = Chapter.objects.get(key="gst-itc")
    assert selectors.chapter_refs([gst.id]) == {}
    assert selectors.topic_refs([Topic.objects.filter(chapter=gst).first().id]) == {}


def test_topic_refs_name_their_chapter():
    make_scheme()
    topic = Topic.objects.get(key="eligibility")
    ref = selectors.topic_refs([topic.id])[topic.id]
    assert (ref.key, ref.chapter_id, ref.chapter_key) == ("eligibility", topic.chapter_id, "gst-itc")


def test_resolve_keys_finds_the_chapter_in_the_current_published_scheme():
    scheme = make_scheme()
    ref = selectors.resolve_keys(scheme.level_id, "taxation", "gst-itc")
    assert ref and ref.scheme_id == scheme.id
    assert selectors.resolve_keys(scheme.level_id, "taxation", "no-such-chapter") is None
    assert selectors.resolve_keys(scheme.level_id, "no-such-subject", "gst-itc") is None


def test_resolve_keys_follows_a_scheme_switch():
    old = make_scheme(code="2023")

    def drop_heads(spec):
        spec["subjects"][0]["chapters"] = [c for c in spec["subjects"][0]["chapters"] if c["key"] != "heads-of-income"]

    new = switch_scheme(old, drop_heads)
    level = Level.objects.get(pk=old.level_id)
    assert selectors.resolve_keys(level.id, "taxation", "gst-itc").scheme_id == new.id
    # the same key is gone from the new scheme: "moved or removed"
    assert selectors.resolve_keys(level.id, "taxation", "heads-of-income") is None
    assert selectors.chapter_refs(
        [Chapter.objects.get(subject__scheme=old, key="heads-of-income").id]
    )  # old rows still resolve by id


def test_resolve_key_pairs_is_one_lookup_for_many_pairs():
    scheme = make_scheme()
    pairs = [("taxation", "gst-itc"), ("corporate-laws", "companies-act"), ("taxation", "nope")]
    got = selectors.resolve_key_pairs(scheme.level_id, pairs)
    assert set(got) == {("taxation", "gst-itc"), ("corporate-laws", "companies-act")}
    assert selectors.resolve_key_pairs(scheme.level_id, []) == {}


def test_chapters_for_scheme_are_in_syllabus_order_and_filter_by_subject():
    scheme = make_scheme()
    everything = selectors.chapters_for_scheme(scheme.id)
    assert {r.key for r in everything} == {"gst-itc", "residential-status", "heads-of-income", "companies-act"}
    only = selectors.chapters_for_scheme(scheme.id, "taxation")
    assert [r.key for r in only] == [
        c.key for c in Chapter.objects.filter(subject__key="taxation").order_by("sort_order", "key")
    ]
    assert all(r.subject_key == "taxation" for r in only)
    assert Subject.objects.filter(scheme=scheme).count() == 2
