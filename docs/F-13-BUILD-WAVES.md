# F-13 Today: build waves

Source: `docs/product/prd/F-13-today-daily-tasks.md` (section 13.2 slices) and `docs/product/erd/F-13-today-daily-tasks.md`. Written 2026-10-14. R1 ships behind the flag `today_plan` (fail-closed until the owner opens the beta), R2 behind `today_planner`.

## 0. What the repo already has, and what that changes

| Finding | Effect on the plan |
| --- | --- |
| `core/today_port.py` (from Recall W3) is a small stand-in: `register_task_provider(key, fn)`, `collect(user_id, now=)`, results shaped `key + tasks[kind,title,count,est_minutes]`. The ERD contract is richer (`today.registry`: `KindSpec`, `TaskCandidate`, `Signals`, completion rules, reconcile, manual actions). | W1 builds `today/registry.py` as the real contract. W2 adds one **bridge provider** `recall.legacy` that wraps `core.today_port.collect` and maps recall tasks to `TaskCandidate`s, so Recall appears in Today with no change to Recall. Recall can move to the new registry later in its own PR, then the bridge and the stand-in are deleted. |
| `core/events.py` is a synchronous `subscribe/emit` bus, not the F-06 outbox. | Today uses `subscribe` for completion (inline, idempotent through `today_taskevidence`). Event names and payloads follow the ERD so the outbox swap is mechanical. |
| F-06 `practice` does not exist (`practice_session_completed`, `register_origin("today")`). | The practice provider (slice 7b) is **deferred** until F-06 ships. R1 providers are coverage, the Recall bridge and the student's own tasks. The registry and completion rules are written so F-06 only adds a `today_providers.py`. |
| `coverage.selectors.study_state` and the event `coverage_event_recorded` are `[PROPOSED EXTENSION to F-02]` and do not exist. Existing: `get_active_enrollment`, `exam_date_of`, `due_for_revision`, `last_studied`, `coverage_pct_by_chapter`, `subject_chapter_rows`. | W2 adds `study_state` (plain data) and W3 adds the event emit, both as small, tested F-02 extensions. The AUD-018 UTC-date fix for `next_revision_due` is checked first in W2, because "due today" must be right for IST students. |
| `tracking.selectors.goals_progress`, `streak`, `day_totals` and `tracking.services.get_timezone`, `local_today` exist. | Used as is. Today never computes its own streak. |
| `core.registry` (erasers and exporters), `core.jobs`, `core.feature_flags` exist. AUD-003 (flag negative cache) is open. | Register the eraser and exporter in W6. The flag helper gets the negative-cache fix in W2 because Today is the hottest authenticated path. |

## 1. Waves (R1)

Each wave is shippable on its own: tests green, behind the flag, nothing user-visible until the flag is on. PRD slice numbers in brackets.

| Wave | Slices | Delivers | Exit check |
| --- | --- | --- | --- |
| **W1 Engine** (API, pure) | 1, 2, 3 (types) | `today` app with migration `0001` (all R1 tables, constraints, indexes), `registry.py` types and registration, `domain/` (constants, phases, budget, scoring, compose, states, deeplinks, estimates, week), golden fixtures from PRD 5.6, 60-day rotation simulation, property tests | `pytest modules/today` green; the PRD 5.6 example yields keys A, F, G, B, H, C and 61 minutes; migration applies; RLS list covers the new tables |
| **W2 Generate and read** (API) | 3, 4, 7a | Provider runner (thread pool, timeouts, partial status), context builder, `ensure_plan` (single flight, idempotent), `open`, `plan`, `preview`, `history`, `settings`, flag and throttles, `coverage/today_providers.py` (revision, next topics, next chapter), `recall.legacy` bridge, `study_state`, flag negative cache | Two simultaneous opens give one plan (Postgres test); 401, 403, 404 matrix; `GET plan/` never writes; contract doc `docs/F-13-API-CONTRACT.md` with a drift test |
| **W3 Act and complete** (API) | 5, 6 | Transitions with row locks and recount, own tasks CRUD and quotas, skip, snooze, swap, undo, regenerate, completion subscribers and evidence, reconcile on read, `coverage_event_recorded` emit, late-night grace | Replayed and out-of-order events change nothing; done beats a stale skip; counters equal the aggregate after random transitions |
| **W4 Today screen** (web + design system) | 8, 9, 10 | Module skeleton, `lib/` (plan view model, transitions mirror with parity test, limits parity), hooks, design-system `ProgressRing` segments, `Celebrate`, `Sheet`, icons, showcase, header, starter, tiles, rows, loading, partial, empty and error states, `/app/today` route, `/app` redirect | Four themes, 320 to 1280 px, `pnpm check` green, contrast check passes |
| **W5 Actions and motivation** (web) | 11, 12 | Tick with undo, menu, why, skip, snooze, swap, add task sheet, optimistic updates with per-task scope, streak and goal, week strip, celebration, tomorrow card, overload notice, comeback copy, day view `/app/today/$date` | All task actions reachable by keyboard; focus moves to next open row; no swipe-only action |
| **W6 Offline, settings, cron, launch** (web + API) | 13, 14, 15 | Offline plan cache and queued actions (queue moved to `src/lib`), lite mode, analytics events with schema contract test, settings page, exam date card, onboarding handoff, `/features/today` and catalog entry, cron (pregenerate, close sweep, prune), digest selector, domain events, eraser and exporter, rollout doc `docs/F-13-ROLLOUT.md` | **R1 complete.** Beta runbook written; flag `today_plan` stays off until the owner opens the cohort |

## 2. Waves (R2, planned, not started)

| Wave | Slices | Delivers |
| --- | --- | --- |
| W7 Planner engine | 16 | Migration `0002_planner`, pure `planner/` (capacity, milestones, health, re-plan, options) with fixtures |
| W8 Planner API | 17 | Services, endpoints, planner provider, replan events, flag `today_planner` |
| W9 Planner web and adaptive | 18 | `/app/planner`, health card, re-plan flow, feedback and adaptive budget (migration `0003`), bonus round |
| Provider slices | 19 | One per owning module as F-10, F-11, F-14, F-04, F-09 and F-06 practice ship; Recall moves off the bridge |

## 3. Decisions taken (defaults, change if you disagree)

1. Planner stays inside the `today` module (PRD 4.3).
2. R1 composes for the primary (most recent) enrolment only.
3. Practice provider waits for F-06; the Recall bridge covers recall, formula and revision cards meanwhile.
4. Own tasks count in completion and celebration (Q-F13-4), manual revision tick asks "Also log revision", default on (Q-F13-6), rotating focus papers with the starvation guarantee (Q-F13-5), streak stays the tracker's (Q-F13-1).
5. Estimates per kind use the PRD defaults, marked `[VERIFY]` (Q-F13-12).

## 4. Open items for the owner

| Item | Needed by |
| --- | --- |
| Create the PostHog flag `today_plan` (0 percent) and, later, `today_planner` | W2 (API reads it) |
| ~~Confirm the cron route for `internal/tick/` (Q-F13-14)~~ Resolved in W6: `GET`/`POST today/internal/tick/` with `TODAY_TICK_SECRET`, called every 5 minutes by any scheduler (see `docs/F-13-ROLLOUT.md`) | W6 |
| Review the phase thresholds and budget formula after the first 100 users | Beta |

## 5. Changes to the PRD (found while building W1). Approved by the owner 2026-10-15

| # | PRD text | What the tests showed | What W1 does instead |
| --- | --- | --- | --- |
| 1 | 5.4 step 3 and FR-F13-04: starvation is a +150 need bonus after 4 untouched days, and "every paper appears at least every `ceil(N / F) + 1` days" | With noisy signals the bonus is too small: over 60 days with 6 papers a paper stayed out for 10 to 14 days (limit 4 to 7). The bound cannot hold from a bonus alone | A starved paper (never touched, or untouched for **3** days) takes a focus slot before any paper that is not starved, longest-waiting first. The +150 stays. Worst case is `3 + ceil(N / F) - 2` days, inside the PRD bound for every budget. Simulation: 4 budgets x 8 seeds, plus 60 seeds checked by hand. The PRD 5.6 example is unchanged |
| 2 | 5.5: "60 when unknown" for `daily_minutes` | Read literally the formula gives a 30 minute plan for a student we know nothing about, but section 7.3 promises "6 tasks, about 1 h" on the first plan | Unknown daily hours give a budget of 60 minutes (the formula is for known hours) |
| 3 | 5.4: a paper "untouched for 4 or more days" | A brand new student has no "days untouched" at all | `None` (never touched) counts as starved, which also rotates a new student's papers instead of re-picking the two loudest |

## 6. Status

| Wave | State |
| --- | --- |
| W1 Engine | Built 2026-10-14. 222 tests green (golden PRD 5.6, rules, 300-example properties, rotation simulation, state cases, deep links, registry, model constraints) on SQLite; `ruff check` and `ruff format --check` clean. Not yet run on PostgreSQL or inside the full repo suite (the linked computer has no usable Python environment), run `pnpm lint:api && pnpm test:api` once |
| W2 Generate and read | Built 2026-10-15. Provider runner, context builder, single-flight `open_today`, endpoints `open`, `plan`, `preview`, `history`, `settings`, `coverage.study_state` and coverage providers, `recall.legacy` bridge, admin, `sync_today_providers`, `docs/F-13-API-CONTRACT.md` with a drift test. Today and coverage-provider suites green on SQLite and PostgreSQL (two simultaneous opens give one plan, verified on PostgreSQL; 401/403/404 matrix; `GET plan/` issues no writes). The flag negative cache item was already done in the repo and is dropped. AUD-018 was fixed after W3: coverage now derives `next_revision_due` from the student's local day (the old pin test became four regression tests). Differences from the PRD are listed in the contract doc |
| W3 Act and complete | Built 2026-10-15. Task actions (start, complete, skip, snooze, swap, undo), own tasks (add, edit, soft delete with undo, quotas, drafts for later days), regenerate (optimistic, 6 a day), completion by events with idempotent evidence and the late-night grace, reconcile on `open/`, and the `coverage_event_recorded` emit (F-02 extension). Row locks plan then task; counters recomputed after every action. Exit checks met on PostgreSQL: replayed, duplicated and reordered events change nothing (including five workers at once), done beats a stale skip however two requests interleave, counters equal the aggregate after 12 seeded random 60-action runs. Three rules were broken on purpose and each was caught by a test. Extended `docs/F-13-API-CONTRACT.md` (drift test now covers every endpoint and error code). Two real bugs were found and fixed by the new tests (a retry race on own-task creation, and evidence reviving a replaced task). Full API suite on PostgreSQL: only the 7 tests that read monorepo files absent in the scratch layout fail (focus/tracking/recall contracts, email brand), same as before W3 |
| W4 | Built 2026-10-15 (see "W4 notes" below) |
| W5 | Built 2026-10-15 (see "W5 notes" below) |
| W6 | Built (2026-10-15) |

### W3 decisions (approved by the owner 2026-10-15; differences from the PRD, listed in the contract doc)

1. **Reconcile happens in `POST open/`, not `GET plan/`.** The PRD says both "GET never writes" and "reconcile on GET plan"; the first wins. The web already opens before it reads. Reconcile is limited to once per 30 seconds per student and day.
2. **Regenerate keeps skipped tasks** (the PRD list omits them). Expiring a skipped task would let the same work come back the same day, which section 5.7 forbids.
3. **Regenerate adds new suggestions only below 90 percent of the budget**, counting what stays, never above 125 percent. Without it a regeneration doubles a full plan.
4. **Undo covers done (manual ticks only), skipped (same day) and own-task deletion.** Work completed by the student's activity cannot be un-ticked. A swap is undone by skipping the new task.
5. **Task actions answer `{version, server_time, task, counts, ...}`** instead of the bare task, so the ring updates without a refetch.
6. **A completion that finds a skipped or snoozed task completes it** (done beats a stale skip), which goes beyond the transition table the web mirrors; W4's `transitions.ts` must treat complete as always allowed from skipped and snoozed.
7. **The `celebrated_at` write has no endpoint** in PRD section 9. W5 needs one (suggested: `POST today/plan/celebrated/`); not built.

### W4 notes (Today screen, web and design system)

- Built: `modules/today` (lib: types, plan view model, time, transitions mirror, limits, search, keys, api; hooks: flag, plan query; components: header, paper tile, task row; containers: Today, home redirect), route `/app/today` (search `paper`, `task`, `add`, `from`), `/app` redirects to Today when `today_plan` is on (`/app?home=true` opts out, so Today's own "back" link cannot loop), nav link "Today" behind the strict `today_plan` flag, design system `ProgressRing` `segments` (1 to 12) and `segmentLabel`, `Celebrate`, icons `Shuffle` and `CalendarClock` (the other five already existed), showcase entries. `Sheet` already existed, so nothing was added.
- Parity: `transitions.test.ts` runs every case of the API's `state_transitions.json`; `test_web_parity.py` compares `lib/limits.ts` with `domain/constants.py`.
- W4 is read only: the marker on a row is a status, the "Start here" button is a link. Tick, menu, skip, snooze, swap, add sheet and optimistic updates are W5.
- For W5: the mirror follows the shared table exactly (a skipped or snoozed task cannot be ticked); the server's "completion beats a stale skip" rule is applied when the screen refetches, so the optimistic path should not offer tick on a skipped or snoozed row. `celebrated_at` still needs an endpoint (for example `POST today/plan/celebrated/`); until then `Celebrate` fires once per page load when the plan says `celebrate`.
- Not shown yet because the plan payload carries no field for it: the comeback banner (PRD 7.3). Add `budget_source` to the plan payload in W5 if the banner is wanted.

### W5 notes (actions and motivation)

- API (small, approved): `POST today/plan/celebrated/` (sets `celebrated_at` once, idempotent), plan payload gains `budget_source` and `closing` (`celebrate`, `calm` or `null`); contract doc and `test_celebrated.py` updated; the whole `modules/today` suite passes on PostgreSQL.
- Web: tick with 10 s Undo toast and a 60 s "Restore" in the menu, "also log it" sheet for a manual action (default from the task), task menu (why, swap, snooze, skip with reason, edit and delete for own tasks), add-task sheet (`?add=true`), optimistic updates with per-task ordering and per-task rollback (409 shows the server task, 422 and 404 refetch), focus moves to the next open row, Start marks the task in progress then opens its link with `from=today&task=<id>`, week strip, tomorrow card (after 18:00 or when the day is closed, unless the setting is off), celebration once per day via `plan/celebrated/`, calm "Day closed" card, overload notice, comeback copy, long-day note, goal bar and streak hint from the tracker values, day view `/app/today/$date` (preview, past recap, no plan).
- Fixed from W4: the header read the streak as an object; the API sends a number.
- Differences to know: a snooze has no Undo (the API undoes only a tick, a same-day skip and an own-task delete), so its toast has no Undo button; the `?task=<id>` link opens the task sheet at "Why this?" and highlights the row; keyboard shortcuts j, k and x of the desktop wireframe are not built (every action is reachable with Tab, Enter and Space); "stuck" own-task prompt (FR-F13-29) and the exam date card are W6.
- Not checked by eye: the new screens in the four themes at 320 to 1280 px (the contrast check and component tests pass).

### W6 notes (offline, settings, cron, launch)

- Built: offline plan cache (IndexedDB `artha-today`) with offline, reconnect, stale (over 6 h) and previous-day banners and a day-rollover bar; ticks and own-task add/delete queue in the shared offline queue (scope `today`) and replay idempotently by `client_id`; lite mode (`open/` accepts `lite`, under 12 KB gzipped); analytics events from the shared `event_schema.json` with a byte-identical API and web copy checked by `test_event_schema.py`; settings page `/app/settings/today`; exam date card; first-plan reveal from onboarding (`/app/today?from=onboarding`, linked from `CatchupResult` when `today_plan` is on); stuck own task prompt (carried 3 times: Keep, Snooze or Delete); `/features/today` (catalog status `soon`, landing beat); API cron tick (pregenerate, close sweep, prune), digest selector, domain events, account eraser and exporter.
- Differences to know: only ticks and own-task add/delete work offline; skip, snooze, swap, edit and undo need a connection. An offline-added task shows "Waiting to sync" and cannot be ticked until it syncs. A plan closes 3 h after its day ends; open provider tasks expire and count as skipped, open own tasks carry to the next day (3 times at most). The API analytics sink is a log line until a PostHog server client is plugged in with `analytics.set_sink`. Keyboard shortcuts j, k and x are still not built.
- Flag `today_plan` stays off until the owner opens the beta cohort (`docs/F-13-ROLLOUT.md`).
