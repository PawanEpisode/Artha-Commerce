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

---

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
