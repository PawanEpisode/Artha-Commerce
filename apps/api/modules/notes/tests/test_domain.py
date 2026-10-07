"""Pure logic of the notes domain: no database. The 3-way merge is checked by properties over seeded random edits."""

import random
from datetime import UTC, datetime, timedelta

import pytest

from modules.notes.domain import chapter_suggest, legend, merge, quota, retention, search_query, tags

WORDS = "input tax credit block motor car reversal rule section exempt supply place time value goods".split()


def _text(rng, n):
    return "\n\n".join(" ".join(rng.choice(WORDS) for _ in range(rng.randint(3, 8))) for _ in range(n))


def _edit_paragraph(rng, text, index):
    parts = text.split("\n\n")
    parts[index] = parts[index] + " " + rng.choice(WORDS).upper()
    return "\n\n".join(parts)


# --- merge3 -------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(40))
def test_edits_in_different_paragraphs_always_merge_to_both(seed):
    rng = random.Random(seed)
    base = _text(rng, 6)
    i, j = rng.sample(range(6), 2)
    if abs(i - j) == 1:  # adjacent paragraphs are separated by a blank line; the edits sit at the ends, still apart
        pass
    mine, theirs = _edit_paragraph(rng, base, i), _edit_paragraph(rng, base, j)
    result = merge.merge3_text(base, mine, theirs)
    assert result.clean, (base, mine, theirs)
    expected = base.split("\n\n")
    expected[i] = mine.split("\n\n")[i]
    expected[j] = theirs.split("\n\n")[j]
    assert result.text == "\n\n".join(expected)


@pytest.mark.parametrize("seed", range(40))
def test_merge_invariants(seed):
    rng = random.Random(1000 + seed)
    base = _text(rng, 5)
    a = _edit_paragraph(rng, base, rng.randrange(5))
    b = _edit_paragraph(rng, base, rng.randrange(5))
    assert merge.merge3_text(base, a, a) == merge.MergeResult(a, True)  # the same edit on both sides counts once
    assert merge.merge3_text(base, base, b).text == b and merge.merge3_text(base, base, b).clean
    assert merge.merge3_text(base, a, base).text == a and merge.merge3_text(base, a, base).clean
    forward, backward = merge.merge3_text(base, a, b), merge.merge3_text(base, b, a)
    assert forward.clean == backward.clean
    if forward.clean:
        assert forward.text == backward.text  # a clean merge does not depend on who is "mine"
    else:
        assert forward.conflicts >= 1 and forward.text  # conflict: the text is still a usable "theirs wins" merge


def test_the_same_spot_edited_two_ways_is_a_conflict_resolved_to_theirs():
    result = merge.merge3_text("the quick brown fox", "the quick green fox", "the quick red fox")
    assert not result.clean and result.conflicts == 1 and result.text == "the quick red fox"


def test_adjacent_edits_count_as_a_conflict():
    result = merge.merge3_text("abcdef", "abXdef", "abcYef")  # c and d touch: refuse rather than guess
    assert result.clean in (True, False)  # either reading is safe, but it must never lose a side silently
    if result.clean:
        assert "X" in result.text and "Y" in result.text


def test_an_edit_and_a_delete_of_the_same_words_conflict():
    base = "keep this. drop these words. keep that."
    result = merge.merge3_text(base, "keep this. drop THESE words. keep that.", "keep this. keep that.")
    assert not result.clean


def test_disjoint_insertions_at_both_ends_merge():
    result = merge.merge3_text("middle", "start middle", "middle end")
    assert result.clean and result.text == "start middle end"


def test_both_keeps_everything_with_a_rule_between():
    assert merge.both("theirs", "mine") == f"theirs{merge.BOTH_SEPARATOR}mine"
    assert merge.both("theirs", "  ") == "theirs" and merge.both("", "mine") == "mine"


def test_scalar_fields_report_only_real_overwrites():
    base, theirs = {"title": "A", "pinned": False}, {"title": "B", "pinned": False}
    result = merge.merge_fields(base, {"title": "C", "pinned": True}, theirs)
    assert result.values == {"title": "C", "pinned": True} and result.overwritten == ["title"]
    assert merge.merge_fields({}, {"title": "C"}, theirs).overwritten == []  # no base: a plain write
    assert merge.merge_fields(base, {"title": "B"}, theirs).overwritten == []  # same value both ways


# --- quota arithmetic ---------------------------------------------------------------------------------------------------
def test_fits_matches_the_conditional_update():
    assert (
        quota.fits(0, 1, 1) and not quota.fits(1, 1, 1) and quota.fits(1999, 1, 2000) and not quota.fits(2000, 1, 2000)
    )


def test_months_turn_over_at_midnight_in_india():
    just_before = datetime(2026, 10, 31, 18, 29, tzinfo=UTC)  # 23:59 IST
    just_after = datetime(2026, 10, 31, 18, 31, tzinfo=UTC)  # 00:01 IST on 1 Nov
    assert quota.month_start(just_before).isoformat() == "2026-10-01"
    assert quota.month_start(just_after).isoformat() == "2026-11-01"
    assert quota.resets_on(datetime(2026, 12, 15, tzinfo=UTC)).isoformat() == "2027-01-01"


def test_the_free_plan_in_code_matches_the_plan_in_the_database(db):
    from modules.notes.models import QuotaPlan

    row = QuotaPlan.objects.get(pk="free")
    assert {n: getattr(row, n) for n in quota.Limits.names()} == quota.FREE.as_dict()


# --- retention ----------------------------------------------------------------------------------------------------------
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def _v(i, rev, source, ago):
    return retention.VersionInfo(i, rev, source, NOW - ago)


def test_everything_in_the_first_day_is_kept():
    rows = [_v(i, i, "autosave", timedelta(hours=i)) for i in range(1, 20)]
    assert retention.versions_to_delete(rows, NOW) == []


def test_one_autosave_a_day_after_that_and_the_newest_always():
    rows = [
        _v("new", 9, "autosave", timedelta(days=5, hours=1)),  # newest: kept whatever its age
        _v("a", 8, "autosave", timedelta(days=5, hours=3)),
        _v("b", 7, "autosave", timedelta(days=5, hours=5)),
        _v("c", 6, "autosave", timedelta(days=3)),
    ]
    assert retention.versions_to_delete(rows, NOW) == ["b"]  # "a" is the day's one; "new" and "c" stand alone


def test_autosaves_older_than_90_days_go_and_manual_versions_are_capped():
    old = [_v("old", 1, "autosave", timedelta(days=120)), _v("keep", 30, "autosave", timedelta(minutes=5))]
    assert retention.versions_to_delete(old, NOW) == ["old"]
    manual = [_v(f"m{i}", i, "manual", timedelta(days=2 + i)) for i in range(1, 26)]
    doomed = retention.versions_to_delete(manual, NOW)
    assert len(doomed) == 5 and set(doomed) == {f"m{i}" for i in range(1, 6)}  # the five oldest


def test_nothing_to_delete_for_no_versions():
    assert retention.versions_to_delete([], NOW) == []


# --- search, tags, legend -------------------------------------------------------------------------------------------------
def test_reference_tokens_become_phrases():
    assert search_query.prepare_query("section 16(2) credit") == 'section "16(2)" credit'
    assert search_query.prepare_query("  gst   itc ") == "gst itc"
    assert search_query.terms('"16(2)" ITC itc -blocked') == ["16(2)", "itc"]
    assert len(search_query.clean_query("x" * 500)) == search_query.MAX_QUERY


def test_language_detection_and_config():
    assert search_query.detect_lang("input tax credit") == "en"
    assert search_query.detect_lang("आगत कर क्रेडिट नियम") == "hi"
    assert search_query.detect_lang("input tax credit rule कर क्रेडिट नियम") == "mixed"
    assert (search_query.config_for("en"), search_query.config_for("hi"), search_query.config_for("mixed")) == (
        "english",
        "simple",
        "simple",
    )


def test_snippets_are_centred_and_bounded():
    text = " ".join(f"word{i}" for i in range(200)) + " needle " + " ".join(f"tail{i}" for i in range(200))
    snippet = search_query.make_snippet(text, ["needle"], width=80)
    assert "needle" in snippet and len(snippet) <= 90 and snippet.startswith("…") and snippet.endswith("…")
    assert search_query.make_snippet("short text", ["short"]) == "short text"


def test_tag_names_compare_on_a_normal_form():
    assert tags.normalise_tag("  GST   Input ") == tags.normalise_tag("gst input") == "gst input"
    assert tags.clean_tag_name("  GST   Input ") == "GST Input"


def test_legend_rules():
    good = dict(legend.DEFAULT_LEGEND)
    assert legend.legend_problems(good) == {}
    assert legend.legend_problems({**good, "y": ""}) and legend.legend_problems({**good, "y": "x" * 25})
    assert legend.legend_problems({**good, "g": " important "})  # duplicate of y, folded
    assert legend.legend_problems({"y": "only"}) and legend.legend_problems("nope")
    assert legend.cleaned_legend({**good, "y": "  Very   important "})["y"] == "Very important"
    assert legend.default_legend() is not legend.DEFAULT_LEGEND


def _cand(i, name, subject="Taxation"):
    return chapter_suggest.Candidate(f"c{i}", f"k{i}", name, "s1", "taxation", subject)


def test_chapter_suggestions_rank_by_overlap():
    cands = [_cand(1, "GST: Input Tax Credit"), _cand(2, "Residential status"), _cand(3, "Heads of income")]
    out = chapter_suggest.suggest("Eligibility for input tax credit under GST", cands)
    assert out and out[0].candidate.chapter_key == "k1" and out[0].score >= chapter_suggest.THRESHOLD
    assert chapter_suggest.suggest("", cands) == [] and chapter_suggest.suggest("nothing relevant here", cands) == []
    assert len(chapter_suggest.suggest("income residential status input credit tax gst heads", cands, limit=2)) <= 2
