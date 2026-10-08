# F-03 Smart Notes, releases R1 (typed notes) and R2 (PDF reader, marks, OCR, export): rollout

R1 is parts A to H below. **R2 is the part headed R2 at the end of this file** (migrations 0003 to 0005, the worker, flag `notes_pdf`, capacity runbook). Do R1 first if the environment has never had notes.

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

**Crons (R2 note).** From R2 the tick should run **every 5 minutes**: it expires upload reservations (a PDF upload that was never completed holds quota and a document slot for 30 minutes), so a 15-minute or daily schedule makes a failed upload block the quota for much longer. Call `POST /api/v1/notes/internal/tick/` with the header `X-Notes-Tick-Secret: <NOTES_TICK_SECRET>` from a Render Cron Job or a Zoho Catalyst Cron on `*/5 * * * *`. The Vercel `crons` entry below is now optional: use it only if you stay on Vercel, where the free plan allows daily schedules only. The tick never runs heavy jobs (virus scan, PDF inspection, text extraction, OCR, export); those wait for the always-on worker.

1. Add to `apps/api/vercel.json` (Vercel Cron works on every plan, but the free plan allows only daily schedules; use `0 3 * * *` there):
   ```json
   "crons": [{ "path": "/api/v1/notes/internal/tick/", "schedule": "*/15 * * * *" }]
   ```
2. Any other scheduler works: `POST` the same URL with header `X-Notes-Tick-Secret: <NOTES_TICK_SECRET>`.
3. A run is bounded to 20 seconds and safe to repeat or overlap. The daily chains (thinning, reconcile) start once per day and continue in batches of 200 on the following ticks.
4. Heavy work (OCR, PDF inspection, exports) arrives with R2 and runs in the always-on worker: `python manage.py run_worker` (`--once` drains and exits). R1 does not need a worker.

## E. PostHog

Create the flag `notes` (percentage rollout, start with your own account). Off means every notes endpoint answers 403 `feature_disabled` and the web shows "not available yet"; image uploads of kind `note_image` are blocked by the same flag. These stay open with the flag off, so a student can always take their data out: `GET /api/v1/notes/export/`, `DELETE /api/v1/notes/` and the cron tick. Create `notes_pdf` later (R2); until then `search/?scope=pdf` answers 403 when it is off.

### Flag behaviour (decision)

The `notes` and `notes_pdf` flags **fail open**: only an explicit `false` from PostHog turns a feature off. No `POSTHOG_API_KEY`, a flag that does not exist yet, a timeout or a PostHog outage all mean **on**. This is `core.feature_flags.flag_enabled(name, user_id)` with its default `strict=False`, the same rule as the web hook `useFeatureFlag`, so web and API always agree.

Why: notes hold a student's own work. A flag outage must never lock a student out of their notes or their reading, and local development and CI have no PostHog key. The flag is a rollout switch, not a safety control. The things that must never happen by accident are protected elsewhere: quotas are database facts, uploads are scanned, data export and erasure ignore the flag.

The cost of fail open: if you create `notes_pdf` with a 0% rollout and PostHog is unreachable at that moment, students are let in for the length of the outage (the API caches answers for 60 seconds). The alternative is `strict=True` (fail closed): only an explicit `true` counts, so a missing key or an outage means off. It is right for things like sending notifications and wrong for reading a student's own files. If you want a closed launch of `notes_pdf` (for example while ClamAV is not yet live), change `flag_required(PDF_FLAG, ...)` and the `flag` check in `media.create_upload` to pass `strict=True` for that flag; nothing else needs to change. Until then do not enable `notes_pdf` in production before `MEDIA_SCANNER=clamd` is set (R2 section in `docs/SETUP.md`).

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


---

# R2: PDF reader, marks, search, OCR and export (flag `notes_pdf`)

What ships: documents (upload, inspect, extract, trash, page ranges), the pdf.js reader (`/app/notes/pdf/$docId`), the library (`/app/notes/library`), sidecar marks (highlight, underline, area, ink, text box, sticky, bookmark) with offline sync, in-document and library PDF search, Tesseract OCR (English, English + Hindi), flattened PDF export with an appendix, and the notes archive. R3 items (AI OCR, AI summaries, share links, recall cards) answer 403 `feature_disabled`, or 503 `recall_unavailable` for cards, until their providers exist. Endpoint shapes: `docs/F-03-API-CONTRACT.md`. Worker: `docs/F-03-WORKER.md`.

## R2-A. What must exist before the flag is on

| Piece | Why |
| --- | --- |
| Worker container (Render Background Worker from `render.yaml`, 2 vCPU / 4 GB) | scan, inspect, extract, OCR and export run only there; without it uploads stay "inspecting" |
| ClamAV in that container, `MEDIA_SCANNER=clamd` | with `null` every file is clean at once: development only |
| Tick every 5 minutes | expires abandoned uploads (30 min) and exports (7 days), purges, reconciles usage |
| Storage bucket `notes-private` | `python manage.py ensure_notes_buckets` |
| Migrations 0003 to 0005 | below |

## R2-B. Environment

API project (Vercel): no new variables. Worker (Render): `DJANGO_SECRET_KEY`, `DATABASE_URL`, `DIRECT_DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `SENTRY_DSN`, `MEDIA_SCANNER=clamd`, `NOTES_TICK_SECRET`; optional `WORKER_TYPE_LIMITS`, `WORKER_SHUTDOWN_GRACE_SECONDS`, `WORKER_HEARTBEAT_SECONDS`, `WORKER_FONTS_DIR`, `WORKER_LIVENESS_FILE`. `render.yaml` and `apps/api/.env.example` list them; `docs/SETUP.md` has the table.

## R2-C. Migrations (from your computer, `DIRECT_DATABASE_URL`)

`python manage.py migrate` applies `notes.0003_ownership_keys` (composite ownership foreign keys, Postgres only), `0004_documents` (creates the `btree_gin` and `btree_gist` extensions, `FileContent`, `FilePage`, documents, chapters, export jobs) and `0005_annotations_and_tags`. All additive. Supabase allows both extensions; confirm with `select extname from pg_extension where extname like 'btree%'`. New tables get Row Level Security from the post-migrate hook. Then `python manage.py ensure_notes_buckets`. Optional: `python manage.py reextract_content` re-reads stored text after an extractor change.

## R2-D. Order of the first launch

1. Deploy the worker; open its logs and confirm it started and reports healthy (`docs/F-03-WORKER.md` section 5).
2. Run the migrations, create the bucket, deploy the API and the web.
3. Schedule the tick every 5 minutes (part D, Crons note).
4. Create the PostHog flag `notes_pdf` at 0% plus your own account. Do not raise it before `MEDIA_SCANNER=clamd` is confirmed (upload the harmless EICAR test file: it must end `rejected`).
5. Check as a signed-in student: upload a text PDF, a scanned PDF and a password-protected PDF; mark, reload offline, edit on two tabs; search in the file and in the library; run OCR on the scan; export; delete all notes in Settings.
6. Raise the percentage in steps.

## R2-E. Capacity runbook

Run locally (needs Postgres and the API virtualenv):

```bash
DATABASE_URL=postgres://user:pass@localhost:5432/e2e python scripts/e2e/notes-r2/run.py        # functional check, exits 1 on a failure
DATABASE_URL=postgres://user:pass@localhost:5432/e2e python scripts/e2e/notes-r2/capacity.py   # indicative numbers
```

Baseline on one cloud CPU with the Django dev server (compare runs, do not treat as a production forecast): a 1,000-page PDF inspected in 2.9 s and fully searchable in 3.8 s; a 50 MB file ready 3.7 s after upload; in-document search over 1,000 pages p50 88 ms, p95 108 ms; library PDF search p50 80 ms, p95 98 ms; 8 writers each sending 25 marks to one document: 200 of 200 accepted in 1.1 s, batch p50 501 ms, `change_seq` gap free. Search endpoints are throttled at 60 a minute per student, so a search load test must use several users.

Manual (cannot be run from the build environment):

| Check | How | Pass |
| --- | --- | --- |
| Device matrix | Chrome and Safari on an Android phone, an iPhone, an iPad with Apple Pencil and a laptop; open a 200-page PDF, highlight by touch and by pen, pinch zoom, go offline and back | marks land under the finger or pen, the stylus draws without scrolling, queued marks sync, no horizontal scroll at 320 px |
| 50 MB and 1,000 pages on the real worker | upload both on the Render worker; watch memory in the Render dashboard | ready within a minute, memory under 80%, no restart |
| Scanned 1,000-page OCR | request OCR on a large scan | chunks of 10 pages, resumes after a worker restart, charged once |
| ClamAV | upload EICAR, and a 50 MB clean file | EICAR `rejected`, the clean file passes |
| Write load on the real API | run the writer from `capacity.py` against staging with 50 users | no 5xx, p95 under 1 s |
| Search p95 on staging | 1,000 PDFs, 100 searches a minute spread over 5 users | p95 under 500 ms |
| Accessibility | keyboard-only reader, screen reader on the library and mark list, 200% zoom, the four themes | no blocked path |

## R2-F. Operations

- Failed jobs stay in `core_job` with the error text for seven days. A job the queue closes after repeated worker silence now fails its OCR content or export and refunds unspent pages (`core.jobs.register_gave_up_handler`).
- Quota plan `free` has the R2 limits (documents, file size, pages, marks per document, OCR pages and exports per month, offline documents). Change them in the admin; monthly counters reset on the first of the month in India time.
- One recall card id is cached per mark (the first kind made). Another kind is created through the provider's idempotent `(student, mark, kind)` call but is not remembered on the mark.
- Q-F03-3 (counsel): storing student PDFs, and the Devanagari export fonts (Noto, OFL), need written sign-off before a public launch.

## R2-G. Rollback

Turn `notes_pdf` off: the reader, library and PDF endpoints answer 403 and the web hides them; typed notes are untouched; data export and delete-all stay open. Stop the worker if it misbehaves (jobs wait in `core_job`). Migrations are additive; to remove R2 drop the document, annotation and content tables and migrations 0003 to 0005.


# R3: AI help, Replace edition, Unlock for search, resumable upload (flag `notes_ai`)

What ships (migrations 0006 to 0009): an AI exam summary of a chapter (draft first, a note only when accepted), AI "Improve this page" for scanned pages, Replace edition with re-anchoring, Unlock for search and resumable upload of big PDFs. **Not built, on purpose:** share links (`notes_share`, parked, see `docs/BUILD-TRACKER.md` P1), offline packs and the recall bridge (blocked on F-15 and the owner). AI is private per student: nothing is shared, so the counsel review (Q-F03-3) stays deferred. Endpoint shapes: `docs/F-03-API-CONTRACT.md` (R3). Worker: `docs/F-03-WORKER.md` (R3 additions).

## R3-A. Fail-closed gates (all must be true for any AI call)

1. PostHog flag `notes_ai` is on for the student. **Fail closed**: a missing key, an unknown flag or an outage means off. Create it at **0%**.
2. `GEMINI_API_KEY` is set (API and worker).
3. `GEMINI_DATA_TIER=paid`. Set it only when the key's Google Cloud project has an active billing account (Gemini API "Paid Services": Google does not use the content to improve its products). A Gemini or Google AI Pro subscription for a personal account is a consumer product and does **not** count. Until you confirm this it stays `unconfirmed` and AI refuses.
4. `NOTES_AI_CONSENT_APPROVED` equals the consent version in `apps/api/modules/notes/domain/ai_consent.py` (`VERSION`). The consent wording is a **draft marked [VERIFY]**: read it (it is what students agree to, and says what is sent to Google), have it checked, and only then copy the version string into the variable. Changing the wording means a new version, and every student is asked again.
5. The kill switch of the feature is on (`NOTES_AI_SUMMARY_ENABLED`, `NOTES_AI_OCR_ENABLED`) and `NOTES_AI_DAILY_BUDGET_PAISE` is above 0 and not spent today. The budget is shared by all students (India day); when it runs out new requests answer 503 `ai_budget_exhausted` and nothing is charged.
6. The student agreed to the current consent text in the app (Settings, Notes, AI help; or the first time they ask).

Per student limits are plan columns in the admin (`ai_summaries_per_month`, `ai_ocr_pages_per_month`; the free plan has 0 pages, set them on the plan you want to offer). They are charged atomically before the job is queued and refunded when the job fails, is cancelled, or a page could not be read.

## R3-B. Environment

API **and** worker: `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_DATA_TIER`, `NOTES_AI_CONSENT_APPROVED`, `NOTES_AI_SUMMARY_ENABLED`, `NOTES_AI_OCR_ENABLED`, `NOTES_AI_DAILY_BUDGET_PAISE`, `GEMINI_PRICE_IN_PAISE_PER_M`, `GEMINI_PRICE_OUT_PAISE_PER_M`, `NOTES_UNLOCK_FERNET_KEYS`. API only: `NOTES_S3_ENDPOINT`, `NOTES_S3_REGION`, `NOTES_S3_ACCESS_KEY_ID`, `NOTES_S3_SECRET_ACCESS_KEY`. Gemini is called only from the API and the worker, never from the browser. Generate the Fernet key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`; to rotate, put the new key first and keep the old one after a comma for an hour. The price table is an assumption to re-check against Google's price page; `cost_paise` in the ledger (`notes_aijob`) is computed from it.

## R3-C. Migrations (from your computer, `DIRECT_DATABASE_URL`)

`python manage.py migrate` applies 0006 (AI ledger, consent, monthly counters), 0007 (replace edition: document columns and `notes_reanchoritem`), 0008 (unlock columns) and 0009 (resumable upload id). All are additive. RLS is switched on for the new tables automatically.

## R3-D. Order of the first launch

1. Deploy the API with the new migrations. With `notes_ai` at 0% nothing changes for students.
2. Set the worker secrets and deploy it (`fly deploy` from `apps/api`; `docs/F-03-WORKER.md`). Check `fly logs` shows the new job types registered.
3. Do the gates above one by one (billing account, wording approved, budget, Fernet key). Leave resumable upload for step 6.
4. Raise `notes_ai` to your own account, then a handful of testers. Quick smoke test: agree to the notice; ask for a summary on a chapter with a few notes; open a scanned PDF page and tap "Improve this page"; replace an edition of a test PDF and open "Needs attention"; unlock a password-protected PDF and search it.
5. Watch the daily budget (`notes_aijob.cost_paise` summed per day) and the worker memory for a day, then widen the percentage.
6. Resumable upload last. In Supabase, Project settings, Storage, create an S3 access key, set the four `NOTES_S3_*` variables, and in the bucket's CORS (Storage settings) allow `PUT` from your web origin. Upload one PDF over 16 MiB with the network throttled and interrupted once. The S3 signing is tested against AWS's published example, but this exact Supabase endpoint is **[VERIFY]**: if it fails, unset the variables and every upload is a single PUT again.

## R3-E. Operations and rollback

- Kill switches without a deploy: `notes_ai` to 0% (everything above answers 403), or `NOTES_AI_SUMMARY_ENABLED=false` / `NOTES_AI_OCR_ENABLED=false` (503 `ai_unavailable`, queued jobs refund). Withdrawing consent deletes the student's unsaved drafts and cancels their queued jobs.
- Replace edition never changes or deletes the old document. If a re-anchor misbehaves, the student still has the old edition with every mark; a failed re-anchor says so on the new edition.
- Unlock for search stores no password and no unprotected file. If `NOTES_UNLOCK_FERNET_KEYS` is unset the button answers 503 `unlock_unavailable`.
- Data rights: `DELETE /notes/` and the export include the AI ledger and the replace-edition items; erase removes them.
