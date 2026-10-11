import copy
import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from modules.recall.models import RecallDeck, RecallDeckVersion, RecallItem, RecallItemVersion
from modules.recall.services import seed

pytestmark = pytest.mark.django_db
SEED_DIR = Path(seed.__file__).resolve().parents[1] / "seed"


def item(ref, text="Q", **over):
    return {
        "ref": ref, "kind": "pointer", "importance": "mandatory",
        "fields": {"prompt_md": f"{text} {ref}?", "answer_md": "Answer"}, "rights_status": "original", **over,
    }  # fmt: skip


def file(items=None, *, sample=False, slug="gst-pointers", chapter="gst-itc"):
    return {
        "schema": 1, "sample": sample,
        "decks": [{
            "slug": slug, "title": "GST pointers", "description": "d", "changelog": "First.",
            "scope": {"course": "ca", "level": "intermediate", "subject_key": "taxation", "chapter_key": chapter},
            "items": items if items is not None else [item("r1"), item("r2")],
        }],
    }  # fmt: skip


def test_load_creates_a_draft_deck_and_a_second_run_changes_nothing(scheme):
    first = seed.load_seed(file())
    assert first.ok and first.decks[0].items_created == 2 and first.decks[0].draft_version_no == 1
    deck = RecallDeck.objects.get(slug="gst-pointers")
    assert deck.live_version_id is None and deck.chapter_id is not None
    again = seed.load_seed(file())
    assert again.ok and again.decks[0].items_created == 0 and again.decks[0].items_unchanged == 2
    assert RecallItem.objects.filter(ownership="platform").count() == 2
    assert RecallDeckVersion.objects.filter(deck=deck).count() == 1


def test_publish_makes_it_live_and_reloading_the_same_file_adds_nothing(scheme):
    report = seed.load_seed(file(), publish=True)
    assert report.ok and report.decks[0].published_version_no == 1
    deck = RecallDeck.objects.get(slug="gst-pointers")
    assert deck.live_version.state == "live"
    again = seed.load_seed(file(), publish=True)
    assert again.ok and again.decks[0].draft_version_no is None
    assert RecallDeckVersion.objects.filter(deck=deck).count() == 1


def test_an_edited_item_becomes_a_draft_and_the_live_text_is_untouched(scheme):
    seed.load_seed(file(), publish=True)
    edited = file([item("r1"), item("r2")])
    edited["decks"][0]["items"][0]["fields"]["answer_md"] = "A better answer"
    report = seed.load_seed(edited)
    assert report.ok and report.decks[0].items_updated == 1 and report.decks[0].draft_version_no == 2
    one = RecallItem.objects.get(external_ref="r1")
    assert one.live_version.fields["answer_md"] == "Answer"
    assert RecallItemVersion.objects.get(pk=one.current_version_id).fields["answer_md"] == "A better answer"


def test_unknown_rights_block_publishing_but_the_draft_loads(scheme):
    data = file([item("r1", rights_status="unknown")])
    report = seed.load_seed(data, publish=True)
    deck_result = report.decks[0]
    assert deck_result.draft_version_no == 1 and deck_result.published_version_no is None
    assert deck_result.errors and "not published" in deck_result.errors[0] and "r1" in deck_result.errors[0]
    assert RecallDeck.objects.get(slug="gst-pointers").live_version_id is None


def test_a_sample_file_is_never_published_unless_asked(scheme):
    report = seed.load_seed(file(sample=True), publish=True)
    assert report.decks[0].published_version_no is None and "sample" in report.decks[0].skipped
    assert RecallDeck.objects.get(slug="gst-pointers").live_version_id is None
    again = seed.load_seed(file(sample=True), publish=True, include_sample=True)
    assert again.decks[0].published_version_no == 1


def test_a_bad_file_is_reported_before_anything_is_written(scheme):
    bad = file()
    bad["decks"][0]["items"][0]["kind"] = "nonsense"
    bad["decks"][0]["items"][1]["surprise"] = 1
    report = seed.load_seed(bad)
    assert not report.ok and RecallItem.objects.count() == 0
    assert seed.problems_in([]) and seed.problems_in({"schema": 2, "decks": []})


def test_an_unknown_chapter_fails_that_deck_only(scheme):
    two = file()
    two["decks"].append(file([item("x1")], slug="other", chapter="no-such-chapter")["decks"][0])
    report = seed.load_seed(two)
    by = {d.slug: d for d in report.decks}
    assert by["gst-pointers"].draft_version_no == 1 and by["other"].errors
    assert not RecallDeck.objects.filter(slug="other").exists()


def test_the_command_skips_template_and_sample_files_by_default(scheme, tmp_path):
    with pytest.raises(
        CommandError, match="No seed files"
    ):  # only the template ships at the top level, and it never loads
        call_command("load_recall_seed", stdout=StringIO())
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "sample_demo.json").write_text(json.dumps(file(sample=True)), encoding="utf-8")
    with pytest.raises(CommandError, match="No seed files"):  # a folder holding only a sample loads nothing by default
        call_command("load_recall_seed", str(paper), stdout=StringIO())
    assert not RecallDeck.objects.exists()
    call_command("load_recall_seed", str(paper), "--include-sample", stdout=StringIO())
    deck = RecallDeck.objects.get(slug="gst-pointers")
    assert deck.live_version_id is None  # a sample is never published, even when it is loaded


def test_the_command_loads_a_named_file_and_dry_run_rolls_back(scheme, tmp_path):
    path = tmp_path / "mine.json"
    path.write_text(json.dumps(file()), encoding="utf-8")
    call_command("load_recall_seed", str(path), "--dry-run", stdout=StringIO())
    assert not RecallDeck.objects.exists()
    call_command("load_recall_seed", str(path), "--publish", stdout=StringIO())
    assert RecallDeck.objects.get(slug="gst-pointers").live_version_id
    with pytest.raises(CommandError):
        call_command("load_recall_seed", str(tmp_path / "missing.json"), stdout=StringIO())


def test_the_shipped_template_is_a_valid_file():
    data = json.loads((SEED_DIR / "_TEMPLATE.json").read_text(encoding="utf-8"))
    assert seed.problems_in(copy.deepcopy(data)) == []


def test_the_command_takes_a_folder_and_loads_the_json_files_inside_it(scheme, tmp_path):
    paper = tmp_path / "ca-foundation-paper1"
    paper.mkdir()
    (paper / "gst.json").write_text(json.dumps(file()), encoding="utf-8")
    (paper / "_skipped.json").write_text("not json", encoding="utf-8")  # underscore files are ignored
    call_command("load_recall_seed", str(paper), stdout=StringIO())
    assert RecallDeck.objects.filter(slug="gst-pointers").exists()
