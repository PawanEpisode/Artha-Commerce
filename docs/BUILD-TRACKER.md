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

**Status 2026-10-09.** Runbook approved (`docs/F-15-ROLLOUT.md`). Done: W0 prerequisites, W1 Python domain (FSRS-6, replay, queue, cards, golden vectors, py-fsrs oracle), W2 TypeScript twin (same vectors, ts-fsrs oracle), W3 schema (four migrations, partitioned immutable review log on PostgreSQL, plans seam `core/plans.py`, quotas, RLS tests), W4 card services, `/api/v1/recall/cards/` endpoints, kind registry and the flag-aware Notes provider (Notes "Make a card" is live only for students with `recall_system` on). Next: W5 reviews. Nothing is user-visible yet and the flag `recall_system` stays off.

### 4.4 Owner tasks for this track

| Task | When |
| --- | --- |
| PostHog flags `notes` and `recall_system` at 0% | Before the first Notes or Recall merge |
| Closed beta list (the same 50 students as F-01 and F-02) | Before Notes R1 beta |
| Editors for the first platform decks and the Django admin accounts | Before Recall R1 beta |
| Counsel review of the copyright posture (Q-F03-3, Q-F15-8) | Deferred by the owner on 2026-10-08, see section 5 |

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
