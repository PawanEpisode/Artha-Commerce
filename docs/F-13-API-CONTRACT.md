# F-13 Today: API contract (Wave 2)

What `/api/v1/today/` answers today. The web builds against this file. It is checked by `modules/today/tests/test_contract.py`: if the code and this page disagree, that test fails, so change both together. PRD section 9 is the source; the places where W2 differs from it are listed under "Differences from the PRD".

Endpoints built in W3 (tasks, regenerate, internal tick) are in "Not built yet" and are not checked.

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

<!-- /contract:endpoints -->

Throttle scopes: `today_read` 120 per minute, `today_write` 120 per minute, `today_regen` 6 per day (declared now, used by `plan/regenerate/` in W3).

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
- `400` `invalid` with field errors in `details`. Changing settings affects the next generation; regeneration of an existing plan arrives with W3.

## Payloads

Key lists are exact: the contract test compares them with a real response.

### Plan

<!-- contract:plan-keys -->
version, date, tz, server_time, state, phase, days_to_exam, generation_no, partial, failed_providers, budget_minutes, planned_minutes, counts, starter_task_id, backlog, tiles, tasks, streak, goal, celebrate, tomorrow, week
<!-- /contract:plan-keys -->

`open/` adds `created`. `week` is absent in lite mode. `state` is `ready`. `phase` is one of `steady`, `build`, `consolidate`, `sprint`, `final`. `failed_providers` lists providers that timed out or failed (`partial` is then `true`). `tomorrow` is always `null` in W2: ask `preview/`. `streak` and `goal` come from the tracker, Today never computes its own. `celebrate` is true once the day is complete, the student wants it and it has not been shown (the action that records it arrives with W3).

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

<!-- /contract:errors -->

## Differences from the PRD

| PRD | W2 | Why |
| --- | --- | --- |
| `open/` takes a `date` | Must equal the student's local today, else `400 invalid_date` | A past or future plan is not generated on demand; `preview/` covers later days |
| Plan payload lists no `version` | `version: 1` added to every payload | The web can reject a payload it does not know |
| `backlog` is `{kind, count, label, link}` | `scheduled` added | The notice needs "3 are scheduled today" |
| `tomorrow: {count, minutes}` | Always `null` | Computing it would run every provider on every read; the web asks `preview/` |
| `settings/` `PUT` | Partial: fields left out are unchanged | Two screens edit different settings |
| `plan/` and `lite` | `lite=1` query parameter and the `lite_mode` setting both drop `why.signals` and `week` | The client decides in `auto` |
| `GET plan/` is 404 for no plan | Also 404 when the only row is a draft made by the student's own first task for that day | A draft has no generated tasks |

## Not built yet (W3 and later)

`POST plan/regenerate/`, `POST tasks/`, `PATCH` and `DELETE tasks/{id}/`, `start`, `complete`, `skip`, `snooze`, `swap`, `undo`, `POST internal/tick/`.
