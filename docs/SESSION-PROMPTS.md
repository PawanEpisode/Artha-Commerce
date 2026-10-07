# Session start prompts

Paste one prompt into a new Claude session with the ArthaCommerce folder connected. Each is self-contained. Tracker: `docs/BUILD-TRACKER.md`.

| # | Prompt | When |
| --- | --- | --- |
| 1 | Wave 0-lite and Smart Notes R1 (F-03) | Now |
| 2 | Flashcards and Spaced Revision R1 (F-15) | After Notes R1 is built (its groundwork is shared) |
| 3 | Desktop companion (X-01 Phase 5) | Later; parked and tracked |

## Prompt 1: Wave 0-lite and Smart Notes R1

````text
You are starting the Smart Notes feature (F-03, release R1) in ArthaCommerce, preceded by a small groundwork set called Wave 0-lite. Your first job is a status check and a build runbook, not code.

READ FIRST (sources of truth)
- CLAUDE.md (non-negotiable rules: modular, design system only, URL-driven, four themes, WCAG 2.2 AA, 320 to 1280 px, tests)
- docs/BUILD-TRACKER.md (sections 3 and 4: what is verified, Wave 0-lite items W0L.1 to W0L.6, Notes R1 scope)
- docs/product/prd/F-03-notes-and-pdf-editor.md: sections 1 to 6 (for R1 read requirement groups D, E, F and K), 7 (screens), 8 (data, quotas, privacy), 9.3 (notes endpoints), 10, 12 (open questions), 13 (slices 0 to 8), 14
- docs/product/erd/F-03-notes-and-pdf-editor.md (tables for typed notes, services, events, offline and conflict rules)
- docs/product/validation/F-02-F-01-implementation-audit-2026-10-05.md (AUD-003, AUD-009, AUD-020 and the layering findings)
- docs/F-02-ROLLOUT.md and docs/X-01-ROLLOUT.md section 0 (runbook style and conventions)
- .claude/skills/new-feature-module, frontend-architecture, django-backend-layers, design-system-usage, ui-quality-checklist, dev-workflow, prd-and-erd
- The features page entry `smart-notes` in apps/web/src/modules/catalog/features.ts (promise: "Notes linked to chapters, Instant search, Formula and section shortcuts")

WHERE THINGS STAND (verified 2026-10-07)
- F-01.1, F-01.2, F-02, F-16 and X-01 (P1 to P4) are built. F-03 and F-15 have PRD and ERD only. No notes or recall code exists.
- Missing shared pieces: core/richtext, a shared offline queue (the only one is apps/web/src/modules/coverage/lib/offlineQueue.ts), the syllabus selector extensions (chapter_refs, topic_refs, resolve_keys, chapters_for_scheme), Sentry and PostHog scrubbing (AUD-020), a short cache for flag-lookup failures (AUD-003), and consolidated core base classes (AUD-009). core/events is a synchronous in-memory stand-in (enough for R1). core/jobs and media do not exist and are NOT needed for R1.
- Owner decisions already taken: build Notes R1 first, then Recall R1; groundwork is Wave 0-lite only; first release is R1 only, behind flag `notes`, no PDF, no AI, no sharing. Flag `notes` is created at 0% in PostHog by the owner before the first wave merges.

ORDER OF WORK
1. Status check: confirm the tracker is still true (read the code for the six W0L items and for any notes or recall module). Report differences in a few lines.
2. Ask me (AskUserQuestion, recommended option first, max 4 per call) the R1 open questions that change the build: Q-F03-2 (free quota numbers), Q-F03-4 (do notes change coverage percent: default no), Q-F03-6 (editor: Markdown source with toolbar), Q-F03-8 (personal tags), plus anything the PRD marks for founder that R1 touches. Do not assume.
3. Write the build runbook docs/F-03-ROLLOUT.md in the style of docs/F-02-ROLLOUT.md and docs/X-01-ROLLOUT.md: scope, waves (one change set each; Wave 0-lite items W0L.1 to W0L.6 first, then PRD slices 2 to 6 and 8 grouped into reviewable waves), file-level changes, migrations (additive, deploy order), flags, env vars (none expected), tests, real-device checks, rollback, risks, and what I must arrange. Wait for my approval before writing any code.
4. After approval, implement wave by wave, with tests, as the runbook says.

HARD CONSTRAINTS FROM THE DOCS
- Rule 1 and 2: notes module has a barrel; other modules import only through it. API layers: views -> services -> selectors -> models; foreign data only through selectors and services (no foreign model imports; see AUD-005). Business logic never in views or JSX.
- Every table: user_id by value, RLS enabled by the post_migrate hook, extend core/tests/test_row_level_security.py. Register an eraser and exporter through core/registry.py (AUD-004 is fixed; use it).
- Notes contain personal study text: no note text or ids in logs, Sentry or PostHog events (W0L.3 first).
- Write idempotent endpoints (client ids), row locks on every note write (select_for_update), and test them against real Postgres (CI uses postgres:16; wrap auth.uid() SQL in the pg_namespace check).
- Design system only: semantic tokens, no raw hex, icons only from @artha/design-system; new shared UI (SyncChip, UsageBar) goes in the design system with a showcase entry and contrast check.
- Four themes, WCAG 2.2 AA, 320 to 1280 px, keyboard operable, URL-driven screens, noindex on private pages.

STANDING RULES
- Work directly on main, no branch. NEVER run git commit, never stage, never touch the index. I commit and push.
- Before any file change or git command, run the lock cleanup through the linked-computer shell (device_bash): `cd "$(git rev-parse --show-toplevel)"; if ! pgrep -x git >/dev/null; then find .git -maxdepth 3 -name "*.lock" -print -delete; fi`. Use `git --no-optional-locks`. Mention it only if a lock was removed.
- Do the work on my computer with device_bash (edit in place with sed or a small script, never retype files from tool output). The folder is ArthaCommerce; the cloud container is only for things the local shell cannot do.
- Test runs happen in a scratch copy of the repo: rsync to a FRESH directory under /tmp (exclude node_modules, .git, .venv, build output; old /tmp copies may be owned by another user, so use new names such as /tmp/artha-notes and /tmp/pnpm-store-notes). pnpm 10.28.0 via `npm i --prefix /tmp/pnpm-bin pnpm@10.28.0`, export PATH, `pnpm install --store-dir <new store>` in the foreground, TMPDIR=/tmp. Each device_bash call is limited to 180 s, so run typecheck, lint, tests and build as separate calls. After autofix (eslint --fix, prettier --write) in scratch, copy only the changed files back to the repo.
- Per wave run: `pnpm --filter @artha/web exec vitest run <module paths> && pnpm check`, plus `cd apps/api && pytest && ruff check . && ruff format --check .` when apps/api changes (Postgres via DATABASE_URL). Fix everything before declaring done. If a generated file changes (routeTree.gen.ts), check the diff is only what you expect.
- No emojis. Conventional Commits: I write the commit; give me a suggested message for each wave ending with the trailers Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com> and Claude-Session: <current session url>.

FINAL REPORT PER WAVE (short): files changed and test results; the real-device checks for me; the suggested commit message; which flags stay where (`notes` stays "team only" until the R1 beta checks pass).

Start with step 1 now.
````

## Prompt 2: Flashcards and Spaced Revision R1 (F-15)

````text
You are starting Flashcards and Spaced Revision (F-15 "Recall system", release R1) in ArthaCommerce. Your first job is a status check and a build runbook, not code.

READ FIRST
- CLAUDE.md, docs/BUILD-TRACKER.md (sections 3 and 4), docs/F-03-ROLLOUT.md (what Notes R1 already built and shared)
- docs/product/prd/F-15-recall-system.md: sections 1 to 6, 7 (screens), 8 (quotas, privacy), 9 (API), 10, 12 (open questions Q-F15-1 to 14), 13 (slices 1 to 13), 14 (interfaces)
- docs/product/erd/F-15-recall-system.md (tables, hash-partitioned recall_reviewlog and its immutability trigger, scheduler contract, offline sync)
- The features page entry `flashcards` in apps/web/src/modules/catalog/features.ts ("Spaced repetition scheduling, Cards from your notes, Daily revision queue")
- docs/product/prd/F-02-syllabus-structure-and-coverage.md (coverage selectors and revision signals it uses), docs/F-02-ROLLOUT.md
- The skills in .claude/skills (new-feature-module, frontend-architecture, django-backend-layers, design-system-usage, ui-quality-checklist, dev-workflow)

WHERE THINGS STAND
- Notes R1 (F-03) and Wave 0-lite should be built (core/richtext with a `card` profile, shared offline queue in src/lib/offline-queue, syllabus selector extensions, scrubbing, core base classes). Verify that first; if anything is missing, say so and stop.
- core/events is a synchronous stand-in; core/jobs and media do not exist. R1 of F-15 should not need them (deck sync and AI are R2): confirm from the ERD and report.
- F-13 Today does not exist: build `provide_today` as a selector but do not register a provider. F-03's "highlight to card" bridge is out of scope (F-03 R2); ship the `create_card` service with `create_card_from_selection` as a thin wrapper.
- Owner decisions already taken: R1 only, behind flag `recall_system`; FSRS-6 default (Q-F15-1). PostHog flag `recall_system` at 0% before the first merge.

ORDER OF WORK
1. Status check (above).
2. Ask me (AskUserQuestion, recommended first, max 4 per call): Q-F15-3 (study day boundary, default 04:00), Q-F15-4 (who writes the first platform decks; default two pilot subjects, about 12 chapters, 40 cards each), Q-F15-5 (free limits), Q-F15-9 (streak rule), Q-F15-10 (new cards per day, default 10), Q-F15-11 (early review), and the pure-scheduler test plan (oracle test against py-fsrs and ts-fsrs in dev only).
3. Write docs/F-15-ROLLOUT.md in the same style as docs/F-03-ROLLOUT.md: waves (one change set each) covering PRD slices 1 to 13, schema and migrations (partitioned reviewlog needs a Postgres test), golden vectors shared by Python and TypeScript, offline review queue, platform decks in Django admin, tests, real-device checks, rollback, risks, what I must arrange. Wait for my approval before code.
4. After approval implement wave by wave.

HARD CONSTRAINTS: the scheduler is a pure, versioned function in Python and TypeScript with identical golden vectors; the review log is append-only and idempotent by client event id; Django is the only gateway; foreign data only through selectors and services (`recall/adapters`, see PRD R-7); account export and erase through core/registry.py; no card text in logs, Sentry or PostHog; design-system components RatingButtons, FlipCard, ProgressCounter, DatePicker added to the design system with showcase and contrast checks; four themes, WCAG 2.2 AA, 320 to 1280 px, keyboard shortcuts and swipe in the review player.

STANDING RULES and FINAL REPORT PER WAVE: identical to prompt 1 (work on main, never commit, lock cleanup through device_bash, scratch copy under new /tmp names such as /tmp/artha-recall, pnpm 10.28.0, per-wave checks, no emojis, suggested Conventional Commit with the Co-Authored-By and Claude-Session trailers, `recall_system` stays "team only" until the R1 checks pass).

Start with step 1 now.
````

## Prompt 3: Desktop companion (X-01 Phase 5), for later

````text
You are continuing X-01 Phase 5, the desktop companion, in ArthaCommerce. Gate G4 is met. The build document is written and waits for approval; no code exists.

READ FIRST
- CLAUDE.md and docs/BUILD-TRACKER.md (section 2 is the companion's status; sections 1 and 3 say what else may have changed)
- docs/X-01-P5-DESKTOP-COMPANION.md (the build document: decisions P5-D1 to D15, architecture, auth flow, device registration, tray and mini-window behaviour, alert dedupe, keep-awake, waves W5.0 to W5.9, CI, signing, release, flag, owner tasks, tests, matrix, risks, approval checklist in section 17)
- docs/X-01-ROLLOUT.md (sections 0, 6 to 9) and docs/X-01-spike-results.md
- docs/product/prd/X-01-notifications-floating-timer-stay-awake.md (PRD B "The desktop companion", PRD C FR-K8) and docs/product/prd/X-01.1-push-notifications.md
- .claude/skills/new-feature-module, frontend-architecture, django-backend-layers, design-system-usage, ui-quality-checklist, dev-workflow

STEP 0: Ask me (AskUserQuestion) whether the document in section 17 is approved, whether section 0 now has the exact G4 figures, whether X1 to X3 in the tracker are closed (QStash fix, W2.7 matrix, P4 matrix), and which of the owner tasks in section 13 are done (Apple enrolment, Windows signing, bucket, PostHog flag `desktop_companion` at 0%). If the document is not approved, apply my changes to it and stop. Do not write code before approval.

Then implement wave by wave as the document says, starting with W5.0 (spikes) and W5.1 (`packages/timer-ui` extraction, no behaviour change).

STANDING RULES: work directly on main, no branch, never commit or stage (I commit and push); lock cleanup through device_bash before any file change or git command (`cd "$(git rev-parse --show-toplevel)"; if ! pgrep -x git >/dev/null; then find .git -maxdepth 3 -name "*.lock" -print -delete; fi`, `git --no-optional-locks`); do the work on my computer with device_bash; test in a scratch copy under new /tmp names (for example /tmp/artha-p5, /tmp/pnpm-store-p5) with pnpm 10.28.0, separate calls for typecheck, lint, tests and build (180 s limit per call); per wave run the web, API and desktop checks the document lists (`pnpm check`, pytest and ruff when apps/api changes, `pnpm check:desktop` and the desktop build once they exist); no emojis; no raw hex; icons only from @artha/design-system; suggested Conventional Commit per wave with the Co-Authored-By and Claude-Session trailers. Flag `desktop_companion` stays "team only" until the P5 matrix is signed off.

FINAL REPORT PER WAVE (short): files changed and test results; the real-device checks for me; the suggested commit message; which flags stay where.
````
