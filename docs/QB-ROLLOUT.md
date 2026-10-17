# Question Bank, Practice Engine, PYQ and MCQ Bank: beta rollout runbook

Flags `question_bank`, `pyq_bank`, and `mcq_bank` stay **off** (at 0%) until you open the cohort. Everything below is safe to do with the flags off.

---

## 1. Before opening the cohort

1. **Run full monorepo check and test suite**:
   - `pnpm check`
   - `pnpm lint:api`
   - `cd apps/api && pytest modules/questionbank modules/practice modules/pyq modules/mcqbank`

2. **Deploy and apply migrations**:
   - `python manage.py migrate`
   - Applies:
     - `questionbank.0001_initial`
     - `practice.0001_initial`
     - `pyq.0001_initial`
     - `pyq.0002_schema_alignment`
     - `mcqbank.0001_initial`
     - `mcqbank.0002_seed`

3. **Ensure monthly partitions for practice attempts**:
   - On PostgreSQL:
     ```bash
     python manage.py ensure_practice_partitions --months-ahead 3
     ```
   - (Note: on local SQLite tests, non-partitioned tables are automatically used; on PostgreSQL, this ensures future monthly tables exist for `practice_attemptanswer`).

4. **Seed authentic CMA Intermediate & Final materials**:
   - Past examination papers (June 2024, Dec 2023, June 2023 with official ICMAI PDF links, section trees & choice rules):
     ```bash
     python manage.py seed_cma_pyq
     ```
   - MCQ Bank presets, official ICMAI Directorate of Studies MCQ booklets, and high-yield platform sprint:
     ```bash
     python manage.py seed_mcq_bank
     ```

5. **Schedule periodic partition maintenance**:
   - Add a monthly or weekly cron / scheduled job:
     ```bash
     python manage.py ensure_practice_partitions --months-ahead 3
     ```

---

## 2. Content Ingestion & Management Paths

Content can be added and managed in three ways:

1. **Seed Management Commands**:
   - `python manage.py seed_cma_pyq`: Seeds verified ICMAI exam papers with links and question trees.
   - `python manage.py seed_mcq_bank`: Seeds verified CMA 2022 exam pattern profiles (15 MCQs x 2 marks = 30 marks) and booklets.

2. **Staff Web UI (Bulk CSV Importer & Review Queue)**:
   - Navigate to `/app/questions/editor` (requires staff permission `questionbank.manage_questions` or `is_staff`).
   - Use the **Bulk CSV Upload** dialog to import questions in bulk.
   - Questions arrive in draft/pending status and appear in the review queue for staff verification and approval before publishing.

3. **Automated API Ingestion (`artha.paper.v1`)**:
   - Staff endpoint `POST /api/v1/pyq/editor/papers/import/` accepts complete paper trees (sections, choice groups, questions, sub-questions, official links) with dry-run support.
   - Questions are upserted cleanly into `questionbank` and indexed into `pyq`.

### 2.1 CMA Final seeds from the Institute PDFs

The committed JSON under `apps/api/modules/questionbank/seed/cma-final/` is the reviewable source of truth; the PDFs stay in
`docs/source-material/` and are only needed to rebuild it.

| Folder | What | Built by | Needs |
|---|---|---|---|
| `mcq/pNN.json` | MCQ banks, one `mcq_single` per row, key matched by exact answer text | `build_question_bank_seed --kind mcq` | `pdfplumber` |
| `workbook/pNN.json` | Workbook illustrations as `long_form` (solution in `explanation_md`), `numeric` only for a single-number answer. Marks are inferred (7) and flagged `marks_source: inferred` | `build_question_bank_seed --kind workbook` | poppler (`pdftotext`, `pdfimages`) |
| `pyq-transcriptions/` | Question papers are scans, so these were transcribed from the page images and paired with the suggested answers | read by a person or model, checked by `build_pyq_seed` | none |
| `pyq/pNN-YYYY-MM.json` | One `artha.paper.v1` paper per paper and term | `build_pyq_seed` | none |

Each folder has a `pNN.needs-review.md` listing items to check by hand.

```
python manage.py load_question_bank_seed --dry-run                # report only, everything rolled back
python manage.py load_question_bank_seed [--paper 14] [--kind mcq|workbook|pyq]
python manage.py load_question_bank_seed --publish                # publishes confirmed items only
python manage.py repair_question_bank --dry-run                   # then without --dry-run, after reading the report
```

Rules the loader keeps: it goes through `upsert_from_source` and `pyq.services.import_paper`, so a rerun creates nothing;
anything with a doubt (key not matched, transcriber note, no answer published) loads as an unpublished draft and is never
published, even with `--publish`; an item the question kinds cannot hold as a draft (an MCQ with no key at all, a workbook
item with no solution) is skipped and reported with the reason; a paper is published only when none of its parts is in doubt.
An empty paper shell left by the early `seed_cma_pyq` command is adopted (its links are kept); a paper that already has
questions is never touched.

Order on the dev database: `load_question_bank_seed --dry-run`, read the report, load, then `repair_question_bank --dry-run`
and read it before running it for real.

---

### 2.2 Workbook mathematics (typeset overlay)

The workbooks print solutions as stacked fractions, powers, roots and aligned `=` rows. Plain text extraction flattens
them ("(1.10)2", "Standard deviation = 10.95 = 0.146 / Mean 75"), so the extracted text alone is not shown to students.
Each workbook item is re-written as Markdown + KaTeX from the page image and stored in
`seed/cma-final/workbook-typeset/pNN.json` (`artha.qbtypeset.v1`, one entry per `external_ref`, with the transcriber's
`confidence` and `review` notes). `build_question_bank_seed --kind workbook` merges the overlay; the PDF text is the
fallback and is flagged for review when an overlay entry is missing or fails a gate.

* Hard gates (the entry is rejected): empty text, editor lint errors, a formula KaTeX cannot parse (`check_katex.mjs`
  runs the same KaTeX as the web app; skipped with a review note when node is unavailable).
* Soft gates (the item loads as draft): figures of the PDF text missing from the typeset text or the reverse (flattened
  exponents are tolerated), noticeably different wording, medium/low transcriber confidence.
* The institute's misprints are kept as printed. They are listed in `evidence.typeset_notes` of the seed item, not
  corrected.
* The overlay text is normalised so the web renderer shows it as written: a multi-line `$$` block has its fences on their
  own lines, a printed `$` inside inline math is written `\char"24`, `[x](y)` shaped text has its `(` escaped, a table
  has a blank line before it.
* Previews and search read formulas as words (`math_to_text`); the stored Markdown is untouched.

To redo a paper: re-run the transcription for the changed pages, replace its overlay file, rebuild and reload.

### 2.3 Past-paper and MCQ-bank mathematics (same overlay pipeline)

The same gates (`typeset.apply_text`: lint, KaTeX parse, figure and wording drift, confidence) apply to the other two sources.

- **PYQ**: `seed/cma-final/pyq-typeset/<paper>-<term>.json` (schema `artha.qbtypeset.v1`, keyed by part reference such as `4(b)`; fields `stem_md`, `options`, `answer_md`, `confidence`, `review`). `build_pyq_seed` applies it inside `pyq.build_paper`; a hard failure keeps the extracted text and drafts the part. Review decisions live in `seed/cma-final/pyq-review/<paper>-<term>.json` (`artha.qbreview.v1`: `verdict`, `reason`, `fixes`, optional `stem_md`, `answer_md`, `options`, and `correct` ONLY for an MCQ that has no stored key). Approve clears the reasons only when nothing is still missing; hold keeps them. A stored MCQ key is never changed by a decision.
- **MCQ bank**: `seed/cma-final/mcq-typeset/<paper>.json` (keyed by `external_ref`; `stem_md`, `options`, `confidence`, `review`). Apply it onto the committed seeds with `build_question_bank_seed --kind mcq --overlay-only`, which never re-parses the PDFs and so can never change an answer key (a full re-parse depends on the pdfplumber version and may read the key cells differently).
- Institute misprints stay as printed; they are recorded in `evidence.typeset_notes` / `review_decisions[...].printed_issues`, not corrected.
- Parts the Institute credits with several options (printed key `(A/B)` or `(A/B/C/D)`) stay drafts by design: there is no single key to publish.

### 2.4 Owner overrides, case scenarios and workbook supplements

- **Keep every input folder committed** (`pyq-typeset`, `pyq-review`, `mcq-typeset`, `workbook-typeset`, `workbook-review`, `pyq-overrides`, `workbook-supplement`). They are inputs to the builders, not scratch; only the generated `*.needs-review.md` reports can be recreated.
- **`pyq-overrides/<paper>-<term>.json`** (`artha.qboverride.v1`) holds fields you fixed by hand in a generated PYQ seed (stem, options, kind, solution, publish, mapping). `build_pyq_seed` applies them last, recomputes `answers_status` and drops the draft report entry for any part that is now publishable. A rebuild therefore never loses a hand edit. To fix more parts, edit the seed JSON as before and ask for the override file to be regenerated, or add the part to the override file directly.
- **Case scenarios**: consecutive MCQs of one question whose stems open with the same text (at least 120 characters) are one case group. Each stem is rewritten as a blockquote `> **Case scenario** · questions (xi) to (xv)` followed by the scenario (tables included) and then the question's own text; the seed records `case_groups`. Pipe-less tables are rewritten as standard tables.
- **`workbook-supplement/<paper>.json`** (`artha.qbsupplement.v1`) records layout decisions the parser cannot make: `merge` two illustrations into one item, `insert` an illustration the cut swallowed, `patch` review evidence. Apply in place with `build_question_bank_seed --kind workbook --paper 19 --supplement-only` (idempotent); a full rebuild applies it too.
- `mapping_state: pending` has no effect on what students see today; it only records that the classifier was below the confidence threshold.

## 3. Security, Privacy & Integrity Invariants

- **Zero Answer Leakage**: Active practice sessions and unsubmitted question payloads strictly scrub `answer_key`, correct options, and explanations. Only submitted sessions or explicit check requests reveal answer keys and explanations.
- **Fail Closed**: If flags `question_bank`, `pyq_bank`, or `mcq_bank` are disabled for a user, API endpoints return 403 `feature_disabled` and workspace navigation hides the links. Public marketing and SEO routes remain accessible.
- **Privacy Separation**: The `pyq` module contains zero `user_id` columns. All attempts and student answers live in `practice`. `mcqbank` owns zero question or attempt tables, functioning as a clean preset layer over F-06 and F-09.

---

## 4. Opening the cohort

1. Enable `question_bank`, `pyq_bank`, and `mcq_bank` in PostHog for the beta cohort (e.g., initial 50 students).
2. Monitor key events:
   - `practice_session_started`, `practice_session_completed`
   - `pyq_paper_opened`, `pyq_practice_started`
   - `mcq_set_started`, `mcq_quick_drill_started`
   - Error rates and 403 / 500 status codes.
3. Verify that coverage events (`practice_done`, `revision_done`) and tracker auto-sessions are properly emitted and recorded.

---

## 5. Rollback

- Set flags `question_bank`, `pyq_bank`, and `mcq_bank` to 0% in PostHog.
- Active data is preserved in PostgreSQL.
- API endpoints immediately fail closed with 403 `feature_disabled`.
