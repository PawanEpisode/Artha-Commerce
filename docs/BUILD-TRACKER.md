# Build tracker

One page for what is pending, what is next and what is parked. Updated 2026-10-08. Statuses marked "verified" were checked against the code on that date; "not verified" means taken from a document or from the owner and not confirmed in the repository.

**Review ritual.** Every time you close an item in section 1 or 3 (an X-01 check, an audit fix, a Wave 0-lite item), re-read section 2 (Desktop companion) and say whether anything unblocks it. The companion is parked on purpose, not forgotten.

## 1. X-01 close-out (before X-01 is called done)

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| X1 | Production QStash callback host. `NOTIFICATIONS_PUBLIC_BASE_URL` was set to `athacommerce-api...` (missing "r"); every callback returned Vercel 404 `DEPLOYMENT_NOT_FOUND` | Open, fix given 2026-10-07 | Steps: fix the env var, redeploy, cancel old QStash messages, check the Supabase sweeper secret `artha_sweep_url`, test a short round. Also check weekly-email unsubscribe links (same variable) |
| X2 | W2.7 device matrix (Android Chrome, iPhone tab, iPhone Home Screen, desktop Chrome, Edge, Firefox, Safari) | Not recorded | No "W2.7 device matrix" section in `docs/X-01-spike-results.md`. Gate G1 also needs the SQL delivery check (accepted ratio 0.98, p95 5 s) over two days, which only means something after X1 |
| X3 | P4 open spikes and W4.2 to W4.5 device checks: Edge, Firefox 151+, Windows, 15 minute hidden run (S4.3), keep awake from the pop-out (S4.4), `resizeTo` above the minimum, install offer and badge matrix | Not recorded | `floating_timer` is live (G4 met), so run and record these now |
| X4 | Rollout ladders for `push_notifications`, `keep_awake`, `floating_timer` | Not verified | Record the current percentage of each here |
| X5 | Sentry rule for `push_slo_breach` and PostHog dashboard from W2.7 | Not verified | |
| X6 | Safari declarative push (`NOTIFICATIONS_DECLARATIVE_PUSH`) | Parked | Stays off until spike S3 passes on a device |
| X7 | `content_published` alert | Parked | No emitter until a content module exists |
| X8 | Commit `docs/X-01-P5-DESKTOP-COMPANION.md`, `docs/BUILD-TRACKER.md`, `docs/SESSION-PROMPTS.md` and the pointer in `docs/X-01-ROLLOUT.md` | Open (owner commits) | |

## 2. Desktop companion (X-01 Phase 5): parked, tracked

| Item | Status |
| --- | --- |
| Gate G4 | Met (owner, 2026-10-07). Paste the exact insight value, the date `floating_timer` reached 100% and the feedback evidence into section 0 of the P5 document |
| Build document | Drafted: `docs/X-01-P5-DESKTOP-COMPANION.md`. Waiting for owner approval. No code written |
| Decisions taken | Companion wins alerts; API link code with PKCE; shared package `@artha/timer-ui`; Supabase Storage hosting; macOS and Windows first, Linux last; cloud signing for Windows; own Rust keep-awake command; app id `com.meetpawan.arthacommerce` |
| Long-lead items to start early | Apple Developer Program enrolment (days for an organisation), Windows signing eligibility check for India, Supabase bucket, PostHog flag `desktop_companion` at 0% |
| Start prompt | `docs/SESSION-PROMPTS.md`, prompt 3 |
| Revisit | At every review ritual (see top) and when F-03 R1 and F-15 R1 are in beta |

## 3. Audit Majors and Wave 0 (verified against the code, 2026-10-07)

Source: `docs/product/validation/F-02-F-01-implementation-audit-2026-10-05.md`.

| Id | Finding | Status now | Needed for Notes and Recall? |
| --- | --- | --- | --- |
| AUD-001 | Coverage writes lack row locks | Partly fixed: `select_for_update` now on settings and chapter progress. Per-chapter mutation scope in the offline queue not verified | No (shared offline queue extraction touches it) |
| AUD-002 | Tracking rollup refresh is delete and insert without a lock | Open (no lock in `tracking/rollups.py`) | No |
| AUD-003 | Flag lookup failures are not cached, so a PostHog outage means a call per request | Open (`core/feature_flags.py` returns before caching on error) | Yes, both features add flags on the request path |
| AUD-004 | No central erasure hook | Fixed: `core/registry.py` and modules register erasers and exporters | Use it |
| AUD-005 | Layering: ORM in views, foreign model queries | Open (7 foreign model imports in coverage and tracking; ORM in coverage views) | New modules must not repeat it (use selectors) |
| AUD-006 | Cross-timer exclusion is check-then-insert | Open | No |
| AUD-007 | Reports UI incomplete | Open (group fixed by `defaultGroup`) | No |
| AUD-009 | Error, flag and view base classes triplicated | Open | Yes (notes would be the fourth copy, recall the fifth) |
| AUD-020 | No Sentry `before_send` scrubbing, PostHog identify sends email | Open | Yes, notes and cards hold personal text; it is an F-03 R1 launch prerequisite |

Shared platform from product README Wave 0: `core/events` is a synchronous in-memory stand-in (fine for R1 of both features), `core/jobs` does not exist (needed from Notes R2 and Recall R2), `media` does not exist (needed from Notes R2), `core/richtext` does not exist, `CACHES` not configured (AUD-008).

## 4. Next features: Smart Notes (F-03) then Flashcards and Spaced Revision (F-15)

Decisions (owner, 2026-10-07): build Notes R1 then Recall R1; groundwork is "Wave 0-lite"; first release is R1 only, behind flags.

The features page entries are `smart-notes` and `flashcards` in `apps/web/src/modules/catalog/features.ts`. Documents:

| Feature | PRD | ERD | Flags | R1 estimate |
| --- | --- | --- | --- | --- |
| Smart Notes (F-03) | `docs/product/prd/F-03-notes-and-pdf-editor.md` | `docs/product/erd/F-03-notes-and-pdf-editor.md` | `notes` (R1), later `notes_pdf`, `notes_ai`, `notes_share` | 4 to 5 weeks |
| Flashcards and Spaced Revision (F-15) | `docs/product/prd/F-15-recall-system.md` | `docs/product/erd/F-15-recall-system.md` | `recall_system` (R1), later `recall_ai`, `recall_sharing` | 8 to 10 weeks |

**Independence.** Their R1 releases do not need each other. The only link is the "highlight to card" bridge (F-03 R2 slice 19, F-15 slice 12), which is out of R1 for both. Both need the same groundwork, which is why it comes first. Notes R1 needs no `core/jobs` and no `media` (those start in Notes R2). Recall R1 needs `core.events` (the stand-in is enough); `core/jobs` first matters for deck sync and AI in R2 (confirm in the kickoff). F-13 Today does not exist, so Recall exposes `provide_today` but does not register a provider yet.

### 4.1 Wave 0-lite (before the first feature slice, about 7 working days)

| Id | Change | Source |
| --- | --- | --- |
| W0L.1 | Consolidate error, flag-permission and view base classes into `core` (modules switch over, no behaviour change) | AUD-009, F-03 slice 0 |
| W0L.2 | Cache flag lookup failures for a short time, set `CACHES` and note `NUM_PROXIES` | AUD-003, AUD-008 |
| W0L.3 | Sentry `before_send` scrubbing, PostHog autocapture masking and identify without email | AUD-020 |
| W0L.4 | `syllabus.selectors` extension: `chapter_refs`, `topic_refs`, `resolve_keys`, `chapters_for_scheme`; coverage hook for note and card signals | F-03 slice 0, F-15 section 14 |
| W0L.5 | `core/richtext` (Markdown plus KaTeX lint and text extraction) with profiles `note` and `card` (add `question` when F-06 starts), and the web `RichText` component with a profile prop | F-03 slice 1 (F-06 has not started, so we create it here) |
| W0L.6 | Extract the persisted offline queue from `coverage/lib/offlineQueue.ts` to `src/lib/offline-queue` with `scope` and a parked-conflict store; coverage and tracker keep working | F-03 slice 7 |

### 4.2 Notes R1 (flag `notes`): PRD slices 2 to 6 and 8

Typed notes in Markdown with KaTeX, autosave, version history, trash, tags, links to subject, chapter and topic, aggregate views, search, `create_clip` service, chapter-page slot, coverage `note_added` count, offline-first queue. No PDF. Launch prerequisite: W0L.3.

### 4.3 Recall R1 (flag `recall_system`): PRD slices 1 to 13 (slice 12 is the service only)

FSRS-6 pure scheduler in Python and TypeScript with shared golden vectors, seven card kinds, append-only review log, review screen, daily limits and catch-up, platform decks edited in Django admin, forgotten list, stats, export and delete, offline review. Open owner items from the PRD: Q-F15-3 (study day boundary, default 04:00), Q-F15-4 (who writes the first platform decks: two pilot subjects, about 12 chapters, 40 cards each).

**Status 2026-10-11: F-15 R1 is built and verified by tests (W0 to W12 done).** Verified by automated tests only: API suite on SQLite and PostgreSQL, recall web unit tests, `pnpm check`, and two end-to-end scripts on PostgreSQL (`scripts/e2e/recall-r1/run.py`, 43 checks; `capacity.py`). Built: the FSRS-6 scheduler in Python and TypeScript with shared golden vectors, schema with a partitioned immutable review log, card services and endpoints, reviews (submit, batch, undo, replay, sessions, rebalance, vacation), the read side (`today/`, `queue/`, `pack/`, `forgotten/`, `stats/*`, `settings/`), design-system components, web offline sync and screens (hub, review player, summary, stats, forgotten, settings, cards browser, creator, card page, decks, export and erase), platform decks edited in Django admin (`load_recall_seed`, `grant_staff_role`), and the flag-aware Notes provider. W12 added the e2e and capacity scripts, the privacy gates (Sentry scrubbing for recall routes on the API and web, log id masking, PostHog allow-list tests), `docs/F-15-API-CONTRACT.md` with a URL-conf test, the SETUP section 9.1 and the fix of a rebalance boundary bug (a card postponed to exactly the start of tomorrow was still counted as due today). Capacity (2-CPU shared sandbox): single requests meet the targets except the 100-event review batch (about 1.2 to 1.5 s against 800 ms); with 8 unthrottled concurrent reviewers queue, today and review p95 exceed their targets; details in `docs/F-15-ROLLOUT.md`, "Capacity note". Not verified by anyone: manual device and browser checks (accepted risk, your standing rule), your own Postgres. Nothing is user-visible and the flag `recall_system` stays off ("team only" cohort) until the tasks below are done.

### 4.4 Owner tasks for this track

| Task | When |
| --- | --- |
| PostHog flags `notes` and `recall_system` at 0% | Before the first Notes or Recall merge |
| Closed beta list (the same 50 students as F-01 and F-02; Recall: PostHog cohort, see `docs/F-15-ROLLOUT.md` W11 operations) | Before Notes R1 beta |
| Editors for the first platform decks and the Django admin accounts (how: `docs/F-15-ROLLOUT.md`, W11 operations, `grant_staff_role`) | Before Recall R1 beta |
| Run `pytest` and `scripts/e2e/recall-r1/run.py` and `capacity.py` on your own Postgres (a development database; `docs/SETUP.md` section 9.1) and keep the capacity output | Before the flag goes to the beta cohort |
| Schedule `POST /api/v1/recall/internal/tick/` every 5 minutes with `RECALL_TICK_SECRET` (set the secret first) | Before the Recall beta |
| Load the CMA Final Paper 13 decks (`load_recall_seed apps/api/modules/recall/seed/cma-final-paper13 --dry-run`, then for real), review each deck in the Django admin, tie it to its CMA Final chapter, set `rights_status`, publish | Before the Recall beta |
| Put the closed-beta cohort into the `recall_system` flag; check with one beta and one non-beta account | Recall beta start |
| Decide whether to speed up the 100-event review batch (about 1.2 to 1.5 s here, target 800 ms; capacity note) | Before widening the beta |
| Counsel review of the copyright posture (Q-F03-3, Q-F15-8) | Deferred by the owner on 2026-10-08, see section 5; needed before R2 sharing |

## 5. Parked: share links and legal (owner decision, 2026-10-08)

Notes R2 (`notes_pdf`) is launched and the flag is raised. Two things are parked on purpose, not forgotten.

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| P1 | F-03 R3 share links (flag `notes_share`, FR-F03-66 and 67) | Parked, not built | Anyone with the link can open a read-only page, no sign-in, to a typed note or a highlight digest (quotes up to 300 characters, page numbers, optional comments). Never the PDF. Expires in 30 days by default (7, 30 or never), revocable at once, `noindex`, "Save a copy" after sign-in, "Report" link and an admin report queue. Documents marked coaching or Institute material cannot be shared. Limit 20 active links. The quota fields and 403 `feature_disabled` stubs already exist. Spec: PRD sections L and "Share (R3) and public page" in `docs/product/prd/F-03-notes-and-pdf-editor.md`. Do the legal review (P2) before building this: sharing is where copyright risk grows |
| P2 | Counsel sign-off Q-F03-3: storing student PDFs and the Devanagari export fonts (Noto, OFL) | Deferred, open | Not needed to run R2 privately for students. Do it before a broad public launch, before share links, or once there is real traffic. Brief for counsel: (1) students upload files they may not own, and the platform scans, extracts, indexes, OCRs and exports them privately for that student; (2) embedding Noto fonts in exported PDFs under the SIL Open Font License, with the notice shown where required |
| P3 | Terms of service line: students may upload only material they have the right to use and are responsible for it | Open, small | Do before a broad public launch |
| P4 | A rights-holder contact or takedown email, and a way for us to remove a file on request | Open, small | Do before a broad public launch |
| P5 | R2 manual checks that need real hardware: device matrix (touch, Apple Pencil), 50 MB and 1,000-page upload and 1,000-page OCR on the live worker, 50-user write load, search p95 on staging, accessibility | Not run, accepted | Owner will not run them. Automated tests, the e2e script and the capacity baseline stand in. Fix on the first real report |


## 6. F-03 R3 (flag `notes_ai`): built 2026-10-08, owner tasks

Built: AI exam summary, AI "Improve this page", Replace edition with re-anchoring, Unlock for search, resumable upload (API, web, tests, `scripts/e2e/notes-r3`). All behind `notes_ai`, which fails closed. Details: `docs/F-03-ROLLOUT.md` (R3), `docs/F-03-API-CONTRACT.md` (R3).

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| R3-1 | Create PostHog flag `notes_ai` at 0% | Open (owner) | |
| R3-2 | Gemini billing tier: link a Google Cloud billing account to the API key's project, then set `GEMINI_DATA_TIER=paid` | Open (owner) | A Gemini / Google AI Pro subscription does not count as a paid API tier. AI refuses while the value is `unconfirmed` |
| R3-3 | Approve the consent wording (draft, [VERIFY]) and set `NOTES_AI_CONSENT_APPROVED` to its version | Open (owner) | `apps/api/modules/notes/domain/ai_consent.py`; the text says what is sent to Google (note and highlight text of the chapter, page pictures) |
| R3-4 | Set `NOTES_AI_DAILY_BUDGET_PAISE`, plan columns `ai_summaries_per_month` and `ai_ocr_pages_per_month` in the admin; re-check the two `GEMINI_PRICE_*` values | Open (owner) | |
| R3-5 | `NOTES_UNLOCK_FERNET_KEYS` in the API and the worker (same value) | Open (owner) | Unlock answers 503 until set |
| R3-6 | Deploy the worker with the new job types and secrets | Open (owner) | `docs/F-03-WORKER.md` |
| R3-7 | Resumable upload: S3 access key, `NOTES_S3_*`, bucket CORS, one throttled test upload | Open (owner), [VERIFY] | Optional: without it every upload is a single PUT. Signing is unit-tested against AWS's published vector; the live Supabase S3 endpoint is not verified |
| R3-8 | Offline PDF packs (item 6) | Blocked, not built | Needs the offline-store design and a service-worker decision. Stubs unchanged |
| R3-9 | Recall bridge (item 7) | Blocked, not built | Waits for F-15 to register a provider (`core/recall_port.py`) |
| R3-10 | Share links | Parked (see P1) | Counsel review first (P2) |
| R3-11 | Postgres run of `modules/notes core` (concurrency, RLS, quota races) | Not run here | The sandbox ran SQLite; Postgres-only tests skip. Run `pytest modules/notes core` against a Postgres once before the flag goes up |


## 7. F-15 R2, wave W2 (living decks): built 2026-10-11, owner tasks

Built: sync service with follow or pin, update preview and apply endpoints with the web UI, amendment subscriber port (F-14 events by name), scheme switch through the F-02 chapter map, admin diff and staff notice, export and erase of all new data, offline pack and client fold. No new flag: `recall_system` stays fail-closed, beta cohort only. Details: `docs/F-15-ROLLOUT.md` (section 8), `docs/F-15-API-CONTRACT.md`.

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| W2-1 | Run `pytest modules/recall core` once on a real PostgreSQL before the cohort opens | Open (owner) | Verified here on a private PostgreSQL 16 and on SQLite |
| W2-2 | Apply migration `0005` on staging, then check that the 5-minute tick drains the fan-out | Open (owner) | Fan-out reaches the 15-minute target only at the boundary in the worst case; see the capacity table |
| W2-3 | Editors: every publish of a new deck version now needs a changelog note | Open (owner) | Answers 422 `changelog_required` |
| W2-4 | Confirm F-14 emits the amendment events under the names the subscriber listens to | Open (owner), [VERIFY] | The coverage scheme event also has an alias subscription |
| W2-5 | Manual device checks | Not run, accepted | Automated tests, e2e r1 and r2 and the W2 capacity script stand in |

## 8. F-15 R2, wave W3 (Recall with Coverage, Tracker and Today, strength on chapter pages, paste import): built 2026-10-11, owner tasks

Built: the chapter recall pass (rolling 7 days, one coverage revision per chapter per week), recall strength on chapter pages, the revision boost and "Review cards" deep links, the Today task port (`core/today_port.py`, no Today screen), the opt-in tracker session, and paste or CSV import with a preview. No new flag: `recall_system` stays fail-closed, beta cohort only. Details: `docs/F-15-ROLLOUT.md` (section 9), `docs/F-15-API-CONTRACT.md`.

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| W3-1 | Apply migration `0006` (one defaulted JSON column on `recall_session`) on staging before the web build that shows the chapter card | Open (owner) | Additive; older code ignores it |
| W3-2 | Run `pytest modules/coverage modules/recall modules/tracking modules/focus core` once on a real PostgreSQL, then `scripts/e2e/recall-r2/run.py` and `capacity.py` | Open (owner) | Verified here on a private PostgreSQL 16 and on SQLite; keep the capacity output |
| W3-3 | Decide whether "Recall counts as revision" stays on by default | Open (owner), decision | On means a passed chapter set moves the chapter's revision schedule in coverage without the student pressing anything. The setting already existed (R1) and defaults to on |
| W3-4 | Tracker auto capture stays off by default; confirm the `time_tracker` flag is open for the cohort | Open (owner) | Recall time only reaches the tracker for students who switched auto capture on |
| W3-5 | F-13 Today: when it is built, call `core.today_port.collect(user_id, now=)` once per load | Open (F-13) | The recall provider is registered and flag aware; the task shape is in section 9.2 |
| W3-6 | Editors and support: the import takes 200 rows a call and refuses duplicates; tell students to split long lists | Open (owner), copy | Row errors name the problem in words |
| W3-7 | Manual device checks (chapter card, revision link, import on a phone) | Not run, accepted | Automated component, keyboard and axe tests, the e2e script and the capacity comparison stand in |

## 9. F-15 R2, wave W4 (history of updates, "my own words", cards from mistakes): built 2026-10-11, owner tasks

Built: the student's history of deck updates, "what changed" in a card, the "my own words" statement for cards made from a selection, and a card from a mistake through a question port that F-06 will fill. No new flag: `recall_system` stays fail-closed, beta cohort only. Sharing and AI suggestions are not in it. Details: `docs/F-15-ROLLOUT.md` section 10.

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| W4-1 | Apply migration `0007` (new table `recall_subscriptionupdate`) on staging before the web build that shows the history | Open (owner) | Additive; older code ignores it |
| W4-2 | Run `pytest modules/coverage modules/recall modules/tracking modules/focus core` once on a real PostgreSQL, then `scripts/e2e/recall-r2/run.py`, `capacity.py` and `capacity_w2.py` | Open (owner) | Verified here on a private PostgreSQL 16 and on SQLite; keep the capacity output |
| W4-3 | F-06: register `core.question_port.register_question_provider` and mount `QuestionCardButton` on the wrong-answer screen | Open (F-06) | Until then `POST recall/cards/from-question/` answers 503 `question_source_unavailable` and the button is not shown anywhere |
| W4-4 | Sharing wave: read `item.shareable` (attested cards are shareable); legal posture Q-F15-8 and counsel's review come before it is opened | Open (later wave) | The statement and its audit trail exist; nothing reads them yet |
| W4-5 | Update history starts at W4: updates applied before it are not listed | Accepted | Nothing recorded them; a deck that changes again fills the list |
| W4-6 | Manual device checks (card page panels, deck page accordion on a phone) | Not run, accepted | Automated component, keyboard and axe tests and the e2e script stand in |

## 10. F-15 R2, wave W5 (AI-suggested cards) and the W4 leftovers: built 2026-10-12, owner tasks

Built: AI-suggested cards behind the fail-closed flag `recall_ai`, the word diff in "what changed", and the "N cards changed" Today task. R2 is complete except sharing (`recall_sharing`). Details: `docs/F-15-ROLLOUT.md` section 11.

| # | Task | Status | Note |
| --- | --- | --- | --- |
| W5-1 | Apply migration `0008` on staging before the web build | Open (owner) | Additive |
| W5-2 | Review and approve the notice wording in `modules/recall/domain/ai_consent.py` (counsel if needed), then set `RECALL_AI_CONSENT_APPROVED=true` | Open (owner) | Until then the feature answers unavailable |
| W5-3 | Set `GEMINI_API_KEY`, `GEMINI_DATA_TIER=paid`, `RECALL_AI_ENABLED`, `RECALL_AI_DAILY_BUDGET_PAISE` on the API and the worker; confirm the worker handles `recall.suggest` | Open (owner) | See `docs/SETUP.md` |
| W5-4 | Open `recall_ai` for the beta cohort only | Open (owner) | Fail closed |
| W5-5 | F-06: register `core.suggestion_source_port` for `wrong_answers` | Open (F-06) | Until then that source answers 422 `source_unavailable` |
| W5-6 | Run the recall, core and notes pytest once on a real PostgreSQL | Open (owner) | Verified on SQLite here |
| W5-7 | Manual device checks of the suggestion screen on a phone | Not run, accepted | Automated component, keyboard and axe tests stand in |

## 11. F-13 Today (flag `today_plan`, fail closed): waves planned 2026-10-14, W1 and W2 built

Plan: `docs/F-13-BUILD-WAVES.md` (W1 to W6 for R1, W7 to W9 for R2). W1 (API engine: schema, registry, pure composition, state machine, deep-link allow-list) is built and tested. W2 (generation, `open`, `plan`, `preview`, `history`, `settings`, coverage and Recall providers, admin, contract doc) is built and tested; the endpoints exist behind the fail-closed flag `today_plan`, nothing is user-visible.

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| F13-1 | Run `pnpm lint:api && pnpm test:api` once on the real repo and on PostgreSQL (migration `today.0001`, RLS test) | Open (owner) | W1 was verified on SQLite in isolation |
| F13-2 | Approve the three PRD changes in `docs/F-13-BUILD-WAVES.md` section 5 (rotation guarantee needs a 3 day hard priority, unknown hours give 60 minutes, never-touched counts as starved) | Done | Approved by the owner 2026-10-15 |
| F13-3 | Create the PostHog flag `today_plan` at 0 percent | Done | Needed now: the API fails closed until it exists and is on |
| F13-4 | `core/today_port.py` (Recall W3 stand-in) is bridged by the provider `recall.legacy`; delete both once Recall registers on `today.registry` | Built (W2) | |
| F13-5 | Practice provider waits for F-06 | Parked | R1 ships with coverage, Recall and own tasks |
| F13-7 | Wave 3 (task actions, own tasks, regenerate, completion events, reconcile) built; confirm the seven decisions at the end of `docs/F-13-BUILD-WAVES.md` section 6 | Done (W3 built; the seven decisions approved 2026-10-15) | W4 mirrors the transition table in the web |
| F13-8 | Wave 4 (Today screen, web and design system) built: `/app/today`, `/app` redirect, `ProgressRing` segments, `Celebrate`, nav link | Built (W4) | Owner: run `pnpm check` on the real repo and look at the four themes at 320 and 1280 px |
| F13-9 | Wave 5 (actions and motivation) built, plus API `plan/celebrated/`, `closing`, `budget_source` | Built (W5) | Owner: run `pnpm check` and `pnpm lint:api && pnpm test:api` on the real repo; look at the four themes at 320 and 1280 px; no new migration |
| F13-10 | Wave 6 (offline cache and queue, lite mode, analytics contract, settings, exam card, onboarding handoff, stuck prompt, `/features/today`, cron tick, eraser and exporter, `docs/F-13-ROLLOUT.md`) built | Built (W6) | Owner: run `pnpm check` and `pnpm lint:api && pnpm test:api`; set `TODAY_TICK_SECRET` and schedule the tick every 5 minutes; run `python manage.py rebuild_coverage` once after deploy; flag `today_plan` stays off until the beta cohort opens |
| F13-11 | Wave 7 (planner engine, R2 slice 16): migration `today.0002_planner` (`today_studyplan`, `today_milestone`, `today_replanevent`), pure `modules/today/planner/` (capacity, milestones, health, options, re-plan) with hand-derived golden fixtures, properties, a multi-week simulation and a missed-week scenario | Built (W7) | Nothing is user-visible: no endpoint, service or flag wiring until W8. Owner: run `pnpm lint:api && pnpm test:api` on the real repo (migration `today.0002` on PostgreSQL); create the PostHog flag `today_planner` at 0 percent before W8; sanity-check the planner numbers and `[VERIFY]` constants listed in `docs/F-13-BUILD-WAVES.md` ("Changes to the PRD found in W7") |
| F13-12 | Wave 8 (planner API, R2 slice 17): `planner_services`, `planner_selectors`, `planner_serializers`, `planner_views`, five endpoints under `today/planner/`, planner provider `today.planner`, replan events, cron `planner` sweep, eraser and exporter, three analytics events, contract doc | Built (W8) | Owner: run `pnpm lint:api && pnpm test:api`; copy the event schema to the web twin if it is not already identical; the flag `today_planner` stays at 0 percent until the beta cohort opens; the web screen is W9. No new migration (W7's `today.0002` is enough). Review the 8 numbered decisions in the waves doc, "Changes to the PRD found in W8" |
| F13-13 | Wave 9 (planner web and adaptive, R2 slice 18): migration `today.0003_feedback`, feedback, budget suggestion and bonus round endpoints, `/app/planner` (health card, milestones, re-plan options), "Study plan" nav link, feedback, suggestion and bonus cards on Today, two analytics events | Built (W9) | Owner: run `pnpm lint:api && pnpm test:api` and `pnpm check` (the web half was written without running the web tooling; check the route tree and the new component tests); apply migration `today.0003`; the flag `today_planner` stays at 0 percent until the beta cohort opens. Review the 8 numbered decisions in the waves doc, "Changes to the PRD found in W9" |
| F13-6 | F-02 extensions: `coverage.selectors.study_state` (W2), event `coverage_event_recorded` (W3), AUD-018 UTC date fix (done 2026-10-15) | Built | After deploying, run `python manage.py rebuild_coverage` once so revision dates stored before the fix are recalculated on each student's calendar |

## 12. F-06 Question Bank System, F-09 PYQ, F-05 MCQ Bank: planned 2026-10-15, W1, W2, W3, W4 built

Plan: `docs/QB-BUILD-WAVES.md` (W1 to W5 for R1). W1 (Content Engine API), W2 (Practice Engine API), W3 (Web Browse and Practice), and W4 (Editors, Admin and Previous Year Questions F-09 R1) are built and tested.

| # | Item | Status | Notes |
| --- | --- | --- | --- |
| QB-1 | Run `pnpm lint:api && pnpm test:api` on real PostgreSQL (apply migrations `questionbank.0001`, `practice.0001`, `pyq.0001`, `pyq.0002`, RLS tests) | Open (owner) | Verified on SQLite and via contract drift test |
| QB-2 | Create PostHog flags `question_bank` and `pyq_bank` at 0% (strict mode fails closed) | Open (owner) | Needed before enabling any cohort |
| QB-3 | Initial seed target: CMA Intermediate and Final (Syllabus 2022, last 3 sittings: June 2024, Dec 2024, June 2025) | Agreed | Selected by owner 2026-10-15 |
| QB-4 | Wave 2 (Practice Engine API: practice schema, partitioned attempts, scoring & grading, ports, subscribers, chapter progress, zero answer leakage) | Built (W2) | All 39 tests passing; contract drift test green; `core.question_port`, `core.suggestion_source_port`, `core.today_port` registered; fail-closed |
| QB-5 | Wave 3 (Web browse and practice: DS primitives, questionbank web, practice player, offline queue) | Built (W3) | DS primitives (`Combobox`, `TagInput`, `NumberGrid`, `Countdown`, `SegmentedBar`), showcase, `pnpm check:contrast` 100%, web modules `questionbank` and `practice`, 9 TanStack Start routes, fail-closed flag guard, 0 answer leak, `pnpm check` and `build:web` green |
| QB-6 | Wave 4 (Editors, admin and Past Papers F-09 R1 & F-06 slice 16) | Built (W4) | `pyq` models (`PyqPaper`, `ChoiceGroup`, `PaperQuestion`, `PaperLink`, `AskedCache`, `DailySet`), marks & choice & links pure domain, `artha.paper.v1` import & publish & withdraw services, paper/chapter practice sessions, zero `user_id` privacy invariant (12/12 pytest passing), staff CSV import, review queue and reports views, web `pyq` module (card, question tree, paper detail, chapter PYQ SEO), staff editor UI (`CsvImportDialog`, `EditorReviewQueueContainer`), 4 TanStack Start routes (`/app/pyq/`, `/app/pyq/papers/$id`, `/courses/.../previous-year-questions`, `/app/questions/editor`), `pnpm check` green |
| QB-7 | Wave 5 (MCQ Bank F-05 R1 and launch) | Planned | Next wave: `mcqbank` presets, daily quick sets, chapter drill selectors, landing beat, catalog status live |
