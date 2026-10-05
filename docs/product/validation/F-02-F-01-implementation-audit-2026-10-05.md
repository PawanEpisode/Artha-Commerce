# Implementation audit: F-02 Syllabus and Coverage, F-01.1 Pomodoro Focus Timer, F-01.2 Time Tracker and Analytics

Date: 2026-10-05. Auditor: Claude (read-only). Scope: `apps/api/modules/{syllabus,coverage,tracking,focus}`, `apps/api/core`, `apps/web/src/modules/{syllabus,coverage,tracker,focus,catalog}`, `apps/web/src/routes`, `packages/design-system`, `supabase`.
Compared against: `docs/product/prd`, `docs/product/erd`, `docs/F-*-ROLLOUT.md`, `docs/product/F-02-syllabus-coverage-report.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `.claude/skills`.

Method: code reading plus grep, and the cheap checks listed in section 9. No file under `apps/`, `packages/` or `supabase/` was modified. No branches or commits were created. Anything not run or not provable from code is marked "Not verified".

Legend: Yes = implemented as specified; Partial = some of the requirement is missing; No = absent; Deviates = implemented differently (documented or not).

## 1. Summary scorecard

| Area | F-02 Syllabus + Coverage | F-01.1 Focus Timer | F-01.2 Time Tracker |
| --- | --- | --- | --- |
| FR/NFR coverage | Good (CA/CS marks content gap) | Good (FR-20 reset missing, flag status code deviates) | Good (reports UI gaps) |
| Data model vs ERD | Good (event type/source check missing) | Good (2 naming/default drifts, doc outdated) | Good (tz doc outdated) |
| API surface and errors | Good | Good | Good (GET with writes, export cap) |
| Layering | Weak (ORM in view, foreign model queries) | Fair (selectors import tracking services) | Weak (foreign model queries, ORM in view) |
| Concurrency and integrity | Weak (no row locks, rollup delete+insert) | Fair (cross-timer race) | Weak (rollup delete+insert, cross-timer race) |
| Design system and icons | Good | Good | Good (hex only in OG renderer, justified) |
| Accessibility | Good (touch targets 36/40 px) | Good (touch targets) | Good (touch targets) |
| SEO / noindex / URL state | Good (chapter CTA not deep link) | Good | Fair (group/compare URL state absent) |
| Analytics events | n/a | Fair (undercount, name drift) | Fair (name drift, manual-only logging) |
| Privacy / secrets | Fair | Fair | Fair (no erasure hook, scrubbing claimed but absent) |
| Tests | Strong (102 syllabus, 91 coverage) | Strong (76) | Strong (176) |
| Docs accuracy | Fair (report outdated) | Fair | Fair |

Headline: functionally complete and well tested (464 pytest pass, 2 skipped; ruff, ESLint and contrast clean), no Blockers. The risks are concurrency integrity under Postgres, flag evaluation latency in the request path, weak serverless rate limiting, no central erasure path, and layering violations against the stated non-negotiables. Several docs are stale or internally inconsistent.

Counts: Blocker 0, Major 7, Minor 17, Nit 3 (see section 7).

## 2. Traceability: F-02 Syllabus Structure and Coverage

Evidence key: tests are in `apps/api/modules/{syllabus,coverage}/tests`, web in `apps/web/src/modules/{syllabus,coverage}`. FR grouping below follows the PRD themes; where one row spans several FR ids they share the same evidence.

| FR | Requirement (short) | Status | Evidence | Note |
| --- | --- | --- | --- | --- |
| FR-1 | Course/level/scheme hierarchy, published only to public | Yes | `syllabus/models.py`, `syllabus/selectors.py`, syllabus public API tests | |
| FR-2 | Draft/published workflow, editors via admin | Yes | `syllabus/admin.py`, ROLLOUT editor workflow | |
| FR-3 | Full syllabus content for launch levels | Partial | Seed JSON counts: CA 32 papers, 304 chapters, 1478 topics; CS 407 chapters, 2772 topics; CMA 231 chapters | Loads as drafts pending editor verification (by design). CA/CS have 0 chapters with marks |
| FR-4 | Exam terms and papers per scheme | Yes | `syllabus/models.py`, seed | Terms lapse over time, see optimisation |
| FR-5..FR-8 | Subject/chapter/topic ordering, stable keys, drag and drop order | Yes | Admin ordering, report "follow-ups closed" | |
| FR-9 | Chapter maps across schemes (scheme switch) | Yes | `ChapterMap`, review queue, tests | Smarter maps closed per report |
| FR-10 | Public course pages, SEO | Yes | Routes under `/courses/...`, `buildHead`, JSON-LD Breadcrumb + Article | |
| FR-11 | OG images per page | Yes | `/og/courses/...`, `modules/seo/og-render.ts` | Runtime on Vercel Not verified |
| FR-12 | Enrollment (select level/scheme) | Yes | `/app/onboarding` | |
| FR-13..FR-16 | Coverage ledger: read/revise/tick events, append-only | Yes | `coverage/models.py`, ledger tests | No DB check on type/source (AUD-016) |
| FR-17 | Derived ChapterProgress and status rules | Yes | `coverage/domain/formula.py`, `test_components_match_shared_fixtures` | TS mirror shares `formula_cases.json` |
| FR-18 | Rollups per subject/paper/level, simple + weighted | Yes | `coverage/services.py recompute_rollups` | Weighted equals simple for CA/CS (no marks) |
| FR-19 | Round half up, thresholds | Yes | `round_half_up` and fixtures | |
| FR-20 | Revision scheduling, next_revision_due | Partial | `coverage/services.py` | Uses UTC date of `occurred_at`, can be off by a day in IST (AUD-018) |
| FR-21..FR-23 | Revision queue, due list, exam_ready logic | Yes | `/app/revision`, tests | PRD Q6 (green confidence overrides exam_ready) not implemented (AUD-025) |
| FR-24 | Undo / edit of events | Yes | Ledger compensation tests | |
| FR-25 | Syllabus tree UI with tick, filters | Yes | `/app/syllabus`, `SubjectContainer`, `ChapterContainer` | |
| FR-26 | Scheme switch with carry-over | Yes | `/app/settings/coverage`, chapter maps | Carry-over is manual |
| FR-27 | Time per chapter from tracker | Yes | tracking selectors by chapter | Cross-module, see AUD-005 |
| FR-28 | Flag `syllabus_coverage` server-side | Yes | `test_every_coverage_endpoint_answers_403_feature_disabled_when_the_flag_is_off` | |
| FR-29 | Deletion / export of own coverage data | Yes | coverage settings screen | Not part of a central erasure hook (AUD-004) |
| FR-30 | Idempotent writes (client_id) | Yes | `test_duplicate_client_id_changes_nothing` | Comment in `lib/offlineQueue.ts` mislabelled FR-30 (AUD-026) |
| FR-31 | Offline queue for writes | Partial | `coverage/lib/offlineQueue.ts` (IndexedDB) | Covers ticks and logs only; no mutation `scope` serialisation (AUD-001) |
| NFR | Rollup correctness invariants | Yes | property-style tests | |
| NFR | Latency (200/300/400 ms) | Not verified | no benchmarks, no `assertNumQueries` | |
| NFR | RLS on all tables | Yes (code) | `core/apps.py` post_migrate hook | Postgres RLS tests skipped locally, Not verified |
| NFR | A11y, 320 px, four themes | Partial | code review, design-showcase | Touch targets under 44 px (AUD-010); visual Not verified |

## 3. Traceability: F-01.1 Pomodoro Focus Timer

| FR | Requirement (short) | Status | Evidence | Note |
| --- | --- | --- | --- | --- |
| FR-1..FR-4 | Start round with focus length, subject/chapter tag | Yes | `focus/services.py start`, tests | |
| FR-5..FR-8 | Pause, resume, extend, end | Yes | services and focus tests | A paused timer lingers forever and blocks the stopwatch (optimisation) |
| FR-9 | Server clock, lazy settle under row lock | Yes | `_settle`, `domain/timing.py` | |
| FR-10 | Short/long break cycle | Yes | `rounds_before_long` | ERD name `rounds_before_long_break` (doc drift) |
| FR-11 | Skip break | Yes | `skip_break`, `focus_break_skipped` | |
| FR-12 | Heartbeat and presence rule 120 s | Yes | `test_a_present_student_finishes_the_round_and_the_break_starts` | |
| FR-13 | Away claim decides whether round counts | Yes | `test_a_student_who_was_away_decides_whether_the_round_counts` | |
| FR-14 | Optimistic version lock | Yes | model `version`, tests | |
| FR-15 | Idempotency via client_id | Yes | tests | |
| FR-16, FR-17 | Daily goal and streak | Deviates | shared with tracker via `tracking` services | Documented in ROLLOUT; PRD text implies a focus-own goal |
| FR-18 | Completed round becomes StudySession (source pomodoro) | Yes | `record_session` | |
| FR-19 | Sound, volume, notifications | Yes | `FocusSettingsForm` | Volume default 70 vs ERD 60 (doc drift) |
| FR-20 | Settings with reset to defaults | Partial | `SettingsContainer` | No reset control (AUD-012) |
| FR-21 | History page | Yes | `/app/focus/history` | |
| FR-22 | Live mini timer in /app layout | Yes | `LiveMiniTimer` | Pause/resume button 40 px |
| FR-23 | Mutual exclusion with stopwatch | Partial | `register_live_timer_provider`, `assert_no_live_timer` | Check-then-insert, not DB enforced (AUD-006) |
| FR-24 | Accessible timer (role=timer, aria-live) | Yes | `spokenDuration`, `minuteLabel` | |
| FR-25 | Flag `focus_timer` gating | Deviates | `core/feature_flags.py`, views | Code returns 403 `feature_disabled`; PRD FR-25 says 404, Build note 1 says 403 (doc is wrong) |
| FR-26, FR-27 | Settings and tz handling | Yes | tracker settings share tz | PRD numbering out of order |
| NFR | Timer accuracy, drift | Yes (logic) | `domain/timing.py` tests | Browser behaviour Not verified |
| NFR | Background tabs | Partial | `useFocusTimer.ts` heartbeat needs visible tab and activity in last 5 min | See optimisation |
| NFR | Tests per endpoint | Partial | 76 focus tests | Unauthenticated 401 test covers one endpoint; no throttle tests (AUD-013) |

## 4. Traceability: F-01.2 Time Tracker and Analytics

| FR | Requirement (short) | Status | Evidence | Note |
| --- | --- | --- | --- | --- |
| FR-1..FR-5 | Stopwatch start/stop/discard, server clock | Yes | `tracking/services.py start_stopwatch`, tests | `GET tracking/stopwatch/` performs a settle write (AUD-014) |
| FR-6..FR-10 | Manual entry, edit, delete, merge, split | Yes | `add_manual`, `SessionAudit` undo trail | |
| FR-11 | Tagging subject/chapter/activity | Yes | models, `SessionRow` | |
| FR-12 | Opt-in auto capture | Yes | `add_auto`, `useAutoCapture`, default off | |
| FR-13 | Idempotency via client_id | Yes | `test_duplicate_client_id_changes_nothing` | |
| FR-14..FR-16 | Daily goal, streak | Yes | `/app/tracker/goals` | Shared with focus |
| FR-17 | DailyRollup and HourBucket derived | Yes | `rollups.py`, `test_rollups_always_equal_the_sum_of_sessions_after_a_random_run_of_edits` | Delete+bulk_create unlocked (AUD-002) |
| FR-18..FR-21 | Reports by range, subject, activity | Yes | `/app/tracker/reports`, `ReportsContainer` | `by` limited to total, subject, activity |
| FR-22 | Group selector day/week/month | Partial | `ReportsContainer.tsx` | Group fixed by `defaultGroup(range)` (AUD-007) |
| FR-23 | Group/level roll-up and chapter drill-down | Partial | API supports, UI missing | AUD-007 |
| FR-24 | Source breakdown, verified-only filter | No | UI absent | PRD Q7, AUD-007 |
| FR-25 | Compare to previous period | Partial | compare always true | No toggle, `compare` not in URL |
| FR-26 | ETag / 304 on reports | Yes | `test_etag_gives_a_304_until_something_changes` | |
| FR-27 | Log page, day page | Yes | `/app/tracker/log`, `/app/tracker/day/$date` | |
| FR-28 | CSV export | Partial | `selectors.export_rows` | Silent cap at EXPORT_ROW_LIMIT; ERD says cursor pagination (AUD-015) |
| FR-29 | Settings (tz, goals) | Yes | `/app/settings/tracker` | tz not shown in reports (`void tz`) |
| FR-30..FR-32 | Delete all data, privacy | Partial | `delete_all_for_user` | No central account-deletion hook calls it (AUD-004) |
| FR-33 | Flag `time_tracker` gating | Deviates | 403 `feature_disabled` | PRD says 404; Build note 1 says 403 (doc is wrong) |
| FR-34 | Chapter time feeds coverage | Yes | tracking data selectors | |
| NFR | Performance 200/300/400 ms | Not verified | no benchmarks | |
| NFR | One live timer, DB enforced | Deviates | check-then-insert | AUD-006 |

## 5. ERD vs implementation

- F-02: tables, columns and unique constraints match the ERD. Gap: `coverage_event` has no DB check on `type`/`source` (ERD says "text + check") (AUD-016). `revision_days` stored as JSON is a documented deviation. RLS is enabled on all public tables by the `post_migrate` hook in `core/apps.py`; policy tests are Postgres-only and skipped locally (Not verified).
- F-01.1: tables match with two drifts: `rounds_before_long` (ERD `rounds_before_long_break`) and volume default 70 (ERD 60). The ERD is stale; the code is consistent.
- F-01.2: `tracking_studysession` is the single session table as designed; `tracking_dailyrollup_key` and `tracking_hourbucket_key` constraints present. ERD 2.3 says tz is "shared with focus_focussettings.tz", which no longer exists (doc is wrong).
- `makemigrations --check --dry-run`: no changes, so models and migrations agree.

## 6. Cross-cutting checks

Layering (views -> services -> selectors -> models; barrel-only):
- Violations: `coverage/views.py:148` ORM (`enrollment.scheme.subjects.filter`); `tracking/views.py:255` `selectors.SessionAudit.objects` in a view; `coverage/services.py:22` imports syllabus models and queries them at lines 352, 500, 536, 545, 710, 828, 887, 896, 905, 1019, 1070; `coverage/selectors.py:10,73-218` queries Topic, Subject, Chapter; `tracking/selectors.py:18,174,251` queries Subject and Chapter; `focus/selectors.py` imports tracking services.
- Web: routes are thin (largest 85 lines); no deep barrel bypass found. The ESLint boundary pattern `~/modules/*/*/*` misses two-segment deep imports (AUD-023).

Design system: no raw hex in feature modules. `modules/seo/og-render.ts` holds raw hex for satori with a justifying comment (AUD-024). Icons come from `@artha/design-system`. `ObservabilityProvider.tsx:18` reads `import.meta.env.MODE` outside `lib/env.ts` (AUD-022).

URL-driven and SEO: all `app.*` routes except the layout set `noindex` via `buildHead`. Public chapter route emits Breadcrumb and Article JSON-LD. Gaps: reports `group` and `compare` not in the URL; the public "Track this chapter" CTA goes to `/app/syllabus`, not a chapter; in-app URLs use scheme-specific UUIDs.

UI states and accessibility: loading, empty, error and offline states present in containers. `role="timer"`, aria-live regions and `role=progressbar` exist; the design showcase covers the new components. Touch targets: Button `sm` is 36 px and `icon` is 40 px, under the 44 px PRD target (mini timer pause/resume, session row menu, nav tabs). The coverage report claim "44 px targets verified" is false for these. Checkbox hit area is fine.

API: paths, auth and error shape match the PRDs. Flag-off returns 403 `feature_disabled` everywhere (the coverage test covers every endpoint). Throttle scopes defined in `config/settings.py`: syllabus_report 20/h, coverage_write 120/min, tracking_write 60/min, tracking_reports 120/min, tracking_export 6/h, focus_write 120/min; none are tested.

Analytics (PRD vs emitted): `session_merged` is emitted as `sessions_merged`; `session_logged` only for manual entries and with `{source}` only; property drift on goal_reached `{period}`, report_viewed `{range, split}`, report_exported `{range}`, goal_set `{count}`, focus_goal_reached `{}`, focus_away_claim `{counted}`, focus_break_skipped `{phase}`, focus_timer_conflict `{code}`, timer_conflict `{kind}`; `focus_session_started` lacks `source_device`; `focus_session_completed` fires only on a client-initiated complete, so server auto-closed and away-claimed rounds are missed.

Secrets: only `VITE_*` values reach the browser; the Gemini key is API-only. Missing from `apps/api/.env.example` and `docs/SETUP.md`: `POSTHOG_API_KEY`, `POSTHOG_HOST`, `POSTHOG_FLAG_TIMEOUT_SECONDS`, `FEATURE_FLAG_CACHE_SECONDS`.

DRY: `FeatureDisabled`, `Conflict`, the error hierarchy, `to_api_exception`, the flag permission and WriteView/parse are triplicated across `coverage/errors.py`, `tracking/errors.py`, `focus/errors.py` (focus re-exports tracking's). Shared goal/streak and `register_live_timer_provider` are used as designed (registered in `FocusConfig.ready`).

### Doc is wrong or outdated (fix the docs)
1. F-01.1 PRD FR-25 says 404 for flag off; Build note 1 and code say 403.
2. F-01.2 PRD FR-33 says 404; Build note 1 and code say 403.
3. F-01.2 ERD 2.3 references `focus_focussettings.tz` (gone).
4. F-01.2 ERD section 7 claims Sentry/PostHog `before_send` scrubbing; not implemented (alternatively fix in code, AUD-020).
5. F-01.2 ERD section 7 says export is "paginated by cursor"; it is a silent cap.
6. F-01.2 ERD says `delete_all_for_user` is invoked by account deletion; F-01.1 ROLLOUT says there is no central hook (code gap is AUD-004).
7. F-01.1 ERD `rounds_before_long_break` and volume 60 vs code `rounds_before_long` and 70.
8. F-02 coverage report: "No tracking module yet" (outdated), "44 px targets" (false), "API 212 passed" (now 464), inconsistent term dates.
9. F-02-ROLLOUT uses `uv run`; CLAUDE.md says venv/pip.
10. F-01.1 PRD FR numbering out of order (FR-26, FR-27 before FR-25).
11. `.env.example` and SETUP.md miss the PostHog variables (AUD-019).

### Code deviates from doc (fix the code)
AUD-001, 002, 004, 005, 006, 007, 011, 012, 015, 016, 018, 020.

## 7. Findings

### Major

**AUD-001 (Major, M): Coverage writes lack row locks and per-chapter mutation scope.** `coverage/services.py` has no `select_for_update`; `_progress_for` uses `get_or_create`; `recompute_rollups` does `Rollup.objects.filter(enrollment=...).delete()` then `bulk_create`. Two concurrent ticks (or an offline-queue flush racing a live tick) can lose a derived `read_pct`, or collide on the Rollup primary key and return a 500. Web hooks lack TanStack mutation `scope` to serialise per chapter. Unreproduced (SQLite locally). Fix: lock the enrollment (or ChapterProgress) row with `select_for_update` at the start of each write service, add `scope: { id: chapterId }` to mutations, and add a Postgres concurrency test.

**AUD-002 (Major, S-M): Tracking rollup refresh is delete+insert without a lock.** `tracking/rollups.py _refresh_day` runs `filter(...).delete()` then `bulk_create` per day; two concurrent session writes for the same user and day can violate `tracking_dailyrollup_key` or `tracking_hourbucket_key`. Unreproduced (needs Postgres). Fix: take `pg_advisory_xact_lock` keyed on the user in `refresh_days`, or use upsert.

**AUD-003 (Major, S-M): Feature-flag evaluation is in the request path.** `core/feature_flags.py` caches per process, and the `except Exception: return True` fail-open path is not cached, so a PostHog outage costs up to 1.5 s on every request against 300 ms p95 targets. Fix: cache the fail-open result briefly (for example 30 s) and consider local evaluation.

**AUD-004 (Major, M): No central account-deletion or erasure hook.** The ERD claims `delete_all_for_user` is invoked on account deletion; the ROLLOUT says it is not, and `profiles` has no deletion path. Users must delete via three separate screens. Fix: add an account-deletion service in `profiles` that calls each module's delete function through its service API, with a test.

**AUD-005 (Major, M): Layering violations.** ORM in views at `coverage/views.py:148` and `tracking/views.py:255`; about 20 foreign-model (syllabus) query sites in coverage and tracking services/selectors; `focus/selectors.py` imports tracking services. Violates CLAUDE.md rules 1 and 2. Fix: add syllabus selectors (subjects for scheme, chapters by ids, topics for chapter) and call those; move view ORM into selectors/services; invert the focus -> tracking dependency.

**AUD-006 (Major, S-M): Cross-timer exclusion is racy.** Stopwatch and Pomodoro each lock only their own row; `assert_no_live_timer` is check-then-insert, so two near-simultaneous starts (two tabs) can create both. The NFR says one live timer is enforced by the database. Fix: per-user advisory lock in both start paths, or a shared `live_timer` row with a unique user constraint.

**AUD-007 (Major, M): Reports UI is incomplete versus the PRD.** Missing group selector (FR-22), source breakdown and verified-only filter (FR-24, Q7), group/level roll-up and chapter drill-down (FR-23), compare toggle; `group` and `compare` are not in the URL (rule 5); time zone not displayed (`void tz`). Fix: surface the existing API parameters as URL search params and add controls.

### Minor

**AUD-008 (Minor, M):** Throttles and the flag cache use the default LocMem cache; `settings.py` has no `CACHES` and no `NUM_PROXIES`. On serverless, limits are per instance and anonymous throttling by `X-Forwarded-For` is spoofable. Fix: shared cache (Redis or DB cache) and `NUM_PROXIES`.

**AUD-009 (Minor, S):** Error/flag/view base classes are triplicated across coverage, tracking and focus. Fix: move to `core`.

**AUD-010 (Minor, S):** Touch targets below 44 px: Button `sm` 36 px, `icon` 40 px. Fix: raise to 44 px or add the Checkbox-style hit area; correct the coverage report claim.

**AUD-011 (Minor, S):** Analytics drift (names, properties, `source_device`, `session_logged` manual-only, `focus_session_completed` undercount). PRD metrics (capture coverage, tagging rate, completion rate) are unreliable. Fix: align names/properties to the PRD or update the PRD; emit completion from the server settle path.

**AUD-012 (Minor, S):** Focus settings have no "Reset to defaults" (FR-20). Fix: add a reset action.

**AUD-013 (Minor, S):** Test gaps: focus unauthenticated 401 test covers one endpoint; no throttle tests; no query-count or benchmark tests for latency NFRs. Fix: parametrise the 401 test over all focus URLs; add throttle and `assertNumQueries` tests.

**AUD-014 (Minor, S):** `GET focus/timer/` and `GET tracking/stopwatch/` perform writes (lazy settle). Fix: document, or keep the GET read-only and settle on a write path.

**AUD-015 (Minor, S):** CSV export silently truncates at `EXPORT_ROW_LIMIT`. Fix: return a truncation notice or stream with cursor pagination as the ERD states.

**AUD-016 (Minor, S):** `coverage_event` lacks a DB check on `type` and `source`. Fix: add `CheckConstraint` and a migration.

**AUD-017 (Minor, S):** Public chapter CTA "Track this chapter" goes to `/app/syllabus`, not the chapter; app URLs use scheme-specific UUIDs so links break after a scheme switch. Fix: key-based or redirecting deep links.

**AUD-018 (Minor, S):** `next_revision_due` uses the UTC date of `occurred_at`; IST students can see a one-day shift. Fix: convert to the student's tz.

**AUD-019 (Minor, S):** `.env.example` and `docs/SETUP.md` omit the PostHog API variables and flag cache settings.

**AUD-020 (Minor, S):** Sentry has `send_default_pii=False` but no `before_send` scrubbing as ERD section 7 claims; PostHog init uses default autocapture and identify sends the email, which may conflict with privacy statements. Fix: add scrubbing, restrict autocapture, or correct the docs.

**AUD-021 (Minor, S):** `focus/selectors.py` depending on tracking services and cursor pagination instead of the project `DefaultPagination` on some list endpoints should be confirmed as intentional and documented.

**AUD-022 (Minor, S):** `ObservabilityProvider.tsx:18` reads `import.meta.env.MODE` outside `lib/env.ts`.

**AUD-023 (Minor, S):** ESLint boundary pattern `~/modules/*/*/*` leaves two-segment deep imports unblocked (none found today). Fix: widen the pattern.

**AUD-024 (Minor, S):** Raw hex in `modules/seo/og-render.ts` (satori needs literals). Accepted with comment; add an explicit lint allow-list so the rule stays enforceable.

### Nit

**AUD-025 (Nit, S):** PRD Q6 (green confidence overrides exam_ready) is not implemented; implement or mark resolved in the PRD.
**AUD-026 (Nit, S):** Comment in `coverage/lib/offlineQueue.ts` says "(FR-30)" but offline is FR-31.
**AUD-027 (Nit, S):** Article JSON-LD on the chapter page is minimal (no dateModified or author).

## 8. Product optimisations (evidence-based)

F-02
1. CA and CS have no chapter marks (0 of 304 and 0 of 407), so the weighted toggle is a no-op for CA Intermediate, the launch course. Add Paper Analysis weights.
2. Deep-link the public chapter CTA into the chapter in the app.
3. Use stable keys in app URLs so links survive scheme switches.
4. Exam terms lapse; add an editor process or reminder for term rollover.
5. Auto-propose carry-over on scheme switch instead of manual review.

F-01.1
1. The heartbeat needs a visible tab and input in the last 5 min, so background tabs lose presence. Use `refetchIntervalInBackground` or Web Push.
2. A paused timer lingers forever and blocks the stopwatch; add an auto-end after N hours.
3. Add a cycle summary after a long break.
4. When blocked by a running stopwatch, offer a one-click switch.
5. Add reset-to-defaults and keyboard shortcuts for start/pause.

F-01.2
1. Surface the group selector, source and verified-only filters.
2. Add chapter drill-down from subject reports.
3. Show the time zone used for day boundaries.
4. Warn when an export is truncated.
5. Link report rows to the coverage chapter for one-tap tick-off.

## 9. Commands run and results

| Command | Result |
| --- | --- |
| `ruff check .` (apps/api) | All checks passed |
| `ruff format --check .` | 149 files already formatted |
| `pytest` (Python 3.12 venv, SQLite) | 464 passed, 2 skipped (Postgres-only RLS), about 21 s. By area: core 13, coverage 91, focus 76, profiles 8, syllabus 102, tracking 176 |
| `manage.py makemigrations --check --dry-run` | No changes detected |
| `tsc --noEmit` (apps/web) | 76 error lines, all environmental (missing @testing-library/*, satori, @resvg/resvg-js, jest-dom matcher types, because the macOS node_modules is incomplete on Linux). No genuine type errors seen in app code. Partially verified |
| ESLint `--max-warnings=0` (apps/web/src, packages/design-system/src) | Exit 0 |
| `pnpm check:contrast` | All required checks passed |

Environment notes: the macOS-built `.venv` and `node_modules` did not work on Linux, so a temporary Python 3.12 venv under `/tmp` was used. The device shell later failed (disk full). Test runs may have left `__pycache__` pyc files under `apps/api`; these are untracked build artefacts and could not be cleaned up from the failed shell.

## 10. Not verified

- Vitest and web unit tests: rolldown native binding missing for the Linux arch.
- Prettier check, full `pnpm check`, production build, `emails:check`.
- Postgres behaviour: RLS tests (skipped), concurrency findings AUD-001/002/006 (reasoned from code, not reproduced).
- Performance NFRs (200/300/400 ms): no benchmarks exist.
- Visual checks: four themes, 320 px layout, real-device accessibility and screen readers.
- OG image renderer runtime on Vercel (native resvg bundle size).
- Browser timer behaviour (background throttling, drift).

## 11. Prioritised remediation backlog

P1 (next sprint)
1. AUD-001 and AUD-002: locks plus a Postgres concurrency test (M).
2. AUD-006: per-user advisory lock for live timers (S-M).
3. AUD-003: negative caching for flag failures (S).
4. AUD-004: central account-deletion hook (M).
5. AUD-008: shared cache and NUM_PROXIES (M).

P2
6. AUD-005 and AUD-009: layering clean-up and shared base classes in `core` (M).
7. AUD-007: reports UI parity with the PRD (M).
8. AUD-011: analytics alignment (S).
9. AUD-010: 44 px targets (S).

P3
10. AUD-012 to AUD-024: small fixes, batched into one hygiene PR per module.
11. Doc corrections (section 6 list): one docs PR.
12. Nits AUD-025 to AUD-027.
