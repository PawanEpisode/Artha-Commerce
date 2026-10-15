# F-13 Today: API contract (Wave 3)

What `/api/v1/today/` answers today. The web builds against this file. It is checked by `modules/today/tests/test_contract.py`: if the code and this page disagree, that test fails, so change both together. PRD section 9 is the source; the places where W2 and W3 differ from it are listed under "Differences from the PRD".

Only `POST internal/tick/` (W6) is not built yet.

## Rules for every endpoint

- Bearer Supabase token. No token or a bad token: `401`.
- Flag `today_plan` off (or PostHog unable to answer, it fails closed): `403` with code `feature_disabled`.
- Errors have one shape: `{"error": {"code", "message", "details"}}`.
- Every response carries `version` (payload version, 1) and `server_time` (ISO 8601, UTC) except `304` and `404`.
- `GET` never writes: no plan, no settings row, no counter. Generation is the explicit `POST open/`.
- Dates are the student's local dates (the tracker's time zone, default `Asia/Kolkata`). A date is `YYYY-MM-DD`.

## Endpoints

<!-- contract:endpoints -->

| Method | Path | Purpose | Throttle |
| --- | --- | --- | --- |
| POST | `today/open/` | Ensure and return today's plan. Idempotent and single flight per student and day | `today_write` |
| GET | `today/plan/` | The plan for a date, read only, with `ETag` | `today_read` |
| GET | `today/preview/` | What a later day would hold, not stored | `today_read` |
| GET | `today/history/` | Day counters for the week strip and recaps | `today_read` |
| GET | `today/settings/` | The student's settings (never creates a row) | `today_read` |
| PUT | `today/settings/` | Save settings (creates the row on the first save) | `today_write` |
| POST | `today/plan/regenerate/` | Rebuild today's suggestions, keep what the student touched | `today_regen` |
| POST | `today/tasks/` | Add the student's own task | `today_write` |
| PATCH | `today/tasks/<uuid:task_id>/` | Edit an own task | `today_write` |
| DELETE | `today/tasks/<uuid:task_id>/` | Delete an own task (soft, undoable for 60 seconds) | `today_write` |
| POST | `today/tasks/<uuid:task_id>/start/` | Mark started, return the deep link | `today_write` |
| POST | `today/tasks/<uuid:task_id>/complete/` | Manual tick | `today_write` |
| POST | `today/tasks/<uuid:task_id>/skip/` | Skip | `today_write` |
| POST | `today/tasks/<uuid:task_id>/snooze/` | Snooze to a date or a preset | `today_write` |
| POST | `today/tasks/<uuid:task_id>/swap/` | Replace a suggestion with another | `today_write` |
| POST | `today/tasks/<uuid:task_id>/undo/` | Revert the last change within 60 seconds | `today_write` |

<!-- /contract:endpoints -->

Throttle scopes: `today_read` 120 per minute, `today_write` 120 per minute, `today_regen` 6 per day (used by `plan/regenerate/`).

### POST `today/open/`

Request (all optional): `client_id` (uuid), `date` (must be the student's own today), `source` (`nav`, `reminder`, `redirect`; default `nav`).

Responses:

- `200` plan payload plus `created` (`true` only for the call that made the plan). A second call returns the same plan and the same task ids with `created: false`.
- `200` with `state: "not_enrolled"` or `state: "post_exam"` and `plan: null`. No plan is stored for either.
- `400` `invalid_date` when `date` is not the student's local today. `400` `invalid` for other bad input.

Two simultaneous opens make one plan: one caller generates, the others wait on a per-student advisory lock and return the finished plan.

### GET `today/plan/`

Query: `date` (default the student's today), `lite` (`1` drops `why.signals` and `week`; the setting `lite_mode: "on"` does the same).

- `200` plan payload (no `created`). Header `ETag` (weak, stable while the content is unchanged; `server_time` is left out of it). Send `If-None-Match` to get `304`.
- `404` `plan_not_generated` when there is no generated plan for that date. The web then calls `open/`.

### GET `today/preview/`

Query: `date`, required, from tomorrow to 14 days ahead.

- `200` preview payload: up to four of the tasks that day would hold, their minutes, and the student's own tasks for that day. Nothing is stored.
- `400` `invalid_date` outside that range or when missing or malformed.

### GET `today/history/`

Query: `from` and `to` (default the last seven days ending today). At most 92 days.

- `200` one row per day that had a plan, newest first. A day without a plan is absent; the web draws it as "no plan".
- `400` `invalid_date` when `from` is after `to` or the range is longer than 92 days.

### GET and PUT `today/settings/`

`PUT` takes any of the fields below; fields left out stay as they are. `minutes_per_day` and `focus_papers` accept `null` for "auto".

- `minutes_per_day`: 15 to 240 or `null`. `focus_papers`: 1 to 4 or `null`.
- `disabled_kinds`: at most 20 registered kind names.
- `show_tomorrow`, `celebrate`: booleans. `lite_mode`: `auto`, `on`, `off`.
- `400` `invalid` with field errors in `details`. Changing settings affects the next generation; `plan/regenerate/` applies them to today's plan.

## Task actions (W3)

Every action below needs `client_id` (uuid): repeating a request with the same `client_id` returns the result of the first and writes nothing. `client_ts` (ISO 8601) is optional and orders writes from different devices. Every action answers `200` (`201` for a new own task) with the task response below, and the plan's counters so the ring updates without a refetch.

<!-- contract:task-response-keys -->
version, server_time, task, counts
<!-- /contract:task-response-keys -->

`task` has the task keys above. `counts` has the counts keys above. Some actions add keys:

<!-- contract:action-extra-keys -->
| Action | Extra keys |
| --- | --- |
| start | link |
| skip | suppressed_days |
| delete | undo_until |
| swap | old, new (instead of task) |

<!-- /contract:action-extra-keys -->

`link` is `{"path", "search"}`. `suppressed_days` is `14` when this was the third skip of the same work in 14 days (the provider stops offering it), else `null`. `undo_until` is the time after which `undo` answers `410`.

### The rules

- Done wins. A skip, snooze or swap that reaches a done task answers `409 state_conflict` with the current task in `details.task`. A completion that reaches a skipped or snoozed task completes it. Between open states the later `client_ts` wins; the loser gets `state_conflict`.
- A repeated action whose result already holds changes nothing: completing a done task, skipping a skipped one, starting a started one.
- Counters are recomputed from the rows after every action, never incremented.

### POST `today/tasks/`

`client_id`, `title` (1 to 120), `est_minutes` (1 to 180), optional `date` (today to 30 days ahead, default today), `subject_id`, `chapter_id` (must belong to the student's course; a chapter alone fills in its paper). `201` the task response; `200` for a retry of the same `client_id`. `429 quota_exceeded` at 20 own tasks for the day or 200 open tasks for later days (`details` has `kind`, `used`, `limit`). A day with no plan gets a draft that holds only own tasks until `open/` generates.

### PATCH and DELETE `today/tasks/<id>/`

`PATCH`: `version` (what the web last saw) and any of `title`, `est_minutes`, `subject_id`, `chapter_id`, `date`. A different `version` is `409 state_conflict`. `DELETE` is a soft delete answering `undo_until`. Both answer `403 provider_task_readonly` for a suggested task: skip or snooze it instead.

### POST `today/tasks/<id>/complete/`

`run_manual_action` (bool, default false): run the provider's action first (for a revision: also log it in coverage). A failing action never blocks the tick. Only a tick the student made can be undone; a task completed by the student's activity cannot.

### POST `today/tasks/<id>/skip/`

`reason` optional: `not_in_attempt`, `already_know`, `no_time`, `other`. (`swapped` is the swap endpoint's own.)

### POST `today/tasks/<id>/snooze/`

`until`: a date after the task's day and within 30 days, or `tomorrow`, `in_3_days`, `next_week`. A suggested task is suppressed until then and its provider decides whether to offer the work again. The student's own task moves to that day (same row) and is a suggestion again when the day opens. `400 invalid_date` out of range.

### POST `today/tasks/<id>/swap/`

Replaces a suggestion with another of the same group (else any) that is not already in the plan; the old task is `skipped` with reason `swapped`. `422 no_alternative`; `429 quota_exceeded` at 20 swaps a day. An own task cannot be swapped (`422 invalid_transition`).

### POST `today/tasks/<id>/undo/`

`from_state`: `done`, `skipped` or `deleted`. Within 60 seconds of the change: a tick goes back to where it was, a skip back to `suggested` (the same day only), a deleted own task comes back. After the window `410 undo_expired`. A `from_state` that is not the task's state is `422 invalid_transition`.

### POST `today/plan/regenerate/`

`expected_generation` (the `generation_no` the web holds), `reason` (`manual`, `exam_date`, `settings`, `provider_recovered`; default `manual`), `client_id`. Keeps done, started, snoozed, skipped, own and pinned tasks; replaces the suggested ones; adds new ones only while the plan is below 90 percent of the budget. Answers the plan payload plus `regenerated`:

<!-- contract:regenerated-keys -->
kept, replaced, replayed
<!-- /contract:regenerated-keys -->

`409 plan_changed` for a stale `expected_generation` (`details.generation_no` has the current one). `429` at 6 a day. `404 plan_not_generated` when today has no generated plan.

### What completes a task without a tap

The owning module announces what happened (`coverage_event_recorded` today) and Today completes the open tasks of that day, and of the day before when the event happened within three hours after local midnight. Replays and reordered events change nothing. `POST open/` also asks each provider about the open tasks of the plan (at most every 30 seconds): work done offline or on another device completes the task. `GET plan/` does neither: it stays a read.

## Payloads

Key lists are exact: the contract test compares them with a real response.

### Plan

<!-- contract:plan-keys -->
version, date, tz, server_time, state, phase, days_to_exam, generation_no, partial, failed_providers, budget_minutes, planned_minutes, counts, starter_task_id, backlog, tiles, tasks, streak, goal, celebrate, tomorrow, week
<!-- /contract:plan-keys -->

`open/` adds `created`; `plan/regenerate/` adds `regenerated`. `week` is absent in lite mode. `state` is `ready`. `phase` is one of `steady`, `build`, `consolidate`, `sprint`, `final`. `failed_providers` lists providers that timed out or failed (`partial` is then `true`). `tomorrow` is always `null` in W2: ask `preview/`. `streak` and `goal` come from the tracker, Today never computes its own. `celebrate` is true once the day is complete, the student wants it and it has not been shown (the action that records it is not built: the PRD lists no endpoint for it, W5 decides).

<!-- contract:counts-keys -->
planned, done, open, skipped, snoozed
<!-- /contract:counts-keys -->

<!-- contract:goal-keys -->
target_minutes, done_seconds, percent
<!-- /contract:goal-keys -->

<!-- contract:backlog-keys -->
kind, count, scheduled, label, link
<!-- /contract:backlog-keys -->

`backlog` is the notice for "38 revisions are overdue, 3 are scheduled today": `count` is how many more the provider has, `scheduled` how many are in today's plan.

<!-- contract:tile-keys -->
subject_id, subject_key, name, tasks
<!-- /contract:tile-keys -->

Tiles are in display order; the General pool (`subject_id: null`, empty `name`) comes last. `tasks` holds task ids.

<!-- contract:task-keys -->
id, origin, kind, slot, title, reason, reason_code, why, est_minutes, progress, target, state, link, subject_id, chapter_id, manual_action, is_must_do, version
<!-- /contract:task-keys -->

`why` is `{"modifiers": [...up to two], "signals": {...}}` (no `signals` in lite mode). `link` is `{"path", "search"}`; the path is an allow-listed `/app/...` route. `manual_action` is `{"label", "default"}` or `null`. `state` is one of `suggested`, `accepted`, `done`, `skipped`, `snoozed`.

<!-- contract:week-keys -->
date, outcome, planned_count, done_count
<!-- /contract:week-keys -->

`outcome` is `all`, `some`, `none` or `no_plan`.

### Open for a student with no plan to make

<!-- contract:state-keys -->
version, date, tz, server_time, state, plan
<!-- /contract:state-keys -->

### Preview

<!-- contract:preview-keys -->
version, date, tz, server_time, phase, days_to_exam, count, minutes, tasks, own_tasks
<!-- /contract:preview-keys -->

<!-- contract:preview-task-keys -->
kind, slot, title, reason, est_minutes, subject_key
<!-- /contract:preview-task-keys -->

### History

<!-- contract:history-keys -->
version, server_time, from, to, days
<!-- /contract:history-keys -->

<!-- contract:history-day-keys -->
date, planned_count, done_count, skipped_count, open_count, planned_minutes, outcome, closed
<!-- /contract:history-day-keys -->

### Settings

<!-- contract:settings-keys -->
version, server_time, minutes_per_day, focus_papers, disabled_kinds, show_tomorrow, celebrate, lite_mode
<!-- /contract:settings-keys -->

## Error codes

<!-- contract:errors -->

| Code | HTTP | When |
| --- | --- | --- |
| `feature_disabled` | 403 | The flag `today_plan` is off for this student |
| `plan_not_generated` | 404 | `GET plan/` for a date with no generated plan |
| `invalid_date` | 400 | A date outside what the endpoint allows |
| `invalid` | 400 | Any other bad input; field errors in `details` |
| `invalid_scope` | 400 | A paper or chapter that is not in the student's course |
| `task_not_found` | 404 | An unknown task, another student's task, or a deleted one |
| `provider_task_readonly` | 403 | Edit or delete of a suggested task |
| `invalid_transition` | 422 | The action is not possible from the task's state; `details.allowed` lists what is |
| `no_alternative` | 422 | Swap found nothing else to offer |
| `state_conflict` | 409 | Another device changed the task first (or a stale `version`); `details.task` is the current task |
| `plan_changed` | 409 | Regenerate with a stale `expected_generation` |
| `undo_expired` | 410 | Undo after the 60 second window |
| `quota_exceeded` | 429 | Own tasks per day, open tasks for later days, swaps per day, regenerations per day |

<!-- /contract:errors -->

## Differences from the PRD

| PRD | Built | Why |
| --- | --- | --- |
| `open/` takes a `date` | Must equal the student's local today, else `400 invalid_date` | A past or future plan is not generated on demand; `preview/` covers later days |
| Plan payload lists no `version` | `version: 1` added to every payload | The web can reject a payload it does not know |
| `backlog` is `{kind, count, label, link}` | `scheduled` added | The notice needs "3 are scheduled today" |
| `tomorrow: {count, minutes}` | Always `null` | Computing it would run every provider on every read; the web asks `preview/` |
| `settings/` `PUT` | Partial: fields left out are unchanged | Two screens edit different settings |
| `plan/` and `lite` | `lite=1` query parameter and the `lite_mode` setting both drop `why.signals` and `week` | The client decides in `auto` |
| `GET plan/` is 404 for no plan | Also 404 when the only row is a draft made by the student's own first task for that day | A draft has no generated tasks |
| `GET plan/` reconciles stale open tasks | `POST open/` does, `GET plan/` stays a pure read | PRD section 9 also says "GET never writes" (audit AUD-014); the web already opens before it reads |
| Task actions answer "200 task" | `{version, server_time, task, counts, ...}` | One shape for every action, and the ring updates without a refetch |
| Regenerate keeps done, accepted, snoozed, own and pinned | Skipped tasks are kept too | A skipped key is never offered twice in a day (PRD 5.7), so expiring it would bring it back |
| Regenerate fills a fresh plan | New tasks are added only below 90 percent of the budget, counting what stayed | The composer plans an empty day; without this a regeneration would double the plan |
| Regenerate with `provider_recovered` rebuilds the missing share | Rebuilds the suggested share as a whole | Simpler; kept tasks are untouched either way |
| Undo reverts "the last transition" | Done (manual ticks only), skipped (same day) and own deletion | A completion by the student's activity is a fact, not a click; a swap is undone by skipping the new task |
| A completion that finds a skipped task | Completes it | Done always wins over a stale skip |

## Not built yet (W6)

`POST internal/tick/` and the jobs behind it (pre-generation, the day sweep that expires open tasks, retention).
