from modules.recall.domain import question_card as qc


def test_front_asks_for_the_rule_and_back_quotes_the_explanation_with_its_source():
    f = qc.build_fields("ITC is blocked on motor cars.", ["Section 17(5), CGST Act"])
    assert f == {
        "prompt_md": "What is the rule in Section 17(5), CGST Act?",
        "answer_md": "ITC is blocked on motor cars.\n\nSource: Section 17(5), CGST Act",
    }


def test_two_labels_are_joined_and_extra_ones_dropped():
    f = qc.build_fields("x", ["A", "B", "C", "D"])
    assert f["prompt_md"] == "What is the rule in A and B and C?"


def test_duplicate_blank_and_long_labels_are_cleaned():
    assert qc.labels_of(["  A  ", "A", "", "B " * 100])[0] == "A"
    assert len(qc.labels_of(["word " * 100])[0]) <= qc.LABEL_MAX + 1


def test_the_source_label_is_added_in_brackets():
    f = qc.build_fields("Because.", ["Section 9"], "ICAI RTP May 2026")
    assert f["answer_md"].endswith("Source: Section 9 (ICAI RTP May 2026)")


def test_no_labels_still_makes_a_card_from_the_explanation():
    f = qc.build_fields("The rule is X.", [])
    assert f == {"prompt_md": "What rule did this question test?", "answer_md": "The rule is X."}


def test_nothing_to_quote_makes_no_card():
    assert qc.build_fields("   ", []) is None
    assert qc.build_fields("", [""]) is None


def test_a_label_alone_is_enough():
    f = qc.build_fields("", ["Section 9"])
    assert f == {"prompt_md": "What is the rule in Section 9?", "answer_md": "Source: Section 9"}


def test_headings_images_and_blank_runs_are_flattened():
    f = qc.flatten("## Rule\n\n\n\n![chart](http://x/y.png) applies\r\n# Note")
    assert f == "Rule\n\nchart applies\nNote"


def test_a_long_explanation_is_cut_on_a_word_with_an_ellipsis():
    f = qc.build_fields("word " * 1000, ["S"])
    body = f["answer_md"].split("\n\nSource:")[0]
    assert body.endswith("…") and len(body) <= qc.EXPLANATION_MAX + 1 and "wor…" not in body


def test_the_function_is_pure_and_stable():
    a = qc.build_fields("Same.", ["S"], "src")
    assert a == qc.build_fields("Same.", ["S"], "src")
