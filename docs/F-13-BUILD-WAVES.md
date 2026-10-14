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
| Confirm the Vercel cron or `pg_cron` route for `POST internal/tick/` (Q-F13-14) | W6 |
| Review the phase thresholds and budget formula after the first 100 users | Beta |

## 5. Changes to the PRD to approve (found while building W1)

| # | PRD text | What the tests showed | What W1 does instead |
| --- | --- | --- | --- |
| 1 | 5.4 step 3 and FR-F13-04: starvation is a +150 need bonus after 4 untouched days, and "every paper appears at least every `ceil(N / F) + 1` days" | With noisy signals the bonus is too small: over 60 days with 6 papers a paper stayed out for 10 to 14 days (limit 4 to 7). The bound cannot hold from a bonus alone | A starved paper (never touched, or untouched for **3** days) takes a focus slot before any paper that is not starved, longest-waiting first. The +150 stays. Worst case is `3 + ceil(N / F) - 2` days, inside the PRD bound for every budget. Simulation: 4 budgets x 8 seeds, plus 60 seeds checked by hand. The PRD 5.6 example is unchanged |
| 2 | 5.5: "60 when unknown" for `daily_minutes` | Read literally the formula gives a 30 minute plan for a student we know nothing about, but section 7.3 promises "6 tasks, about 1 h" on the first plan | Unknown daily hours give a budget of 60 minutes (the formula is for known hours) |
| 3 | 5.4: a paper "untouched for 4 or more days" | A brand new student has no "days untouched" at all | `None` (never touched) counts as starved, which also rotates a new student's papers instead of re-picking the two loudest |

## 6. Status

| Wave | State |
| --- | --- |
| W1 Engine | Built 2026-10-14. 222 tests green (golden PRD 5.6, rules, 300-example properties, rotation simulation, state cases, deep links, registry, model constraints) on SQLite; `ruff check` and `ruff format --check` clean. Not yet run on PostgreSQL or inside the full repo suite (the linked computer has no usable Python environment), run `pnpm lint:api && pnpm test:api` once |
| W2 to W6 | Not started |
