# F-15 Recall: API contract for the web (R1 cards, reviews, queue, pack, stats, platform decks, export and erase)

Backend: `apps/api/modules/recall` (flag `recall_system`). Source of truth for behaviour: `docs/product/prd/F-15-flashcards-spaced-revision.md`
and `docs/product/erd/F-15-flashcards-spaced-revision.md`. This file fixes the exact request and response shapes and was
derived from `modules/recall/urls.py`, `views.py`, `serializers.py` and `errors.py`. `modules/recall/tests/test_api_contract.py`
fails when a path documented here no longer resolves in the URL conf, or when a route exists that is not documented here.
All paths are under `/api/v1/`. Auth: `Authorization: Bearer <Supabase JWT>`. Detail routes answer 404 for anything the caller does not own.
Ids are UUID strings, timestamps are ISO 8601 UTC (`...Z`).

## Conventions

- **Errors:** `{"error": {"code": str, "message": str, "details": any|null}}`. Codes used here: `feature_disabled` (403, flag `recall_system` off or unknown,
  it fails closed; the four export and erase paths are never gated), `not_authenticated` (401), `not_found` (404), field map (400), `invalid_fields`,
  `unknown_kind`, `unknown_chapter`, `bulk_too_large`, `not_in_this_release`, `batch_too_large`, `invalid_setting`, `deck_too_large` (422), `duplicate_card`,
  `edit_conflict`, `not_undoable` (409), `card_deleted`, `undo_expired` (410), `bad_cursor` (400), `deck_not_found` (404), `quota_exceeded` (429, `details`
  `{kind, used, limit, plan}`), `throttled` (429), `forbidden` (403, tick secret). `recall_unavailable` (503) is not raised by these endpoints: it is what the Notes
  endpoints that create cards answer when this module is not installed (`core/recall_port.py`).
- **Lists:** cursor pagination `{"items": [...], "next_cursor": str|null}`; send `?cursor=<next_cursor>&limit=<n>`. Cursors are opaque, a bad one is 400 `bad_cursor`.
- **Throttles (per student):** `recall_review` 600/min (reviews, batches, sessions), `recall_write` 120/min (card, deck, settings and catch-up writes),
  `recall_export` 6/hour (JSON and CSV export and erase share it), every other read the default 300/min. Rating a card is never limited by quota; the throttle is politeness.
- **Idempotency:** every create takes a client generated UUID (`client_id` for cards, sessions and selections, `id` for a review event). A replay returns the stored row
  with 200 instead of 201. The review log is append only: an event id is recorded once and a resend answers `status: "duplicate"`.
- **Privacy:** card text, note text, deck titles and ids leave the API only in response bodies, never in a log line, Sentry event or analytics event.

## Cards

`Card`: `{id, rev, item_id, item_version_id, kind, ordinal, front_md, back_md, fields, state (0..3), state_name, status: "active"|"suspended"|"archived"|"deleted",
importance: "bullet"|"important"|"mandatory", chapter: {id, key, name, subject_key, subject_name}|null, subject_key, tags, reference_keys, deck_ids, badges: ("suspended"|"tricky"|"recheck"|"buried")[],
source: {origin, module, ref_id, locator}|null, due_at, buried_until, reps, lapses, created_at, updated_at}`. `CardDetail` = `Card` + `memory`
`{stability, difficulty, due_scheduled_at, postponed_until, due_at, last_review_at, reps, lapses, step}`.

| Method and path | Body or query | Success | Errors |
| --- | --- | --- | --- |
| `GET recall/cards/` | `?subject_key&chapter_id&kind&tier&state=new\|learning\|review\|suspended\|tricky\|recheck&deck_id&q (<=200)&status&sort=newest\|oldest\|updated&cursor&limit<=100 (default 30)` | 200 `{items: Card[], next_cursor, server_time}`. `deck_id` filters cards of the student's own decks | 400 |
| `POST recall/cards/` | `{client_id, kind, fields, chapter_id?, topic_id?, importance? (default "bullet"), tags?, reference_keys?, deck_ids?, force?}` | 201 `{item_id, kind, existing, cards: Card[]}` (200 with `existing: true` on replay) | 409 `duplicate_card` details `{card_id, item_id}` unless `force`; 422 `invalid_fields` details `{errors:[{field, code, message}]}`, `unknown_kind`, `unknown_chapter`; 429 `quota_exceeded` |
| `POST recall/cards/from-selection/` | `{client_id, origin: "note_highlight"\|"solution_text"\|"chapter_page"\|"question_review", selection_text (<=8000), source: {module, object_id, locator?}, chapter_id?, topic_id?, kind?, quick? (true), cloze? (false), force?}` | 201 as create plus `{card_id, undo_token, undo_seconds}` (200 on replay) | as create |
| `POST recall/cards/undo-delete/` | `{undo_token}` | 200 `CardDetail` (restores a card deleted within the last 10 seconds, or undoes a quick selection card) | 410 `undo_expired`; 409 `not_undoable` |
| `POST recall/cards/bulk/` | `{ids: uuid[] (max 200), action: "move_chapter"\|"set_importance"\|"add_tag"\|"suspend"\|"delete"\|"add_to_deck", chapter_id?, importance?, tag?, deck_id?}` (`importance`, `tag`, `deck_id` are required by their action) | 200 `{count}` | 422 `bulk_too_large`; 400 |
| `GET recall/cards/{id}/` | | 200 `CardDetail` | 404; 410 `card_deleted` |
| `PATCH recall/cards/{id}/` | `{base_rev (required), fields?, chapter_id? (null means Unsorted), topic_id?, importance?, tags?}`; only sent keys change | 200 `CardDetail` | 409 `edit_conflict` details `{server_fields, rev}` (nothing written); 410; 422 |
| `DELETE recall/cards/{id}/` | | 200 `{deleted: true, card_id, undo_token, undo_seconds: 10}` | 404 |
| `GET recall/cards/{id}/reviews/` | | 200 `{items: [{id, rating, reviewed_at, mode, duration_ms, scheduled_days, retrievability_before}]}` | 404 |
| `POST recall/cards/{id}/suspend/`, `unsuspend/`, `reset/`, `recheck-ok/` | `{}` | 200 `CardDetail` (`reset` forgets the memory and starts the card as new) | 404; 410 |
| `POST recall/cards/{id}/bury/` | `{until?: datetime}` (default: the start of the next study day) | 200 `CardDetail` | 404; 410 |

Edits create a new item version only when the text changes. `base_rev` must be the `rev` the client last saw (a review also raises `rev`).

## Reviews, sessions, catch-up, offline sync

`ReviewEvent`: `{id (client event id), card_id, rating: 1..4, reviewed_at, duration_ms?, session_id?, mode? ("normal" default), item_version_id?, device_id? (<=64), tz_offset_min? (-840..840)}`.
`CardPatch` (what a review changed): `{id, rev, state, state_name, status, due_at, buried_until, reps, lapses, leech, needs_recheck}`.
`ReviewResult`: `{event_id, status: "applied"|"duplicate"|"applied_to_deleted"|"stale_content"|"late_unapplied"|"invalid", reason, merged: bool, card: CardPatch|null}`.

| Method and path | Body or query | Success | Errors |
| --- | --- | --- | --- |
| `POST recall/reviews/` | `ReviewEvent` | 201 `ReviewResult` (200 when `status` is `duplicate`) | 404 (unknown card); 422 `{detail, code}` with code `bad_rating` or `bad_mode`; 400 |
| `POST recall/reviews/batch/` | `{events: ReviewEvent[]}` (1 to 100, in any order, from any device) | 200 `{results: ReviewResult[], cards: CardPatch[], server_time}`. An event that fails validation comes back with `status: "invalid"`, `reason: "invalid_event"` | 422 `batch_too_large` (more than 100) |
| `POST recall/reviews/undo/` | `{undo_id (new event id), voids_id}` | 200 `{undo_id, voids_id, card: CardPatch|null}` | 409 `not_undoable` (only the last 10 reviews of a session, received less than 30 minutes ago, once); 404 |
| `POST recall/sessions/` | `{client_id, source, spec?, tz?, planned_count?}` | 201 session (200 on replay): `{id, client_id, source, status, started_at, ended_at, local_date, planned_count, reviewed}` | 400 |
| `POST recall/sessions/{id}/close/` | | 200 session plus `summary` | 404 |
| `POST recall/catchup/rebalance/` | `{days? (1..14, default 7)}` | 200 `{moved, kept_today, days, per_day: int[]}`; a second call moves nothing. Moved cards are postponed to the first instant of the next study day, so they are not due today | |
| `PUT recall/vacation/` | `{until: "YYYY-MM-DD"|null}` (today to 60 days ahead; `null` ends it) | 200 `{vacation_until, postponed, restored}` | 400; 422 `invalid_setting` (date out of range) |
| `GET\|POST recall/internal/tick/` | header `X-Recall-Tick-Secret: <RECALL_TICK_SECRET>` or `Authorization: Bearer <secret>`; no student token | 200 `{sessions_closed}` (closes sessions idle for 60 minutes). Open whatever the flag says, bounded, safe to repeat | 403 `forbidden` (also when the secret is not configured) |

**Offline sync.** A device holds a pack (below), records `ReviewEvent`s with a client generated `id` and `reviewed_at`, and sends them with `reviews/batch/` as soon as it is online, oldest first,
at most 100 per call. Resending is always safe. An event older than 30 days is `late_unapplied` (kept in the log, not applied to the card). An event for a card whose text changed in a substantive way since
the device last saw it is `stale_content`; for a deleted card `applied_to_deleted`. When events from two devices overlap in time the server replays the card's log in time order and answers `merged: true`;
the returned `cards` hold the final state to adopt (compare `rev`). An event dated more than 5 minutes in the future is recorded at the server's now.

## Read side

| Method and path | Query | Success |
| --- | --- | --- |
| `GET recall/today/` | `tz?` | 200 `{server_time, local_date, tz, mode: "normal"\|"catchup"\|"vacation", counts: {new, learning, due}, queue_size, deferred, days_to_clear, est_minutes, next_due_at, new_available, limits: {new_per_day, reviews_per_day, new_done, reviews_done}, catchup: {active, due, oldest_overdue_days}, vacation_until, streak, tiles: [{subject_key, total, kinds}], forgotten: [...], exam: null}`. A card due exactly at the end of the study day is due tomorrow |
| `GET recall/queue/` | `source=today\|chapter\|deck\|forgotten\|quick\|catchup\|cram\|review_ahead (default today)`, `chapter_id`, `deck_id`, `kind`, `tier`, `limit<=50 (20)`, `exclude` (comma separated card ids), `extra<=100` ("do 20 more"), `tz` | 200 `{source, server_time, cards: [QueueCard + memory]}`; `QueueCard`: `{id, rev, item_id, item_version_id, kind, ordinal, front_md, back_md, state, badges, importance, chapter, previews: {"1".."4": label}, preview_days, source}`. `quick` and `cram` answer 422 `not_in_this_release` |
| `GET recall/pack/` | `limit<=1000` (capped by the plan and `RECALL_PACK_MAX`) | 200 `{pack_id, generated_at, server_time, expires_at, settings, weights, scheduler_version, cards: [QueueCard + memory], counters: {new_done_today, reviews_done_today, local_date}}` |
| `GET recall/forgotten/` | `subject_key`, `limit<=50 (20)`, `window_days<=90 (30)` | 200 `{items: [{card_id, kind, front_md, back_md, subject_key, chapter_id, importance, score, lapses, agains, last_again_at}]}` |
| `GET recall/stats/summary/`, `retention/` | `range=7d\|30d\|90d\|1y (30d)`, `tz` | 200 report with an `ETag` and `Cache-Control: private, no-cache`; 304 when `If-None-Match` matches |
| `GET recall/stats/forecast/` | `days<=90 (30)`, `tz` | as above |
| `GET recall/stats/chapters/` | `tz` | as above |
| `GET recall/settings/` | | 200 settings: `{desired_retention, new_per_day, reviews_per_day, learning_steps_min, relearning_steps_min, max_interval_days, leech_threshold, day_start_hour, tz, bury_siblings, interleave, catchup_mode, pause_new_in_catchup, exam_horizon, recall_counts_as_revision, gestures, show_intervals, quick_minutes_per_day, improve_scheduler_consent, vacation_until, consent_at, scheduler_version}` |
| `PUT recall/settings/` | any subset of the keys above (partial) | 200 settings | 400 for an unknown key; 422 `invalid_setting` details `{errors:[{field, code, message}]}` |

GETs never write. `desired_retention` is 0.80 to 0.97, `new_per_day` 0 to 100, `reviews_per_day` 20 to 500, `day_start_hour` 0 to 6.

## Platform decks

`Deck`: `{id, slug, title, description, course_id, level_id, subject_key, subject_name, chapter_id, chapter_name, version_no, item_count, card_count, tiers, published_at, changelog_md,
subscription: {id, status, version_no, newer_versions, subscribed_at, min_importance}|null}`.

| Method and path | Body or query | Success | Errors |
| --- | --- | --- | --- |
| `GET recall/decks/library/` | `?course&level&subject_key&chapter_id&tier&cursor&limit<=50` | 200 `{items: Deck[], next_cursor}` (live decks only) | 400 |
| `GET recall/decks/subscribed/` | | 200 `{items: Deck[]}` | |
| `GET recall/decks/{id}/` | | 200 `{deck: Deck, items: [{item_id, kind, importance, position, preview, chapter_name}]}` | 404 `deck_not_found` |
| `POST recall/decks/{id}/subscribe/` | `{follow_updates? (true), unlock_mode? ("with_coverage"\|"all"), min_importance? ("bullet")}` | 201 (200 when already subscribed) `{created, cards_created, cards_restored, deck}` | 404 `deck_not_found`; 422 `deck_too_large` details `{cards, limit}` (500); 429 `quota_exceeded` |
| `POST recall/subscriptions/{id}/unsubscribe/` | | 200 `{deck}` (idempotent; the cards stay) | 404 |
| `POST recall/subscriptions/{id}/resubscribe/` | | 201 or 200 `{created, cards_created, cards_restored, deck}` (idempotent) | 404; 422 |
| `POST recall/items/{id}/report/` | `{reason: "wrong"\|"outdated"\|"copyright"\|"other", note? (<=500)}` | 201 `{id, created: true}` (200 `created: false` when she already has an open report on the item) | 404 |

## Export and erase (never gated by the flag)

| Method and path | Query or body | Success |
| --- | --- | --- |
| `GET recall/export/` | | 200 JSON of everything the student owns in recall (cards, items and versions, review log, sessions, settings, subscriptions, reports), `Content-Disposition: attachment; filename="recall-export.json"` |
| `GET recall/export/cards.csv` | `cursor?`, `limit<=100000?` | streamed `text/csv`, `Cache-Control: no-store`; the last line is `#complete,<rows>` or `#next,<cursor>` (call again with the cursor) |
| `GET recall/export/reviews.csv` | as `cards.csv` | as `cards.csv`; the review log without card text |
| `POST recall/erase/` | `{confirm: "ERASE"}` | 200 `{deleted: {reviewlog, scheduleevents, sessions, cards, subscriptions, item_versions, items, decks, daily_rollups, chapter_rollups, settings, params, quota, reports}}` (row counts): every recall row of the student is deleted, including the partitioned review log; nothing is kept. A wrong `confirm` word is 400 |

## Notes for the web

- Every screen sends `tz` (the IANA zone) to `today`, `queue` and `stats`; the day starts at `day_start_hour` (default 4) in that zone.
- Keep `server_time` from each answer; compare it with the device clock before trusting local due times.
- Never log or track card text, deck titles or ids: `modules/recall/lib/analytics.ts` has the allow-list.
