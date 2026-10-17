from modules.questionbank.domain.pdf_ingest.chapters import ChapterDef, ChapterIndex, classify, classify_sequence

CHAPTERS = [
    ChapterDef(
        "investment",
        "Investment Decisions, Project Planning and Control",
        ("Net present value", "Payback period", "IRR"),
    ),
    ChapterDef("leasing", "Leasing Decisions", ("Finance lease", "Operating lease", "Lease rental")),
    ChapterDef("mutual", "Mutual Funds", ("Net asset value", "Expense ratio", "Sharpe ratio")),
    ChapterDef("forex", "Foreign Exchange Market", ("Spot rate", "Forward rate", "Exchange rate")),
]


def test_classifies_by_chapter_vocabulary():
    index = ChapterIndex(CHAPTERS)
    assert (
        classify(index, "Compute the net present value and payback period of the project").chapter_key == "investment"
    )
    assert classify(index, "Annual lease rental of a finance lease").chapter_key == "leasing"


def test_no_evidence_gives_zero_confidence():
    index = ChapterIndex(CHAPTERS)
    assert classify(index, "Which colour is the sky?").confidence == 0.0


def test_title_hint_wins_for_workbook_chapters():
    index = ChapterIndex(CHAPTERS)
    assert classify(index, "Compute the value.", title_hint="Foreign Exchange Market").chapter_key == "forex"


def test_sequence_uses_neighbours_for_unclear_questions():
    index = ChapterIndex(CHAPTERS)
    texts = [
        "Net present value of a project",
        "IRR and payback period",
        "What is the answer to this vague question?",
        "Finance lease or operating lease",
        "Lease rental amount",
        "Net asset value of a fund",
    ]
    keys = [c.chapter_key for c in classify_sequence(index, texts)]
    assert keys == ["investment", "investment", "investment", "leasing", "leasing", "mutual"]
    assert classify_sequence(index, texts)[2].confidence == 0.0


def test_sequence_allows_a_late_jump_back_when_the_evidence_is_strong():
    index = ChapterIndex(CHAPTERS)
    texts = [
        "Spot rate and forward rate",
        "Exchange rate quotation",
        "Net present value payback period IRR of the project",
    ]
    keys = [c.chapter_key for c in classify_sequence(index, texts, backward_cost=0.5)]
    assert keys[-1] == "investment"
