import copy

import pytest

from modules.pyq.domain.importer import validate_paper_payload
from modules.questionbank.domain.pdf_ingest.pyq import TranscriptionError, build_paper, term_title

SUBJECT = {
    "key": "strategic-financial-management",
    "name": "Strategic Financial Management",
    "paper_number": 14,
    "chapters": [
        {
            "key": "leasing-decisions",
            "name": "Leasing Decisions",
            "topics": [{"name": "Finance lease"}, {"name": "Lease rental"}],
        },
        {"key": "mutual-funds", "name": "Mutual Funds", "topics": [{"name": "Net asset value"}]},
    ],
}


def _mcq(label, correct="B"):
    return {
        "label": label,
        "kind": "mcq_single",
        "marks": 2,
        "stem_md": "What is the lease rental for a finance lease?",
        "options": ["A", "B", "C", "None of the above"],
        "correct": correct,
        "answer_md": "",
    }


TRANSCRIPTION = {
    "schema": "artha.pyq-transcription.v1",
    "paper": "14",
    "term_code": "2024-06",
    "total_marks": 18,
    "duration_minutes": 180,
    "answers_source": "suggested_answer_pdf",
    "sections": [
        {
            "label": "Section A",
            "choice": {"rule": "compulsory"},
            "questions": [
                {
                    "number": "1",
                    "marks": 4,
                    "intro_md": "Choose the correct option. 2x2=4",
                    "parts": [_mcq("i"), _mcq("ii", "C")],
                }
            ],
        },
        {
            "label": "Section B",
            "choice": {"rule": "any_n_of_m", "pick": 1, "of": 2},
            "questions": [
                {
                    "number": "2",
                    "marks": 14,
                    "parts": [
                        {
                            "label": "a",
                            "kind": "long_form",
                            "marks": 7,
                            "stem_md": "Compute the net asset value of the mutual fund.",
                            "answer_md": "NAV = ₹ 10.50",
                        },
                        {
                            "label": "b",
                            "kind": "long_form",
                            "marks": 7,
                            "stem_md": "Explain the finance lease.",
                            "answer_md": "A finance lease transfers risk.",
                        },
                    ],
                },
                {
                    "number": "3",
                    "marks": 14,
                    "parts": [
                        {
                            "label": "",
                            "kind": "long_form",
                            "marks": 14,
                            "stem_md": "Discuss lease rental.",
                            "answer_md": "",
                        }
                    ],
                },
            ],
        },
    ],
}


def test_built_paper_passes_the_existing_importer_validation():
    built = build_paper(TRANSCRIPTION, subject=SUBJECT)
    payload = built["payload"]
    assert validate_paper_payload(payload) == []
    assert payload["external_ref"] == "pyq:cma-final:p14:2024-06"
    assert payload["title"] == "CMA Final June 2024: Strategic Financial Management (Paper 14)"
    assert [g["rule_kind"] for g in payload["choice_groups"]] == ["compulsory", "any_n_of_m"]


def test_tree_shape_and_refs():
    parts = build_paper(TRANSCRIPTION, subject=SUBJECT)["payload"]["parts"]
    by_label = {p["number_label"]: p for p in parts}
    assert set(by_label) == {"1", "1(i)", "1(ii)", "2", "2(a)", "2(b)", "3"}
    assert by_label["1"]["is_leaf"] is False and by_label["1(i)"]["parent_ref"] == "1"
    assert by_label["1(i)"]["ref_suffix"] == "q1i" and by_label["2(a)"]["ref_suffix"] == "q2a"
    assert by_label["3"]["is_leaf"] is True and by_label["3"]["depth"] == 0 and by_label["3"]["ref_suffix"] == "q3"


def test_mcq_key_and_long_form_answer_are_carried():
    parts = {p["number_label"]: p for p in build_paper(TRANSCRIPTION, subject=SUBJECT)["payload"]["parts"]}
    assert [o["is_correct"] for o in parts["1(ii)"]["options"]] == [False, False, True, False]
    assert parts["2(a)"]["reference_solution_md"] == "NAV = ₹ 10.50"
    assert parts["2(a)"]["answer_source"] == "icmai_suggested"


def test_missing_answer_makes_the_part_a_draft():
    built = build_paper(TRANSCRIPTION, subject=SUBJECT)
    parts = {p["number_label"]: p for p in built["payload"]["parts"]}
    assert parts["3"]["publish"] is False
    assert parts["2(a)"]["publish"] is True
    assert built["report"] == [{"part": "3", "reasons": ["no suggested answer was found for this part"]}]
    assert built["payload"]["answers_status"] == "partial"


def test_every_leaf_has_difficulty_and_chapter():
    for p in build_paper(TRANSCRIPTION, subject=SUBJECT)["payload"]["parts"]:
        if p["is_leaf"]:
            assert 1 <= p["difficulty"] <= 5 and p["chapter_key"] in {"leasing-decisions", "mutual-funds"}


def test_no_answers_pdf_means_no_review_noise_and_status_none():
    t = copy.deepcopy(TRANSCRIPTION)
    t["answers_source"] = "none"
    for s in t["sections"]:
        for q in s["questions"]:
            for part in q["parts"]:
                part["answer_md"] = ""
                part.pop("correct", None)
    built = build_paper(t, subject=SUBJECT)
    assert built["payload"]["answers_status"] == "none" and built["report"] == []
    # With no key or solution nothing can be published, and an unkeyed MCQ is kept as a long-form draft (options in the stem).
    leaves = [p for p in built["payload"]["parts"] if p["is_leaf"]]
    assert leaves and all(p["publish"] is False and p["kind"] == "long_form" for p in leaves)
    assert "(A) A" in leaves[0]["stem_md"]


def test_bad_transcription_is_rejected_with_reasons():
    bad = copy.deepcopy(TRANSCRIPTION)
    bad["sections"][0]["questions"][0]["parts"][0]["correct"] = "F"
    bad["sections"][1]["questions"][0]["parts"][0]["stem_md"] = " "
    with pytest.raises(TranscriptionError) as err:
        build_paper(bad, subject=SUBJECT)
    assert any("not one of the options" in i for i in err.value.issues) and any(
        "empty stem" in i for i in err.value.issues
    )


def test_choice_count_must_match_listed_questions():
    bad = copy.deepcopy(TRANSCRIPTION)
    bad["sections"][1]["choice"] = {"rule": "any_n_of_m", "pick": 5, "of": 7}
    with pytest.raises(TranscriptionError):
        build_paper(bad, subject=SUBJECT)


def test_term_title():
    assert term_title("14", "SFM", "2025-12") == "CMA Final December 2025: SFM (Paper 14)"


def _parts(**kw):
    return {p["number_label"]: p for p in build_paper(TRANSCRIPTION, subject=SUBJECT, **kw)["payload"]["parts"]}


def test_overlay_replaces_stem_and_answer_with_typeset_text():
    overlay = {"2(a)": {"answer_md": "$\\text{NAV} = \\text{₹ }10.50$", "confidence": "high"}}
    part = _parts(overlay=overlay)["2(a)"]
    assert part["reference_solution_md"] == "$\\text{NAV} = \\text{₹ }10.50$"
    assert part["publish"] is True


def test_overlay_with_hard_gate_failure_keeps_the_extracted_text_and_drafts_the_part():
    overlay = {"2(a)": {"stem_md": "$\\includegraphics{x}$"}}
    part = _parts(overlay=overlay)["2(a)"]
    assert part["stem_md"] == "Compute the net asset value of the mutual fund."
    assert part["publish"] is False


def test_overlay_medium_confidence_sends_the_part_to_review():
    built = build_paper(
        TRANSCRIPTION, subject=SUBJECT, overlay={"2(b)": {"confidence": "medium", "review": ["layout"]}}
    )
    assert any("typeset confidence medium" in r for item in built["report"] for r in item["reasons"])
    assert built["typeset_notes"]["2(b)"] == ["layout"]


def test_overlay_options_must_keep_the_count():
    overlay = {"1(i)": {"options": [{"key": "A", "body_md": "$x$"}]}}
    built = build_paper(TRANSCRIPTION, subject=SUBJECT, overlay=overlay)
    assert any("option count differs" in r for item in built["report"] for r in item["reasons"])


def test_decision_approve_clears_reasons_and_publishes():
    decisions = {"3": {"verdict": "approve", "reason": "x", "answer_md": "Lease rental is the periodic payment."}}
    built = build_paper(TRANSCRIPTION, subject=SUBJECT, decisions=decisions)
    part = {p["number_label"]: p for p in built["payload"]["parts"]}["3"]
    assert part["publish"] is True and built["report"] == []
    assert built["decisions"]["3"]["by"] == "claude-review"


def test_decision_approve_without_an_answer_stays_a_draft():
    built = build_paper(TRANSCRIPTION, subject=SUBJECT, decisions={"3": {"verdict": "approve", "reason": "x"}})
    part = {p["number_label"]: p for p in built["payload"]["parts"]}["3"]
    assert part["publish"] is False


def test_decision_hold_keeps_reasons_and_adds_the_reviewers():
    built = build_paper(
        TRANSCRIPTION, subject=SUBJECT, decisions={"2(b)": {"verdict": "hold", "reason": "needs a human"}}
    )
    part = {p["number_label"]: p for p in built["payload"]["parts"]}["2(b)"]
    assert part["publish"] is False
    assert any("review hold: needs a human" in r for item in built["report"] for r in item["reasons"])


def test_decision_can_set_a_missing_mcq_key_but_never_changes_a_stored_one():
    t = copy.deepcopy(TRANSCRIPTION)
    t["sections"][0]["questions"][0]["parts"][0]["correct"] = None
    decisions = {
        "1(i)": {"verdict": "approve", "reason": "key printed", "correct": "C"},
        "1(ii)": {"verdict": "approve", "reason": "x", "correct": "A"},
    }
    parts = {p["number_label"]: p for p in build_paper(t, subject=SUBJECT, decisions=decisions)["payload"]["parts"]}
    assert [o["is_correct"] for o in parts["1(i)"]["options"]] == [False, False, True, False]
    assert [o["is_correct"] for o in parts["1(ii)"]["options"]] == [False, False, True, False]  # stored C kept
    assert parts["1(i)"]["publish"] is True


def test_decision_text_failing_a_gate_is_not_used():
    decisions = {"2(a)": {"verdict": "approve", "reason": "x", "stem_md": "$\\includegraphics{x}$"}}
    built = build_paper(TRANSCRIPTION, subject=SUBJECT, decisions=decisions)
    part = {p["number_label"]: p for p in built["payload"]["parts"]}["2(a)"]
    assert part["stem_md"] == "Compute the net asset value of the mutual fund." and part["publish"] is False
