# F-03 Smart Notes, release R1 (typed notes): rollout

What ships in the API: shared foundations (`core/richtext.py`, `core/jobs.py` and the `run_worker` command, `modules/media`, stable-key selectors in `syllabus`, display fields in `coverage`) and the `notes` module (`apps/api/modules/notes`). The web side is `apps/web/src/modules/notes`. The endpoint shapes are in `docs/F-03-API-CONTRACT.md`. PDF, highlights, OCR, AI summaries and sharing are R2 and later; nothing here depends on them.

Do the parts in order. Part A is the same code hygiene as `docs/F-02-ROLLOUT.md` part A, plus one extra: run `pytest` once against Postgres before merging (`DATABASE_URL=postgres://...`). The quota concurrency tests (`modules/notes/tests/test_concurrency.py`) and the row level security checks only run there; on SQLite they skip.

## A. Code changes

- `diff-match-patch` is a new dependency (`apps/api/requirements.txt`): the 3-way merge of two devices' edits uses it. `pip install -r requirements.txt`.
- `ruff check . && ruff format --check . && pytest` must be green in `apps/api`.

## B. API environment (Vercel, project `arthacommerce-api`)

| Name | Value |
| --- | --- |
| `NOTES_TICK_SECRET` | a long random value (`openssl rand -hex 32`). Authenticates the cron tick. Empty means the tick refuses every caller, which is safe but means no trash purge |
| `CRON_SECRET` | the same value. Vercel Cron sends it as `Authorization: Bearer <CRON_SECRET>`, which the tick accepts |
| `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL` | already set for avatars. Needed for the image bucket |
| `POSTHOG_API_KEY` | already set. Without it the `notes` flag is not checked on the API and notes stay on |

New throttle rates ship in `config/settings.py`: `notes_read` 300 per minute, `notes_write` 600 per minute, `notes_search` 60 per minute, `notes_account` 6 per hour; the media endpoints have their own (`media_upload`, `media_read`). Cost-bearing limits (notes, tags, storage) are database quotas, never throttles.

## C. Database migration (once per environment, from your computer)

1. `cd apps/api`, export `DJANGO_SECRET_KEY` and `DIRECT_DATABASE_URL`.
2. `python manage.py migrate`. Order: `core.0001` (the `core_job` queue), `media.0001` (`media_attachment`), `coverage.0005` (adds `notes_count` and `has_summary` to chapter progress, display only), `notes.0001` (quota plans and usage, settings, tags, notes, versions, note images, item tags) and `notes.0002_seed_free_plan` (inserts the `free` plan: 2000 notes, 100,000 characters a note, 200 tags, 500 MB). Every new table gets Row Level Security from the post-migrate hook.
3. Create the storage bucket once: `python manage.py ensure_notes_buckets` (private bucket `notes-private`; safe to repeat).
4. Deploy the API. There is nothing to back-fill.

Plan limits live in the `notes_quotaplan` row `free` (Django admin, **Quota plans**). A change takes effect on the next request. A missing row falls back to the same numbers in code, never to "unlimited".

## D. The cron tick

Notes needs a small periodic job: it purges notes that were in the trash for 30 days (and queues their image files for deletion), thins old versions (one autosave a day after the first 24 hours, 90 days), recomputes usage counters and logs any drift, and releases uploads that were never completed.

1. Add to `apps/api/vercel.json` (Vercel Cron works on every plan, but the free plan allows only daily schedules; use `0 3 * * *` there):
   ```json
   "crons": [{ "path": "/api/v1/notes/internal/tick/", "schedule": "*/15 * * * *" }]
   ```
2. Any other scheduler works: `POST` the same URL with header `X-Notes-Tick-Secret: <NOTES_TICK_SECRET>`.
3. A run is bounded to 20 seconds and safe to repeat or overlap. The daily chains (thinning, reconcile) start once per day and continue in batches of 200 on the following ticks.
4. Heavy work (OCR, PDF inspection, exports) arrives with R2 and runs in the always-on worker: `python manage.py run_worker` (`--once` drains and exits). R1 does not need a worker.

## E. PostHog

Create the flag `notes` (percentage rollout, start with your own account). Off means every notes endpoint answers 403 `feature_disabled` and the web shows "not available yet"; image uploads of kind `note_image` are blocked by the same flag. These stay open with the flag off, so a student can always take their data out: `GET /api/v1/notes/export/`, `DELETE /api/v1/notes/` and the cron tick. Create `notes_pdf` later (R2); until then `search/?scope=pdf` answers 403 when it is off.

Coverage shows the number of notes on each chapter row from the `notes_chapter_counts_changed` event. This is display only: notes never change a chapter's coverage percentage or start date.

## F. Web

1. No new variables. Redeploy after the API is live.
2. Check as a signed-in student with the flag on: create a note in a chapter, edit it on two tabs (a clean merge keeps both edits, an overlapping edit shows the conflict sheet), add an image, tag it, trash and restore it, open its history and restore a version, search for a word from its body, switch the syllabus scheme in admin and confirm the note still shows under the same chapter, and check Settings, Usage.

## G. Support and operations

- **Quota plans** are editable in the admin. **Notes** and **Quota usage** are read-only there, and the admin shows no note text.
- Usage counters are kept by atomic conditional updates. `python manage.py reconcile_notes_usage` recomputes them from the rows and prints how many had drifted (should be 0). The nightly job does the same and logs the count.
- `python manage.py rebuild_note_search` rewrites every search vector (after a language configuration change or a restore from backup). PostgreSQL only; on SQLite search falls back to a substring match.
- A student's data export and delete: `GET /api/v1/notes/export/` and `DELETE /api/v1/notes/` (queues their image files; the objects leave storage within the next ticks). Account deletion calls the same eraser through `core.registry`.
- Failed jobs stay in `core_job` with `status=failed` and the error text (never the payload) for seven days.

## H. Rollback

Turn the `notes` flag off: the web hides notes and the API refuses them, while data stays intact. Migrations are additive; to remove the feature entirely drop the `notes_*` tables, `media_attachment` and `core_job` (nothing else references them) and revert `coverage.0005` (two display columns).
