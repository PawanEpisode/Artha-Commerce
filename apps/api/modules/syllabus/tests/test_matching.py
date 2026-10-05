"""Chapter-name matching is pure logic: no database, so these run fast and pin every rule."""

from decimal import Decimal

from modules.syllabus import matching
from modules.syllabus.matching import Item, match_chapters, match_moved, match_papers, normalise, similarity


def items(*pairs: tuple[str, str]) -> list[Item]:
    """(key, name) pairs in paper order."""
    return [Item(key, key, name, position) for position, (key, name) in enumerate(pairs)]


def by_old(result):
    return {p.old: p for p in result.proposals}


def test_normalise_drops_numbering_punctuation_case_and_accents():
    assert normalise("Chapter 3: Income from Salaries") == "income from salaries"
    assert normalise("3. Income  from SALARIES!") == "income from salaries"
    assert normalise("2.1 Café & Co (Part A)") == "cafe and co part a"
    assert normalise("Unit 4 - Ethics") == "ethics"
    assert normalise("") == ""
    assert normalise("100 Marks Quiz") == "100 marks quiz"  # a bare number with no separator is part of the name
    assert normalise("Chapter 3 Income") == "income"


def test_similarity_is_one_for_the_same_name_and_low_for_unrelated_names():
    assert similarity("Chapter 2: GST", "2. gst") == 1.0
    assert similarity("GST: Input Tax Credit", "GST Input Tax Credit (ITC)") > 0.85
    assert similarity("Companies Act", "Partnership Act") < 0.6
    assert similarity("Corporate Governance", "Governance of Corporates") == 1.0  # word order and plurals
    assert similarity("", "Anything") == 0.0


def test_same_key_wins_and_is_trusted():
    result = match_chapters(items(("a", "Alpha"), ("b", "Beta")), items(("b", "Beta"), ("a", "Alpha")))
    assert {(p.old, p.new, p.basis, p.needs_review) for p in result.proposals} == {
        ("a", "a", "key", False),
        ("b", "b", "key", False),
    }
    assert not result.unmatched_old and not result.unmatched_new


def test_a_reused_key_with_an_unrelated_name_is_flagged_for_review():
    result = match_chapters(items(("ch-1", "Income from Salaries")), items(("ch-1", "Company Formation")))
    (proposal,) = result.proposals
    assert proposal.basis == "key" and proposal.needs_review and proposal.confidence < 0.5


def test_identical_normalised_names_match_across_different_keys():
    old = items(("old-1", "Chapter 1: Basics of GST"), ("old-2", "Chapter 2: Input Tax Credit"))
    new = items(("n-a", "2. Input tax credit"), ("n-b", "1. Basics of GST"))
    result = match_chapters(old, new)
    mapped = {p.old: (p.new, p.basis, p.needs_review) for p in result.proposals}
    assert mapped == {"old-1": ("n-b", "name", False), "old-2": ("n-a", "name", False)}


def test_close_names_match_and_the_weaker_ones_are_flagged():
    old = items(("a", "GST: Input Tax Credit"), ("b", "Residential Status and Incidence of Tax"))
    new = items(("x", "GST Input Tax Credit (ITC)"), ("y", "Residential Status & Tax Incidence"))
    result = match_chapters(old, new)
    mapped = by_old(result)
    assert mapped["a"].new == "x" and mapped["a"].basis == "fuzzy" and not mapped["a"].needs_review
    assert mapped["b"].new == "y"
    assert all(p.relation == "same" for p in result.proposals)


def test_position_breaks_a_tie_between_equally_named_candidates():
    old = items(("a", "Revision Test"))
    new = items(("p", "Revision Test"), ("q", "Intro"), ("r", "Intro two"), ("s", "Revision Test"))
    # one old chapter can only take one new chapter: the one at the same relative position (first) wins
    result = match_chapters(old, new)
    (proposal,) = result.proposals
    assert proposal.new == "p"
    assert [i.ref for i in result.unmatched_new if i.name == "Revision Test"] == ["s"]


def test_a_new_chapter_that_contains_two_old_names_is_a_proposed_merge():
    old = items(("a", "Residential Status"), ("b", "Heads of Income"), ("c", "Ethics"))
    new = items(("m", "Residential Status and Heads of Income"), ("c2", "Ethics"))
    result = match_chapters(old, new)
    merged = [p for p in result.proposals if p.relation == "merged"]
    assert {p.old for p in merged} == {"a", "b"} and {p.new for p in merged} == {"m"}
    assert all(p.needs_review and p.carry_ratio == Decimal("0.50") and p.basis == "merge" for p in merged)
    assert any(p.old == "c" and p.new == "c2" for p in result.proposals)


def test_an_old_chapter_that_contains_two_new_names_is_a_proposed_split():
    old = items(("big", "Direct Tax and Indirect Tax"), ("e", "Ethics"))
    new = items(("d", "Direct Tax"), ("i", "Indirect Tax"), ("e", "Ethics"))
    result = match_chapters(old, new)
    split = [p for p in result.proposals if p.relation == "split"]
    assert {p.new for p in split} == {"d", "i"} and {p.old for p in split} == {"big"}
    assert all(p.needs_review and p.carry_ratio == Decimal("1.00") for p in split)


def test_single_word_names_never_form_a_split_or_merge():
    old = items(("a", "Tax"), ("b", "Audit"))
    new = items(("n", "Tax and Audit Overview"))
    result = match_chapters(old, new)
    assert not [p for p in result.proposals if p.relation != "same"]


def test_the_lone_leftover_pair_is_a_renamed_chapter_when_the_names_still_resemble():
    old = items(("a", "Ethics"), ("b", "Audit Planning"))
    new = items(("a", "Ethics"), ("z", "Planning and Risk Assessment in Audit"))
    result = match_chapters(old, new)
    renamed = [p for p in result.proposals if p.basis == "renamed"]
    assert len(renamed) == 1 and renamed[0].old == "b" and renamed[0].needs_review


def test_a_lone_leftover_pair_with_nothing_in_common_stays_unmatched():
    result = match_chapters(items(("a", "Ethics")), items(("z", "Quantitative Aptitude")))
    assert not result.proposals and len(result.unmatched_old) == 1 and len(result.unmatched_new) == 1


def test_papers_pair_by_key_then_by_name():
    old = items(("p1", "Accounting"), ("p2", "Business Laws"), ("p3", "Quantitative Aptitude"))
    new = items(("p1", "Accounting"), ("laws", "Business laws"), ("qa", "Statistics"))
    pairs = {(o.key, n.key) for o, n in match_papers(old, new)}
    assert pairs == {("p1", "p1"), ("p2", "laws")}  # p3 and "Statistics" have nothing in common


def test_chapters_that_moved_paper_need_an_almost_identical_name_and_are_flagged():
    proposals = match_moved(
        items(("a", "Ethics and Professional Conduct")), items(("z", "Ethics & Professional conduct"))
    )
    (proposal,) = proposals
    assert proposal.basis == "moved" and proposal.needs_review and proposal.confidence <= 0.8
    assert match_moved(items(("a", "Ethics")), items(("z", "Audit"))) == []


def test_thresholds_are_ordered_sensibly():
    assert matching.LOW < matching.HIGH < matching.MOVED_FLOOR <= 1.0
