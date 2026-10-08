# F-03 PDF worker: build, deploy and operate

Status: written 2026-10-08 with the R2 worker toolchain. The image has **not been built yet**: the authoring sandbox had no Docker
daemon. Run the first build locally (section 1) before the first deploy; the Python libraries, the job runtime and the tests were run.

## What it is

One always-on container that runs `python manage.py run_worker`. It claims rows from `core_job` (Postgres, `FOR UPDATE SKIP LOCKED`)
and runs the heavy F-03 jobs: `notes.inspect`, `notes.extract_text`, `notes.ocr`, `notes.export_pdf`, `notes.export_archive`, plus
`media.scan` (ClamAV). The libraries live in `apps/api/modules/notes/worker/` (database-free: paths in, frozen dataclasses out); the
job handlers that call them are glue in the notes module. Light jobs (purge, reconcile, reservations) still run from the cron tick
`POST /api/v1/notes/internal/tick/` and never need the worker.

Decision (research note `F-03-CATALYST-FIT.md`): **not Zoho Catalyst.** AppSail answers HTTP requests (30 s limit, idles out after
5 minutes, 2 GB RAM, no documented always-on instance) and Catalyst Functions cannot run Tesseract. Catalyst stays useful for
scheduling only (section 7). Target host: **Render Background Worker (Docker), Singapore**; Fly.io and Railway are a config change.

## 1. Build and run locally

```bash
cd apps/api
docker build -f worker/Dockerfile -t artha-worker .            # context is apps/api
docker run --rm -e DJANGO_SECRET_KEY=x -e DATABASE_URL=... -e SUPABASE_URL=... \
  -e SUPABASE_SERVICE_ROLE_KEY=... -e SUPABASE_JWT_SECRET=... -e MEDIA_SCANNER=null artha-worker
# or the whole local stack (Postgres + worker, ClamAV off):
docker compose -f docker-compose.worker.yml up --build
docker compose -f docker-compose.worker.yml run --rm migrate    # once, creates the tables
```

The image: Python 3.12 slim (Debian bookworm), tini as PID 1, non-root user `worker` (uid 10001), Tesseract 5 with `eng` and `hin`,
ClamAV (`clamd`, `freshclam`; signatures baked at build as a seed and refreshed in the background), pikepdf (qpdf), pypdfium2, pypdf,
uharfbuzz, fontTools, Pillow, reportlab (tests only), and the Noto fonts (`apps/api/worker/FONTS.md`, SIL OFL 1.1, checksum-pinned).
The entrypoint starts clamd when `MEDIA_SCANNER=clamd` and waits until it answers before the worker starts (loading signatures takes
20 to 90 seconds and about 1 GB of RAM). PyMuPDF is deliberately absent (AGPL).

Local development without Docker: `pip install -r apps/api/worker/requirements-worker.txt`, then `python manage.py run_worker`.
Tests: `cd apps/api && pytest modules/notes/tests/worker core/tests/test_jobs.py core/tests/test_run_worker.py`.

## 2. Environment variables

All configuration is env vars (same names as the API where they overlap, see `docs/SETUP.md`).

| Variable | Needed | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false` | yes | the settings module refuses to import without a key |
| `DATABASE_URL` | yes | Supabase transaction pooler (6543), same as the API |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | yes | storage reads and writes (`notes-private`, quarantine); never in a browser |
| `SUPABASE_JWT_SECRET`, `FIELD_HASH_PEPPER` | yes | read at settings import; same values as the API |
| `MEDIA_SCANNER` | yes | `clamd` in production; `null` only in development. `CLAMD_SOCKET` defaults to `/tmp/clamd.sock` in the image |
| `SENTRY_DSN` | recommended | never receives payloads, filenames or note text (project rule) |
| `POSTHOG_API_KEY` | if flags are read | server-side flag checks |
| `WORKER_TYPE_LIMITS` | recommended | `notes.ocr=1,notes.export_pdf=1`: at most that many running **across all instances** |
| `WORKER_SHUTDOWN_GRACE_SECONDS` | optional (25) | how long a job may finish after SIGTERM; keep under the host's kill delay |
| `WORKER_HEARTBEAT_SECONDS` | optional (60) | lock refresh interval; the visibility timeout is 5 minutes |
| `WORKER_FONTS_DIR`, `WORKER_LIVENESS_FILE` | set by the image | fonts directory; file whose mtime proves the loop is alive |
| `DIRECT_DATABASE_URL` | no | only for running `migrate` from this image |

Gemini keys are not needed by the PDF jobs. `NOTES_TICK_SECRET` is needed only by whatever calls the tick (section 7).

## 3. Deploy on Render, step by step

1. Push the repo with `render.yaml` at its root. Render dashboard, **New, Blueprint**, choose the repo. It creates the service
   `artha-worker` (type Background Worker, runtime Docker, region **singapore**, plan `2c-4g`).
2. Fill the `sync: false` secrets when asked (`DJANGO_SECRET_KEY`, `DATABASE_URL`, `DIRECT_DATABASE_URL`, `SUPABASE_URL`,
   `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `FIELD_HASH_PEPPER`, `SENTRY_DSN`, `POSTHOG_API_KEY`). Render asks only at
   creation: add any later secret by hand under the service's Environment tab.
3. Wait for the first build (the Dockerfile downloads fonts and signatures) and for the deploy to turn Live. The first start takes
   one to two minutes while clamd loads.
4. Check Logs for `entrypoint: clamd is ready` and then `Ran 0 job(s)` style idle output; upload a small PDF in the app and watch
   `job type=notes.inspect status=done duration_ms=...`.
5. Make sure the API's `MEDIA_SCANNER` and the worker's agree, and that the `notes_pdf` flag is still off until the checks in
   `docs/F-03-ROLLOUT.md` pass.
6. Set up the tick (section 7).

`maxShutdownDelaySeconds: 120` gives a deploy two minutes to finish the current job; the worker's own grace is 100 s. A job still
running after that is handed back to the queue untouched (attempt refunded) and another instance picks it up.

## 4. Scaling

- **More throughput:** raise the instance count in Render (Scaling tab), or run a second service from the same image with
  `--types` (for example one dedicated to `notes.ocr`). Workers coordinate only through `core_job`.
- **Fairness and cost control:** `WORKER_TYPE_LIMITS` caps a type over all instances, enforced inside the claim transaction with
  a Postgres advisory lock per limited type, so two instances can never both take the last slot. A cap of 0 parks a type.
- **Priority:** the first chunk of every document is queued with higher `priority`, so a 600-page OCR cannot starve new uploads.
- **Memory:** one job at a time per process (ERD 6.5: 2 GB per job). Do not run several processes in one small container.
- **Crashed or evicted worker:** its job stays `running`, the lock goes stale after 5 minutes and any worker reclaims it (the
  attempt counts). Healthy long jobs refresh the lock every minute, and handlers also call `jobs.heartbeat()` between chunks.

## 5. Health, logs, monitoring

- `python manage.py worker_health` prints JSON and exits 0 or 1. Docker `HEALTHCHECK` runs it with `--require-worker --require-tools
  tesseract[,clamd]`. It reports: database reachable and latency; worker loop heartbeat age (a file touched every loop); running
  jobs and stale locks; queue depth and oldest due age **per job type**; Tesseract version and languages; clamd PING. Only the
  database, a dead worker loop and a missing required tool fail the check. Backlogs and stale locks are warnings
  (`backlog:<type>` after 15 minutes).
- Logs: one line per job, `job type=notes.ocr status=done attempts=1 duration_ms=8421`. Payloads, filenames and text are never logged.
- Alert on: `worker_health` failing, `backlog:notes.inspect` (uploads stuck in "Preparing"), `stale_running_jobs` that does not clear.

## 6. Cost

Verified 2026-10-08 from https://render.com/pricing (services and workers table) and https://render.com/docs/blueprint-spec.
Prices are monthly, in USD, taxes and bandwidth excluded.

| Render plan (`plan:` value) | CPU | RAM | Price |
| --- | --- | --- | --- |
| `0.5c-512mb` | under 1 | 512 MB | $7 |
| `1c-2g` | 1 | 2 GB | $25 |
| **`2c-4g` (blueprint default)** | 2 | 4 GB | $85 |
| `2c-8g` | 2 | 8 GB | $135 |

`1c-2g` meets the ERD's "2 GB" floor but leaves nothing for ClamAV (about 1 GB). Use it only with `MEDIA_SCANNER=null`, or with clamd on
a separate small service. With clamd inside, `2c-4g` is the sensible start. The free plan (512 MB) cannot run this image.

Other hosts, briefly (not a recommendation to switch): Fly.io `shared-cpu-2x` with 2048 MB is $13.39 a month and `performance-1x`
2 GB is $33.00, extra RAM $6 per GB per month, prices quoted for Ashburn and higher elsewhere (https://docs.fly.io/about/pricing,
read 2026-10-08; a Singapore price was not shown). Railway charges $10 per GB RAM and $20 per vCPU per month of use, Hobby $5 and Pro $20
subscription including that credit (https://docs.railway.com/reference/pricing/plans, read 2026-10-08; whether Singapore is offered
was not stated on that page). Render's page showed no per-hour rate and no cron-job price, so none is quoted.

## 7. The light tick (every 5 minutes)

`POST /api/v1/notes/internal/tick/` with header `X-Notes-Tick-Secret: <NOTES_TICK_SECRET>`. Pick one:

**A. Render Cron Job.** Uncomment the `artha-notes-tick` entry in `render.yaml`, set `API_BASE_URL` (the API's public origin) and
`NOTES_TICK_SECRET`. It reuses the worker image and posts with Python's stdlib, so no curl is needed.

**B. Zoho Catalyst Cron (Job Scheduling).** Create a cron that makes an HTTP POST to the same URL every 5 minutes with the header
above. Nothing in the repo is Catalyst specific; the Vercel free plan only allows daily crons, which is why a separate scheduler is
needed. Keep the secret in Catalyst's secret store.

The Vercel `crons` entry in `apps/api/vercel.json` may stay as a slow backup.

## 8. Swapping the host (Fly.io or Railway)

The same Dockerfile and env vars work anywhere that runs a long-lived container with at least 2 GB (4 GB with clamd).

Fly.io: the config is `apps/api/fly.toml` (no `[http_service]`, so no port and no public IP; 2 GB `shared-cpu-2x` by default, about $13.39 a month running all the time in 2026-10). Run every command from `apps/api`: `fly apps create`, `fly secrets set ...`, `fly deploy --ha=false`, `fly scale count 1`. `fly deploy` makes two machines per process unless told not to, which doubles the bill. Fly machines can only be scheduled hourly at the finest, so the 5-minute tick must come from Catalyst Cron or a Render Cron Job (section 7), not from Fly. The step-by-step with cost controls is in the F-03 rollout notes given with the release.

Railway: new service from the repo, then set `RAILWAY_DOCKERFILE_PATH=apps/api/worker/Dockerfile` and root directory `apps/api`; start
command is the image's CMD; add the env vars above; Settings, Deploy, set the region (check Singapore availability), memory limit 4 GB,
and `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=120` for the shutdown grace. No health port is needed for a worker.

These two recipes were not run; confirm the exact keys against each host's current docs when you switch.

## 9. Limits the worker enforces (ERD 6.5)

| Limit | Value | Where |
| --- | --- | --- |
| Pages per document | 1,000 (`too_many_pages`) | `inspect_pdf`, `build_flattened_pdf` (`ExportTooLarge` with a page-range hint) |
| Page size | 14,400 pt per side (`policy`; OCR and extract report `page_too_large`) | `pdfutil.MAX_PAGE_POINTS` |
| Render size | 40 million pixels (`render_too_large`) | `pdfutil.MAX_RENDER_PIXELS` |
| Header | `%PDF-` within the first 1 KB (else `type_mismatch`) | `pdfutil.is_pdf_header` |
| Memory per job | 2 GB; 1,000-page inspect and extract measured under 400 MB peak in tests | host plan |
| OCR | chunks of 10 pages, 300 dpi (200 above A3), 30 s per page, `eng` and `eng+hin` only, one thread | `ocr.py` |
| Extract | chunks of 20 pages, 60,000 characters per page | `extract.py` |
| Export | at most 1,000 pages and 3 minutes (`ExportTooLarge`); refuses copy-restricted files (`ExportNotAllowed`) | `export.py` |
| Network | none for the libraries; the worker talks to Postgres, Supabase and clamd only | host firewall |
| Scripts | never executed: qpdf and PDFium without a form or JavaScript environment; JavaScript presence is only flagged | `pdfutil.py` |

## 10. Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| Uploads stay "Preparing" | worker down or stuck. `worker_health`; look for `worker_not_alive`, `backlog:notes.inspect`. Redeploy |
| `entrypoint: clamd did not become ready in time` | not enough RAM (clamd needs about 1 GB) or signature download failed. Use `2c-4g`; check outbound access to `database.clamav.net` |
| Jobs rerun or "Gave up: no attempts left" | handler outlived the 5 minute lock without heartbeats. Handlers must call `jobs.heartbeat()` between chunks; check RAM kills in the host's events |
| `FontsMissing` | `WORKER_FONTS_DIR` wrong or the build skipped the font stage; rebuild |
| Build fails at the font stage | upstream changed a file: checksum mismatch. Review and update hashes (`worker/FONTS.md`) |
| OCR jobs never start | `WORKER_TYPE_LIMITS` is 0 for the type, or one OCR job holds the slot; check running rows in `core_job` |
| Deploy cancels a long OCR chunk | expected: it is requeued and resumed. Raise `maxShutdownDelaySeconds` if chunks regularly exceed the grace |
| `eng+hin` returns an error | the `hin` data is missing in a local install: `apt-get install tesseract-ocr-hin` (the image has it) |

## 11. Job types (OCR, export, archive)

| Type | Chunk or unit | Queue limit alias (`WORKER_TYPE_LIMITS`) | Who runs it | Payload (ids and counts only) |
| --- | --- | --- | --- | --- |
| `notes.ocr` | 10 pages, one job per chunk, chained: the next chunk is queued by the one that just finished; progress lives in `notes_filepage` rows, so a restart resumes at the next unread page | `notes.ocr=1` | worker | `{content_id, document_id, user_id, spec, lang, since, chain, charged, pages}` |
| `notes.export_pdf` | one flattened PDF (at most 1,000 pages, 3 minutes) | `notes.export_pdf=1` | worker | `{export_id}` |
| `notes.export_archive` | one zip of notes and digests (at most the plan's note count) | `notes.export_archive=1` (optional) | worker | `{export_id}` |
| `notes.expire_exports` | a batch of 200 exports past their 7 days | none | the tick (`POST /api/v1/notes/internal/tick/`) | `{}` |

Notes on `notes.ocr`:

- The first job of a request has priority 10 and key `notes.ocr:<content_id>`, so the first ten pages of every document are claimed before
  later chunks (priority 0, key `notes.ocr:<content_id>:<chain>:<first page>`) of any document.
- One OCR document per student at a time: a chunk that finds another OCR job of the same student (a different file) running puts itself back
  as a new job 20 seconds later; a second chain on the same file waits 10 seconds. `WORKER_TYPE_LIMITS=notes.ocr=1` already serialises the
  whole fleet, so with that setting the waits only matter when the cap is raised.
- A failure that is the LAST attempt marks the content `failed` and refunds the pages the student paid for and never got. A job that the
  queue closes by itself because a worker stopped answering five times (`Gave up: no attempts left...`) never reaches the handler, so it
  keeps the content `running` and the charge; the student asks again and only the missing pages are charged (`charged_pages`).
- `notes.export_pdf` fails with `error_code` `export_too_large`, `restricted`, `locked` or `failed` and refunds the monthly export it took.
  The original object is only read (range reads into a temp file, capped at the file's size).

No new environment variables: the jobs use `WORKER_FONTS_DIR` (fonts for the appendix and text marks) and `WORKER_TYPE_LIMITS` from section 2.

## 12. Checking the whole path locally

`scripts/e2e/notes-r2/run.py` starts a fake Supabase Storage, the API and this worker (`run_worker --once`) against a throwaway database and drives upload, scan, extract, search, marks, OCR, export and archive over HTTP. `capacity.py` in the same folder prints indicative timings. Both need the API virtualenv, Postgres, Tesseract and the Noto fonts (`WORKER_FONTS_DIR`). They do not replace building the Docker image: it has not been built yet, so build it once before the first deploy.

## 13. When a worker goes silent

A job whose worker stops heartbeating is handed to another worker after the visibility timeout. When it has no attempts left the queue closes it itself and calls the gave-up handler registered for its type; for OCR and exports that marks the record failed and refunds unspent pages.
