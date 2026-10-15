# Question Bank, Practice Engine, Past Papers (PYQ) and MCQ Bank: build waves

Source:
- `docs/product/prd/F-06-question-bank-system.md` and `docs/product/erd/F-06-question-bank-system.md`
- `docs/product/prd/F-09-previous-year-questions.md` and `docs/product/erd/F-09-previous-year-questions.md`
- `docs/product/prd/F-05-mcq-bank.md` and `docs/product/erd/F-05-mcq-bank.md` (including F-06 extensions E-F06-1..4)
Written: 2026-10-15. R1 delivers the foundation (`questionbank`, `practice`, shared `media`), the past paper layer (`pyq`), and the MCQ preset layer (`mcqbank`), backing catalog feature `past-papers`.

---

## 0. What the repo already has, and what that changes

| Finding | Effect on the plan |
| --- | --- |
| `core/events.py` is a synchronous in-memory bus (`subscribe/emit`, `on_commit` handler), not the ERD's outbox tables (`core_domainevent`, `core_eventdelivery`). | **Keep the synchronous bus for R1.** Standardise the event envelope `{"id", "name", "v", "occurred_at", "user_id", "key", "payload"}` and store strict JSON Schemas in `apps/api/core/event_schemas/<name>.v1.json`. Swap to the database outbox in a later wave without modifying event consumers. |
| `core/jobs.py` exists (durable Postgres queue `core_job`, `enqueue`, `claim_next` with `SKIP LOCKED`, heartbeat, worker supervision). | F-06 background work (`practice.autoclose`, `questionbank.stats`, `questionbank.remap`, `practice.regrade`, `media.scan`) registers directly into `core/jobs.py`. No new job table needed. |
| `core/richtext.py` already defines the `QUESTION` profile (20,000 chars, max 12 images, 40 rows x 12 cols, headings disallowed, alt text required). | Rich text linting and text extraction for question stems, options, and explanations reuse `core/richtext.py` directly; test against the shared conformance corpus `core/tests/richtext_cases.json`. |
| `apps/api/modules/media` already exists with model `Attachment` (`media_attachment`) and pluggable `registry.register_kind(spec: KindSpec)`. | `questionbank` and `practice` register their kinds (`question_media`, `answer_sheet`, `import_file`, `export_file`) in `media.registry` in `AppConfig.ready()`. No database schema changes needed in `media`. |
| `core/question_port.py` (Recall W4-3) and `core/suggestion_source_port.py` (Recall W5-5) exist as stand-ins waiting for F-06. | In W2, `practice` registers `core.question_port.register_question_provider` and `core.suggestion_source_port.register_suggestion_source("wrong_answers", ...)`, unblocking Recall's card-from-mistake and AI suggestion paths. |
| Today provider hook (`core/today_port.py` / `today.registry` F13-5). | In W2, register a lightweight practice provider with Today (`today.registry.register_task_provider`) to suggest unattempted or revision chapter practice. |
| Coverage events (`coverage.services.record_event`). | F-06 practice session completions emit `practice_session_completed`; the coverage subscriber calls `record_event` with `practice_done`, `mock_done`, or `revision_done` idempotently using deterministic `client_id`s. |
| Tracker auto-time subscriber (F-01.2). | `practice_session_completed` triggers auto-session recording if the student has auto-capture on and no overlapping live timer; requires nullable `source_ref` on `tracking_studysession` (already reserved in ERD F-01.2). |
| Web infrastructure (`src/lib/offline-queue`, `RichText`, `kv-store`, `retry`). | Web practice engine uses the shared `offline-queue` with scope `practice` for offline answer saving and queued submissions. |
| Catalog entry `past-papers` in `apps/web/src/modules/catalog/features.ts` has status `soon`. | At the end of W5, flip `past-papers` to `live` gated by flag `question_bank` with `tool: { to: '/app/practice', cta: 'Start practising', flag: 'question_bank' }`, update landing story ordering and test. |

---

## 1. Waves (R1)

Each wave is independently shippable: automated tests green, behind a feature flag, nothing user-visible until its flag is on.

| Wave | Slices | Delivers | Exit check |
| --- | --- | --- | --- |
| **W1 Content engine (API)** | F-06 S1–S7 | `questionbank` app with schema (question, version, option, answerkey, rubric, rubricstep, questiontopic, tag, questiontag, versionmedia, fingerprint, duplicatelink, review, report, verification, auditlog), pure domain (markdown/math lint, fingerprinting, simhash, numeric parsing, kind registry with 7 kinds: `mcq_single`, `mcq_multi`, `true_false`, `numeric`, `case_study`, `long_form`, `practical`), services (create draft, save, versions, publish, mapping, audit, `upsert_from_source`), selectors (filters, keyset pagination, search, facets, CDN-cached public endpoints), flag `question_bank` (fail-closed), API contract doc `docs/QB-API-CONTRACT.md` with drift test. | `pytest modules/questionbank` green; migrations apply cleanly; RLS deny-all tests pass; 80-fixture rich text conformance corpus passes; answer keys never leak in playable endpoints; contract drift test green. |
| **W2 Practice engine (API)** | F-06 S10–S12, S15, E-F06-1, E-F06-4 | `practice` app with schema (`practice_session`, `practice_attemptanswer` monthly partitioned on `created_at`, `practice_questionstate` with `chapter_id`, `practice_dailyrollup`, `practice_scoringrule`, `practice_settings`), partition maintenance command `ensure_practice_partitions`, pure grading and scoring (negative marking, partial credit modes, numeric tolerance, frozen snapshot, property tests), services (pickers: `filter`, `wrong_only`, `unattempted`, `collection`, `explicit_items`; create, save, check, pause, submit, retake, mistake tags, tick command), event bus integration, idempotent coverage & tracker subscribers, register `core.question_port` and `core.suggestion_source_port` ("wrong_answers"), Today practice provider hook. | `pytest modules/practice modules/coverage` green on SQLite and PostgreSQL; partition creation & routing verified; property test "session score equals sum of item marks" passes; coverage receives `practice_done`/`revision_done`; Recall question card port responds 200. |
| **W3 Web browse and practice** | F-06 S8, S9, S13, S14 | Design system components (`Sheet`, `Combobox`, `TagInput`, `FilterChip`, `NumberGrid`, `Countdown`, `SegmentedBar`) with showcase and contrast checks; web `questionbank` module (question browser with URL-bound filters, question detail, public chapter SEO pages); web `practice` module (test builder, player for MCQ, numeric, case study, offline answer queue on `src/lib/offline-queue`, session hub, review screen, mistakes list, bookmarks, mistake reason tagging, report error dialog); mount `QuestionCardButton` on Recall wrong answers screen. | `pnpm check` and `pnpm check:contrast` green; all 4 themes verified at 320 to 1280 px; offline answers survive reload and sync cleanly; instant feedback and at-end review work without key leakage. |
| **W4 Editors, admin and Past Papers (F-09 R1)** | F-06 S16, F-09 S1–S6 | Staff editor UI, CSV import for questions, admin review queue, error reports, duplicate resolution, verified-by badge. Then `pyq` module: migrations (`pyq_paper`, `pyq_choicegroup`, `pyq_paperquestion`, `pyq_paperlink`), admin integration, `artha.paper.v1` import service with dry-run and publish checks (calling F-06 `upsert_from_source`), selectors and read API, web PYQ home (`/app/pyq`), subject terms list, paper page (link-out default), practice paper & chapter sessions with self-grading, public SEO pages (`/courses/.../previous-year-questions`). Flag `pyq_bank`. | F-06 R1 complete. `pytest modules/pyq modules/questionbank` green; `artha.paper.v1` import idempotent; paper sessions launch in F-06 player; public PYQ pages render server-side with `buildHead`; no `user_id` columns in `pyq`. |
| **W5 MCQ Bank and launch (F-05 R1)** | F-05 S2–S9, Launch | `mcqbank` module: schema (`mcqbank_set`, `mcqbank_patternprofile`, `mcqbank_refsource`), selectors (`chapter_tiles`, pure `suggest_quick_set` ranking), pickers `mcq_set` and `mcq_blueprint`, set catalogue (hosted and link-out), negative-marking display; web containers (MCQ home `/app/mcq`, subject and chapter views, public subject page with sitemap); flag `mcq_bank`. Launch steps: catalog entry `past-papers` flipped to `live` (flag-gated), landing story updated & test passed, workspace nav link added, `docs/QB-ROLLOUT.md` runbook written, BUILD-TRACKER updated, CLAUDE.md product status updated. | Full monorepo check: `pnpm check`, `pnpm lint:api`, `pnpm test:api` green; landing story test passes; flags `question_bank`, `pyq_bank`, `mcq_bank` ready at 0%. |

---

## 2. Out of scope for these 5 waves (planned for R2 / R3)

| Feature | Scope deferred to later releases |
| --- | --- |
| **F-06 Question Bank System** | R2: Student community contributions, moderation SLA queue, public submission levels, copyright takedown intake form, collections and saved filters, shareable capability links, long-form photo upload pipeline (`media.scan` with Pillow/ClamAV), self-grading against rubric, F-07 AI hook (`apply_evaluation`), regrade jobs, question stats batch ("62% correct").<br>R3: Spaced re-ask (Leitner boxes), QTI 3.0 import/export, semantic search via pgvector/embeddings, anonymous 5-question try. |
| **F-09 Previous Year Questions** | R2: "Asked N times" chips and frequency sort (dependent on F-11 `asked_summary`), F-08 paper runner hand-off for strict exam simulation, spaced re-ask hub card, "Law as of" annotations from F-14 amendments.<br>R3: Daily 5 challenge generator and picker (dependent on X-03 gamification), legacy sittings (10–15 years back), offline term packs. |
| **F-05 MCQ Bank** | R2: Exam-pattern tests (`mcqbank_patternprofile` generation), chapter blueprint with custom difficulty mixes, negative-marking insights, bare-act reference links, F-14 amendment filters.<br>R3: Elo-based adaptive practice chain (`mcqbank_abilityestimate`), "Add to recall" bridge. |
| **Cross-cutting modules** | F-07 AI Evaluation, F-08 Mock Tests, F-04 Super 50, F-10 Performance Analytics, F-11 Paper Analysis, X-04 Ingestion Pipeline. |

---

## 3. Decisions taken (defaults)

1. **Synchronous event bus for R1:** Keep `core/events.py` as an in-memory synchronous bus with try/except logging and `transaction.on_commit` dispatch. Standardise the event payload envelope and schemas now in `core/event_schemas/<name>.v1.json` so the swap to database outbox tables (`core_domainevent`, `core_eventdelivery`) requires zero consumer modifications.
2. **Media attachments:** Reuse existing `modules/media` and register `question_media`, `answer_sheet`, `import_file`, `export_file` via `media.registry.register_kind`. No new tables or schema changes in `media`.
3. **Partitioning on `practice_attemptanswer`:** Monthly range partitioning on `created_at` created via Django migration `RunSQL`. `created_at` is set to the session's creation time for all its rows, satisfying PostgreSQL's requirement that partition keys belong to unique constraints and ensuring single-partition pruning. SQLite test runner uses a non-partitioned table fallback or raw table creation.
4. **Scoring rules data-driven:** No negative marking value or exam duration is hard-coded in Python. All scoring rules come from `practice_scoringrule` with `verified=False` by default; only verified rules are applied when `scoring_profile="official"`.
5. **Separation of concerns:** `pyq` and `mcqbank` own ZERO question or attempt rows. All questions live in `questionbank`, all attempts in `practice`.
6. **Feature flags fail closed:** `question_bank`, `pyq_bank`, and `mcq_bank` fail closed (403 `feature_disabled` on API, hidden in web nav). Public marketing and SEO pages remain accessible without flags.

---

## 4. Open items for the owner (confirm before build)

| # | Question | Recommended default | Impact |
| --- | --- | --- | --- |
| 1 | **Events: Database Outbox vs Sync Bus for R1?** | **Keep sync bus for R1**, add JSON schemas in `apps/api/core/event_schemas/` and standard envelope. Build outbox tables in a later wave. | Eliminates unnecessary worker queue overhead during initial R1 feature build while keeping consumer contracts 100% compliant. |
| 2 | **Media: Does existing `modules/media` suffice?** | **Yes, it completely suffices.** Register `question_media`, `answer_sheet`, `import_file`, `export_file` via `media.registry.register_kind`. | Avoids touching or duplicating the existing stable `media` app. |
| 3 | **Feature flag names?** | `question_bank` (F-06), `pyq_bank` (F-09), `mcq_bank` (F-05). | Matches PRD specs and PostHog conventions. |
| 4 | **Licensing posture for hosted PYQ solutions?** | Default to `link_out` for Institute materials with official deep links; allow `hosted` only for platform-original explanations or verified licensed content. | Protects against copyright claims while delivering full study value. |
| 5 | **Which sittings to seed first for PYQ?** | Last 3 sittings (e.g. June 2024, Dec 2024, June 2025) of CMA Intermediate and Final in the current syllabus 2022 scheme. | Provides immediate high-yield pilot data without massive manual authoring backlog. |

---

## 5. Status

| Wave | State | Notes |
| --- | --- | --- |
| **W1 Content engine (API)** | Built | Slices 1–7: F-06 models (28 tables), pure domain (numeric parse, fingerprinting, simhash, content linting, 7 kind specs), services, selectors, views & serializers, RLS test, contract doc `docs/QB-API-CONTRACT.md` with drift test. 65 unit/integration tests passing. Ruff check and format clean. |
| **W2 Practice engine (API)** | Built | Slices 10–12, 15, E-F06-1, E-F06-4: `practice` models (9 tables), partitioned attempts, pure scoring & grading domain, session lifecycle & option shuffling, pickers, services, selectors (E-F06-1 chapter progress, state stamp), views & URLs behind `question_bank` flag, 0 answer leak verified, event bus subscribers, `core.question_port`, `core.suggestion_source_port`, and `core.today_port` integrations. 39 unit/integration tests passing. Ruff check and format clean. |
| **W3 Web browse and practice** | Built | Slices 8, 9, 13, 14: DS primitives (`Combobox`, `TagInput`, `NumberGrid`, `Countdown`, `SegmentedBar`), DS showcase, `pnpm check:contrast` 100%, web `questionbank` module (browser, detail, public SEO chapter questions), web `practice` module (hub, builder, player with 0 answer leakage, offline queue `scope: 'practice'`, review screen, mistakes list, bookmarks, mistake reason tagging, report dialog), 9 TanStack Start routes under `/app/questions*`, `/app/practice*`, `/courses*`. `pnpm check` and `build:web` green. |
| **W4 Editors, admin and Past Papers** | Planned | F-06 slice 16 + F-09 slices 1–6: PYQ app, imports, paper practice, SEO. |
| **W5 MCQ Bank and launch** | Planned | F-05 slices 2–9: MCQ app, sets, presets, landing beat, catalog status live. |
