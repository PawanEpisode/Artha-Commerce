from django.test import SimpleTestCase

from modules.questionbank.domain.pdf_ingest import review


class ApplyDecisionTests(SimpleTestCase):
    def test_no_decision_changes_nothing(self):
        self.assertEqual(review.apply_decision("Q", "A", ["r"], None), ("Q", "A", ["r"], None))

    def test_approve_clears_reasons_and_records_who(self):
        stem, sol, reasons, ev = review.apply_decision(
            "Q", "A", ["typeset confidence medium"], {"verdict": "approve", "reason": "matches print"}
        )
        self.assertEqual((stem, sol, reasons), ("Q", "A", []))
        self.assertEqual(ev["by"], review.REVIEWER)

    def test_approve_applies_corrected_text(self):
        _s, sol, reasons, _ev = review.apply_decision(
            "Q",
            "A 100",
            ["x"],
            {"verdict": "approve", "reason": "fixed a figure", "explanation_md": "A 110"},
            check=False,
        )
        self.assertEqual((sol, reasons), ("A 110", []))

    def test_bad_corrected_text_is_not_used_and_item_stays_draft(self):
        _s, sol, reasons, _ev = review.apply_decision(
            "Q",
            "A",
            [],
            {"verdict": "approve", "reason": "fixed", "explanation_md": r"$\includegraphics{x}$"},
            check=False,
        )
        self.assertEqual(sol, "A")
        self.assertTrue(reasons)

    def test_approve_with_empty_solution_stays_draft(self):
        _s, _t, reasons, _ev = review.apply_decision("Q", "", [], {"verdict": "approve", "reason": "ok"})
        self.assertTrue(reasons)

    def test_hold_keeps_reasons_and_adds_the_reviewers(self):
        _s, _t, reasons, _ev = review.apply_decision("Q", "A", ["a"], {"verdict": "hold", "reason": "needs merging"})
        self.assertEqual(reasons[0], "a")
        self.assertIn("needs merging", reasons[-1])


class NumericKeyTests(SimpleTestCase):
    def test_null_means_not_numeric(self):
        self.assertIsNone(review.numeric_key_from({"numeric_key": None}))

    def test_key_is_normalised(self):
        key = review.numeric_key_from({"numeric_key": {"numeric_value": "24,000,000", "unit": "₹"}})
        self.assertEqual(key["numeric_value"], "24000000")
        self.assertEqual(key["tolerance_rel"], "0.01")
