from django.test import SimpleTestCase

from modules.questionbank.domain.pdf_ingest import typeset

BOND = r"""$$
\begin{aligned}
\text{Value} &= \frac{2{,}400}{(1 + 0.15)^{1}} + \frac{22{,}400}{(1 + 0.15)^{2}} \\
&= \text{₹ } 9{,}71{,}800
\end{aligned}
$$"""


class FormulaTests(SimpleTestCase):
    def test_formulas_found_and_code_fences_ignored(self):
        md = "Cost is $x^2$.\n\n$$a=b$$\n\n```text\n$not math$\n```"
        found = typeset.formulas_of(md)
        self.assertEqual([(f.tex, f.display) for f in found], [("a=b", True), ("x^2", False)])

    def test_figures_ignore_commas_and_tex_grouping(self):
        self.assertEqual(
            typeset.figures("₹ 9,71,800 and 0.15"), typeset.figures(r"$\text{₹ } 9{,}71{,}800$ 0.15", tex=True)
        )


class GateTests(SimpleTestCase):
    def test_bond_example_renders_and_passes(self):
        fs = typeset.formulas_of(BOND)
        errs = typeset.katex_errors(fs)
        if errs is None:
            self.skipTest("node not available")
        self.assertEqual(errs, [None])
        res = typeset.gate("Value 2,400 1.15 22,400 9,71,800 0.15", BOND, katex=errs, formulas=fs)
        self.assertTrue(res.ok, res)

    def test_bad_command_is_a_hard_error(self):
        fs = typeset.formulas_of(r"$$\badcmd{1}$$")
        errs = typeset.katex_errors(fs)
        if errs is None:
            self.skipTest("node not available")
        self.assertTrue(errs[0])
        self.assertFalse(typeset.gate("x", r"$$\badcmd{1}$$", katex=errs, formulas=fs).ok)

    def test_changed_figures_warn(self):
        res = typeset.gate("Profit 55000 and 75000", "Profit 55000 and 99999", katex=[], formulas=[])
        self.assertTrue(res.ok)
        self.assertTrue(any("figures" in w for w in res.warnings))

    def test_overlay_missing_keeps_text_and_flags(self):
        stem, sol, reasons, done, _notes = typeset.apply_overlay("Q 100", "A 200", None)
        self.assertEqual((stem, sol, done), ("Q 100", "A 200", False))
        self.assertTrue(reasons)

    def test_overlay_rejected_on_bad_tex(self):
        stem, sol, reasons, done, _notes = typeset.apply_overlay(
            "Q 100", "A 200", {"explanation_md": r"$$\badcmd$$ 200"}
        )
        self.assertFalse(done)
        self.assertEqual(sol, "A 200")


class EscapeTests(SimpleTestCase):
    def test_link_like_text_is_escaped_outside_math_and_code(self):
        out = typeset.escape_link_like("ratio [DC](₹ 40) and $a[1](2)$\n```text\n[x](y)\n```")
        self.assertIn("[DC]\\(₹ 40)", out)
        self.assertIn("$a[1](2)$", out)
        self.assertIn("[x](y)", out)

    def test_empty_both_sides_is_not_an_error(self):
        _s, _t, reasons, done, _n = typeset.apply_overlay("Q 100", "", {"stem_md": "Q 100", "explanation_md": ""})
        self.assertTrue(done)
        self.assertEqual(reasons, [])


class FlattenedExponentTests(SimpleTestCase):
    def test_flattened_superscripts_do_not_warn(self):
        res = typeset.gate(
            "(1.10)2 and 152 and 1.084", r"$(1.10)^{2}$ and $15^{2}$ and $1.08^{4}$", katex=[], formulas=[]
        )
        self.assertFalse(any("figures" in w for w in res.warnings), res.warnings)


class NormalizeMathTests(SimpleTestCase):
    def test_display_fences_get_their_own_lines(self):
        out = typeset.normalize_math("Intro\n$$\\begin{aligned}\na &= 1\\\\\n&= 2\n\\end{aligned}$$\nafter")
        self.assertEqual(out, "Intro\n\n$$\n\\begin{aligned}\na &= 1\\\\\n&= 2\n\\end{aligned}\n$$\n\nafter")

    def test_single_line_display_is_left_alone(self):
        self.assertEqual(typeset.normalize_math("a $$x=1$$ b"), "a $$x=1$$ b")

    def test_dollar_inside_inline_math(self):
        self.assertEqual(
            typeset.normalize_math(r"$(10\% \times \$0.65)$ and $\text{US\$ 5}$"),
            r'$(10\% \times \char"24 0.65)$ and $\text{US\char"24  5}$',
        )

    def test_code_fences_untouched(self):
        md = "```text\n$$\na\n$$ \\$x\n```"
        self.assertEqual(typeset.normalize_math(md), md)


class TableSpacingTests(SimpleTestCase):
    def test_blank_line_before_and_after_a_table(self):
        out = typeset.table_spacing("1. Paid:\n| a | b |\n|---|---|\n| 1 | 2 |\n2. Next")
        self.assertEqual(out, "1. Paid:\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n2. Next")

    def test_tables_in_code_are_left_alone(self):
        md = "```text\ntext\n| a | b |\n|---|---|\n```"
        self.assertEqual(typeset.table_spacing(md), md)


def test_mcq_overlay_changes_text_but_never_the_key_and_drafts_on_doubt():
    from modules.questionbank.domain.pdf_ingest.seedbuild import apply_mcq_overlay

    stem, options, reasons, notes, done = apply_mcq_overlay(
        "Beta of the portfolio is Rp / sigma",
        ["Rp", "Both 1 and 2"],
        [],
        {
            "stem_md": "Beta of the portfolio is $R_p / \\sigma$",
            "options": [{"key": "A", "body_md": "$R_p$"}, {"key": "B", "body_md": "Both 1 and 2"}],
            "confidence": "medium",
            "review": ["subscripts read from print"],
        },
    )
    assert stem.startswith("Beta") and options == ["$R_p$", "Both 1 and 2"] and done
    assert notes == ["subscripts read from print"]
    assert any("typeset confidence medium" in r for r in reasons)


def test_mcq_overlay_ignores_options_when_the_count_differs_and_keeps_text_on_hard_failure():
    from modules.questionbank.domain.pdf_ingest.seedbuild import apply_mcq_overlay

    stem, options, reasons, _, done = apply_mcq_overlay(
        "Q", ["a", "b"], [], {"stem_md": "$\\includegraphics{x}$", "options": [{"key": "A", "body_md": "x"}]}
    )
    assert stem == "Q" and options == ["a", "b"] and not done
    assert any("rejected" in r for r in reasons) and any("option count differs" in r for r in reasons)
