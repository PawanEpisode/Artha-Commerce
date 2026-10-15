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

## 2. Waves (R2; W7 and W8 built, W9 onwards not started)

| Wave | Slices | Delivers |
| --- | --- | --- |
| W7 Planner engine (built 2026-10-15) | 16 | Migration `0002_planner`, pure `planner/` (capacity, milestones, health, re-plan, options) with fixtures |
| W8 Planner API (built 2026-10-15) | 17 | Services, endpoints, planner provider, replan events, flag `today_planner` |
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
| ~~Create the PostHog flag `today_planner` at 0 percent~~ Done by the owner before W8 (the planner endpoints read it, fail-closed like `today_plan`) | W8 |
| Sanity-check the planner numbers in `apps/api/modules/today/tests/fixtures/planner_golden.json` (hand-derived, derivations written beside them) and the `[VERIFY]` constants in `planner/constants.py` | Before the planner opens |

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
| W7 Planner engine | Built 2026-10-15 (see "W7 notes" and "Changes to the PRD found in W7" below). API only and pure: nothing is user-visible and there is no endpoint, flag wiring or service yet (W8). |
| W8 Planner API | Built 2026-10-15 (see "W8 notes" and "Changes to the PRD found in W8" below). Five endpoints under `today/planner/`, services, the planner provider, re-plan events, the cron sweep, eraser and exporter. Behind the flag `today_planner`; the web screen is W9. |

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

### W7 notes (planner engine, PRD slice 16)

- Built: migration `today.0002_planner` (`today_studyplan`, `today_milestone`, `today_replanevent`, 19 check constraints, the partial unique index for one active plan per student and enrolment, the open-milestone index, the re-plan history index; RLS is switched on for every public table by the existing post-migrate hook, and `core/tests/test_row_level_security.py` now lists the three tables); models `StudyPlan`, `Milestone`, `ReplanEvent`; read-only admin for plans (with their milestones) and re-plan events; the pure package `apps/api/modules/today/planner/` with `constants` (every tunable marked `[VERIFY]`), `capacity`, `milestones`, `health`, `options` and `replan` (`build_plan`, `should_replan`, `consecutive_missed_days`, `replan`, `summary_json`). A test checks that no planner module imports Django or reads the clock.
- Constraints the database adds to the ERD (all tested): `shortfall = max(0, remaining - capacity)` exactly, no negative minutes, `reading_deadline <= exam_date`, a whole-plan milestone has no paper key and a paper milestone has one, `done_at` is set exactly when a milestone is done, JSON size limits (params 2 KB, re-plan summary 8 KB, counted the way PostgreSQL renders jsonb). `today_milestone.subject_key` is 80 characters, as long as `syllabus_subject.key`.
- Tests: 143 planner tests. Golden scenarios worked out by hand (`fixtures/planner_golden.json`: a plan that fits, one that is at risk with the three options, a short runway, FR-F13-48's 120 h against 100 h, and two three-missed-day re-plans); 17 hypothesis properties (capacity never negative, shortfall exact, capacity never grows as days pass, milestones monotonic and unique, a paper finishes before the deadline exactly when its lane load fits the capacity, re-plan idempotent, a feasible option closes the gap, health bands ordered, the summary always fits the database check); and a simulation over 12 weeks with a steady student, a missed week (with and without slack, each option taken or declined), a student who stops, the exam day and after, and a moved exam date. 20 rules were broken on purpose (floor for ceil, off-by-one in the gap, the deadline recomputed, done rows moving, ...) and every one is caught by a test. Two found real defects while writing the tests: the summary size was measured compactly, which PostgreSQL's check would not have accepted; and a finished paper's first revision slid later with the calendar.
- Whole `modules/today` and `core` suites on PostgreSQL: 877 passed, 1 skipped; the one failure is `test_web_parity`, which reads a file in `apps/web` that the scratch layout does not have (it passes in the real repo).
- For W8 (the numbers and rules the services must respect): store the reading deadline when the plan is created (`planner.freeze_deadline`) and pass it back on every re-plan; clear it when the exam date or the scheme changes (apply `next_attempt` does this); mark a `finish_reading` milestone done when the last chapter is read (the date of the milestone becomes that day) rather than waiting for the weekly re-plan, and pass `finished_on` or the stored done rows back in; persist a chosen `skim_low_weight` choice (for example in `params["skimmed"]`) and pass `skim=True` for those chapters; build the milestone `Task` rows only from milestones that are open; compute `missed_days` from the tracker's and Today's activity with `consecutive_missed_days(active_days, today, since=plan start)`.

### W8 notes (planner API, PRD slice 17)

- Code: `planner_services.py` (writes, single flight per student), `planner_selectors.py`, `planner_serializers.py`, `planner_views.py`, `planner_provider.py` (`today.planner`, kind `planner_read`, behind the flag), `planner_hooks.py` (reading finished, exam date changed, scheme switched). The contract is `docs/F-13-API-CONTRACT.md` ("Planner"), checked by `test_contract.py`.
- Endpoints (flag `today_planner`, strict, independent of `today_plan`): `GET` and `POST today/planner/`, `POST today/planner/replan/` (throttle `today_replan`, 20 a day), `POST today/planner/options/`, `GET today/planner/events/`.
- The W7 notes are all applied: the reading deadline is frozen at creation and cleared on an exam-date change, a scheme switch or `next_attempt`; `finish_reading` is marked done on the day the last chapter is read (listening to `coverage_event_recorded`); a chosen skim is kept in `params["skimmed"]` and passed back as `skim=True` (the list is cut to fit the 2 KB column; a cut chapter counts in full again, which the health shows); only open milestones feed the provider; missed days come from tracked time plus done tasks.
- The cron tick has a new `planner` step: every active plan not checked in 12 hours is re-planned when a trigger applies (2 missed days, Monday, 3-day gap), otherwise its health numbers are refreshed; a plan whose exam passed is archived. Replan events older than 24 months are pruned. The eraser and exporter include the plan, milestones and events.
- Not built, on purpose: the "apply moves of 1 day or less silently" idea from the W7 observation (every move is stored and listed; the web in W9 can decide what to show). Recall and other providers are untouched.

### Changes to the PRD found in W8 (decided by Claude without a question, because the session ran unattended; each can be reversed in a small change)

| # | PRD / ERD text | What W8 found | What W8 does instead |
| --- | --- | --- | --- |
| 1 | Section 9 lists only R1 endpoints | R2 has no endpoint table | Five endpoints under `today/planner/` (contract doc). One active plan per student |
| 2 | FR-F13-49 "apply only the student's choice" | An exam-date change, new daily minutes or a scheme switch is itself the student's choice | Those apply their new dates at once; a shortfall found by a plain re-plan only stores numbers and waits for an option |
| 3 | `next_attempt` | The exam date belongs to F-03 | Choosing it sets the exam date on the enrolment through the coverage service, then the plan follows. Only a later open term of the same level is offered |
| 4 | Plan on scheme switch | Another scheme has other chapters | The old plan is `superseded`, a new plan starts, with a `scheme_switch` event. Done milestones are not carried over |
| 5 | Re-plan triggers | Section 6.F says "on demand, weekly, 2 missed days" without a clock | The cron tick checks each plan every 12 hours; an automatic re-plan with nothing new records no event |
| 6 | `must_do` | FR-F13-50: overdue by 3 or more days | `OVERDUE_MUST_DO_DAYS = 3`. A paper is "behind" when its reading milestone is `at_risk` or its date has come |
| 7 | Daily minutes | Enrolment `planned_minutes`, else the Today setting, else the student must say | `422 planner_not_ready` with `details.reason = no_daily_minutes` |
| 8 | Planner flag | Not in the PRD for the provider | The provider carries `flag="today_planner"` (fails open once a plan exists, which only a flagged student can make) |

### Changes to the PRD found in W7 (approved by the owner 2026-10-15, in the W7 session)

| # | PRD / ERD text | What W7 found | What W7 does instead |
| --- | --- | --- | --- |
| 1 | ERD "Planner": milestones are "papers sorted by (marks desc, paper_number) assigned to `lanes` (2) lanes" (how, is not said) | Strict alternation can leave the last `finish_reading` after the reading deadline while the health (aggregate capacity) says on track | Greedy least-loaded lane (the first lane wins a tie). A property test proves the two agree exactly: a paper finishes before the deadline if and only if its lane load times the lanes fits the capacity |
| 2 | Milestone dates when there is a shortfall | `finish_reading` and `first_revision` run past their windows, and past `mock = deadline + 7` | The dates are honest (not clamped) and `at_risk`; `mock` is moved to at least `first_revision + 1` so finish < first revision < mock always holds |
| 3 | `reading_deadline = exam - max(14, 30% of the runway)` for exams under about 14 days away | The deadline is already past, so the learn window is empty | Capacity 0, health `at_risk` when anything is unread, options are skim and next attempt only (`more_time` is left out: no reading days). Exam week is not squeezed |
| 4 | Triggers: ERD "2 consecutive missed days", FR-F13-49's example says 3 | Without a minimum gap a long break re-plans every day | 2 missed days, every Monday in the student's own time zone, and at least 3 days between automatic re-plans. A student's request, a new exam date and a scheme switch ignore the gap |
| 5 | "replan = same computation with today's progress" (re-evaluates the deadline formula) | The formula uses the shrinking runway, so the deadline slides later on every re-plan: 18 Dec at the start, 24 Dec after five weeks, 31 Dec after seven; the mocks slide from 25 Dec to 7 Jan even for a student who never misses a day, and missed days are hidden (capacity looks unchanged) | The reading deadline is frozen when the plan is created (the `reading_deadline` column) and kept until the exam date or scheme changes or the student picks `next_attempt`. Missed days now shrink the capacity honestly: three missed days on a plan with no slack turn it slightly behind with options instead of silently shifting dates (golden fixture) |
| 6 | "each day before the reading deadline" | Does a finish on the deadline day itself fit? | No: the deadline is the first day without reading (today counts as a full study day). A finish on or after it is `at_risk`. A first revision or mock may fall on the first day of exam week (`revise_until = exam - exam_week_days`) at the latest. Exam week is fixed at 7 days until a student setting exists |
| 7 | (not specified) a paper that has been read completely | The next re-plan listed its finish as "moved" to today, and its first revision slid later every week | It becomes `done` (reported in `ReplanResult.completed`, dated the day it was noticed), is never moved again, and the paper's first revision follows that date |
| 8 | (not specified) arithmetic | Percent maths on floats makes golden fixtures fragile | Integer arithmetic: capacity floored once at the end, work and daily rates rounded up, halves rounded up (not Python's half-to-even). Skim halves a chapter's remaining minutes (rounded up) |
| 9 | Options | `next_attempt` needs the next open term from F-02, which may not exist | The option is always listed (so the screen shows three), marked not feasible with no date when F-02 has none; `more_time` is marked not feasible above 720 minutes a day; `skim_low_weight` orders by marks per remaining minute (exact fractions, ties by chapter key) and is marked not feasible when skimming everything still falls short |

Observation for the owner (not changed): with the lane model a steady student's dates stay put for weeks, but a student who reads one paper after another instead of in parallel will see 4 to 8 "moved" milestones on each Monday re-plan until the reading is done (all small shifts, health stays on track). If that feels noisy in the beta, the cheap fix is to apply moves of 1 day or less silently in W8 and to mention only larger ones.
