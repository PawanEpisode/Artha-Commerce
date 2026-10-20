from modules.amendments.domain.checklist import check_word_overlap, validate_revision_release


def test_check_word_overlap_detects_20_words():
    quote = "the provisions of this section shall not apply to any taxable person who has opted to pay tax under section 10 of the act"
    # Exact 20 words
    words = quote.split()[:20]
    run = " ".join(words)
    summary = f"Notice that {run} in all situations."

    overlap = check_word_overlap(summary, quote, max_run=20)
    assert overlap is not None
    assert overlap == run


def test_check_word_overlap_ignores_short_overlap():
    quote = "the provisions of this section shall not apply"
    summary = "the provisions of this section shall apply"
    overlap = check_word_overlap(summary, quote, max_run=20)
    assert overlap is None


def test_validate_revision_release_success():
    res = validate_revision_release(
        state="staged",
        subject_count=1,
        term_count=1,
        change_versions=[
            {
                "title": "Section 17(5) amendment",
                "change_type": "modification",
                "has_mapping": True,
                "summary_new": "Our own clean summary in unique words.",
                "evidence_quote": "Official statutory text quoted here.",
            }
        ],
        official_url="https://boslive.icai.org/assets/statutory_update_may2026.pdf",
    )
    assert res.is_valid
    assert len(res.errors) == 0


def test_validate_revision_release_blocks_invalid_state():
    res = validate_revision_release(
        state="live",
        subject_count=1,
        term_count=1,
        change_versions=[{"change_type": "clarification", "has_mapping": False}],
    )
    assert not res.is_valid
    assert any("must be 'staged' or 'in_review'" in err for err in res.errors)


def test_validate_revision_release_requires_subjects_and_terms():
    res = validate_revision_release(
        state="staged",
        subject_count=0,
        term_count=0,
        change_versions=[],
    )
    assert not res.is_valid
    assert any("paper must be linked" in err for err in res.errors)
    assert any("exam term applicability" in err for err in res.errors)


def test_validate_revision_release_requires_mapping_for_non_clarifications():
    res = validate_revision_release(
        state="staged",
        subject_count=1,
        term_count=1,
        change_versions=[
            {"title": "Unmapped card", "change_type": "modification", "has_mapping": False},
            {"title": "Scope note", "change_type": "clarification", "has_mapping": False},
        ],
    )
    assert not res.is_valid
    # The modification card requires mapping; clarification does not
    assert any("Unmapped card" in err for err in res.errors)
    assert not any("Scope note" in err for err in res.errors)
