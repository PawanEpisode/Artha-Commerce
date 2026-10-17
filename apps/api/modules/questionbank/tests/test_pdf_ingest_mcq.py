from modules.questionbank.domain.pdf_ingest.mcq import match_answer, parse_mcq_tables

Q1 = ["1", "How many minimum members are required to form a public\nlimited company?", "3", "4", "6", "7"]
A1 = ["1", "How many minimum members are required to form a public\nlimited company?", "7"]
Q2 = [
    "2",
    "Foreign company is a company, registered out of India and_____",
    "Having a place of business in India",
    "Conducts any business in India",
    "Need not have any business in India",
    "Either (a) or (b)",
]
A2 = ["2", "Foreign company ...", "Either (a) or (b)."]


def test_questions_and_answers_are_rejoined_by_number():
    items, problems = parse_mcq_tables([["SL NO", "QUESTIONS", "OPTION 1", "OPTION 2", "OPTION 3", "OPTION 4"], Q1, A1])
    assert problems == []
    assert items[0].stem == "How many minimum members are required to form a public limited company?"
    assert items[0].correct_index == 3
    assert items[0].status == "ok"
    assert items[0].to_dict()["options"][3]["is_correct"] is True


def test_exact_match_ignores_punctuation_and_case():
    items, _ = parse_mcq_tables([Q2, A2])
    assert items[0].correct_index == 3 and items[0].status == "ok"


def test_unmatched_key_is_a_draft_with_evidence():
    q = ["3", "Stem", "Alpha", "Beta", "Gamma", "Delta"]
    a = ["3", "Stem", "Something else entirely"]
    items, _ = parse_mcq_tables([q, a])
    assert items[0].correct_index is None
    assert items[0].status == "needs_review"
    assert "Something else entirely" in items[0].review_reasons[0]


def test_missing_answer_row_and_blank_option_are_reported():
    q = ["4", "Stem", "A1", "A2", "", "A4"]
    items, _ = parse_mcq_tables([q])
    reasons = " ".join(items[0].review_reasons)
    assert "no row for this number" in reasons and "option C is empty" in reasons


def test_fuzzy_matches_are_never_trusted_without_review():
    idx, confidence, _ = match_answer(
        "Controller of Certifying Authorities", ["Controller of Certifying Authority", "x", "y", "z"]
    )
    assert idx == 0 and confidence == "fuzzy"
    items, _ = parse_mcq_tables(
        [
            ["5", "Stem", "Controller of Certifying Authority", "b", "c", "d"],
            ["5", "Stem", "Controller of Certifying Authorities"],
        ]
    )
    assert items[0].status == "needs_review" and items[0].correct_index == 0


def test_duplicate_options_make_the_key_ambiguous():
    idx, confidence, _ = match_answer("Same", ["Same", "same", "x", "y"])
    assert idx is None and confidence == "none"


def test_gaps_in_numbering_are_reported():
    _, problems = parse_mcq_tables([Q1, ["3", "Stem", "a", "b", "c", "d"]])
    assert any("missing" in p for p in problems)


def test_select_all_stems_are_flagged_multi():
    q = ["6", "Select all that apply: which are taxes?", "GST", "TDS", "Fee", "Fine"]
    items, _ = parse_mcq_tables([q, ["6", "x", "GST"]])
    assert items[0].kind == "mcq_multi" and items[0].status == "needs_review"
