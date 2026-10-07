# Prompt: build F-03 R2 (PDF library, reader, annotations, OCR, export) end to end

You are continuing ArthaCommerce feature F-03 "Smart Notes" in the repo at the linked computer folder `ArthaCommerce`
(`$HOME/mnt/ArthaCommerce` via `device_bash`). R1 (typed notes) is built, pushed and migrated. Build **R2** now, API and web,
production grade. Do not git commit or push unless I ask. Ask me only if blocked; otherwise decide, state the decision, continue.

## 0. Before anything else
1. Run the git-lock cleanup from CLAUDE.md. Read `CLAUDE.md`, then these skills in `.claude/skills/`: `new-feature-module`,
   `django-backend-layers`, `frontend-architecture`, `design-system-usage`, `ui-quality-checklist`, `ux-aha-moments`,
   `clean-code-review`, `dev-workflow`.
2. Read in full: `docs/product/prd/F-03-notes-and-pdf-editor.md`, `docs/product/erd/F-03-notes-and-pdf-editor.md`,
   `docs/F-03-ROLLOUT.md`, `docs/F-03-API-CONTRACT.md`, `docs/F-03-CATALYST-FIT.md` (if present).
3. Study what R1 left you: `apps/api/core/{jobs,richtext,events,registry,storage,feature_flags,permissions}.py`,
   `apps/api/modules/{media,notes,syllabus,coverage}`, `apps/web/src/modules/notes`, `apps/web/src/lib/{offline-queue,richtext,kv-store}`,
   `packages/design-system` (SyncChip, UsageBar, Sheet, FilterChip). Reuse; extend; never duplicate.
4. Check the machine can run tests (python venv + Postgres per `apps/api` conventions, `pnpm`). The R1 agents used a Linux mirror
   because the Mac `node_modules` are darwin builds; do the same if needed.

## 1. Scope: release R2, flag `notes_pdf`
Everything in PRD sections 4.1 items 6 to 12 and functional requirement groups A, B, C, F (PDF search), G, H, I, K (annotation
offline), M (platform) for R2, plus PRD 5.5 edge cases. R3 items (AI summary, AI OCR, share links, replace edition, offline PDF packs,
resumable upload, unlock-for-search) stay behind their flags as stubs that return 403 `feature_disabled`, nothing user-visible.
Slices to follow are PRD 13.2 numbers 9 to 20 (below). Each slice ships green and flag-gated.

## 2. Decisions already made (do not reopen)
- **Worker host: container host, not Catalyst.** Catalyst AppSail has a 30 s request limit, no always-on instance and 2 GB RAM, and
  Catalyst Functions cannot run Tesseract, so it cannot be the PDF worker. Target **Render "Background Worker" (Docker)**, Singapore
  region for Indian students, instance with at least 2 GB RAM for Tesseract + pypdfium2 + ClamAV (verify current plan sizes and
  prices on render.com before telling me the monthly cost). Keep the worker host-agnostic: one Dockerfile, env vars only, so
  Fly.io or Railway is a config change.
  Deliver: `apps/api/worker/Dockerfile` (python slim + Tesseract 5 `eng` `hin`, ClamAV with clamd and freshclam, pypdfium2, pikepdf,
  pypdf, reportlab, Pillow, Noto Sans and Noto Sans Devanagari fonts, check each licence), `render.yaml` blueprint for the worker,
  `docker-compose.worker.yml` for local dev, and `docs/F-03-WORKER.md` (build, env vars, deploy on Render, scaling, health, logs,
  cost, how to swap hosts). The worker runs `python manage.py run_worker` (already in `core/jobs.py`); extend it with heartbeats,
  graceful shutdown, per-type concurrency limits and visibility-timeout re-claim of crashed jobs.
- **Scheduling:** the light tick `POST /api/v1/notes/internal/tick/` should be called every 5 minutes. Document two options in
  `docs/F-03-WORKER.md`: Render Cron Job, or Zoho Catalyst Cron Job Scheduling calling the URL with the `NOTES_TICK_SECRET`
  header. Do not build anything Catalyst-specific in code.
- **Storage:** stay on Supabase Storage through `modules/media` (bucket `notes-private`, quarantine prefix, signed URLs). No Stratus.
- **Viewer:** pdf.js behind the `PdfEngine` adapter in `notes/lib/pdf-engine` (ESLint boundary: only that folder imports
  `pdfjs-dist`), own annotation layer, per ERD section 0. Skip the 2-day EmbedPDF spike unless pdf.js fails the device checks
  (then write a short findings note and ask me).
- **Recall bridge (F-15 does not exist):** define the port `recall.services.create_card_from_source` and `cards_for_source` as a
  registry in `core` (provider registers itself later) with a null adapter. The "Card" button and badges are hidden until a provider
  exists; endpoint `POST annotations/{id}/card/` returns 503 `recall_unavailable`. Test both states.
- **Platform documents (`open_platform_document`)** are built as a service plus tests; no UI beyond opening them in the reader.
- **Quotas and limits:** PRD 8.5 `free` plan; atomic conditional updates as ERD 2.11.

## 3. R1 follow-ups to do FIRST (small PRs inside this work)
1. **Offline note creation without the `/new` limbo.** Fix by making the client own the id: the note's `id` is a client-generated
   UUID (the existing `client_id` becomes the primary key on create; keep `client_id` for idempotency compatibility if migration
   cost is high, but the create call must accept and honour a client `id`). `PUT notes/{id}/` upserts idempotently (same id, same
   payload returns the stored row; id owned by another user returns 404, never leaks). Web: on "New note" generate the UUID, write
   the draft to the local store and navigate immediately to `/app/notes/n/$noteId`; the editor works offline, the queue creates the
   row on reconnect, tags can be attached before first save (queued after create). Remove the "stays on /new" behaviour and the
   "new notes cannot take tags" limitation. Update the API contract doc, tests (replay twice, two devices, cross-user id collision,
   offline create then edit then replay order) and web tests.
2. **Ownership hardening (deferred from R1):** add composite foreign keys `(tag_id, user_id)`, `(note_id, user_id)`,
   `(annotation_id, user_id)`, `(document_id, user_id)` on `ItemTag`, and owner-consistent keys on `NoteImage` and `NoteVersion`,
   with unique `(id, user_id)` on parents, via additive migrations (`NOT VALID` then `VALIDATE`; Postgres only, SQLite keeps the
   service check). Add Postgres tests that a cross-user link is rejected by the database itself. Complete `ItemTag` with the
   `annotation_id` and `document_id` columns and the `num_nonnulls = 1` check when the annotation and document tables arrive.
3. Resolve the R1 open items from the report: decide and document the `notes` flag fail-open behaviour; add a `crons` note (not
   code) for the tick; fix the pre-existing flaky quiet-hours notification test by freezing time if it is trivial.

## 4. R2 build order (PRD 13.2 slices 9 to 20)
**API (`apps/api/modules/notes`, `modules/media`, worker):**
9. `media` kinds `note_pdf` (application/pdf only, magic bytes `%PDF-`, no polyglot, plan `max_file_mb`), `note_image` scan on,
   `note_export`; bucket `notes-private` via `ensure_notes_buckets`; scan then inspect job chain through `core.jobs`; worker
   `inspect` (pikepdf validation, encryption detection, page count and boxes, rotation, outline, permissions, JS flag, SHA-256 from
   stored bytes, find-or-create `filecontent`, first-page cover thumbnail, scanned detection by sampling 20 pages).
10. Document schema and endpoints (migration 0003): reserve with atomic quota, complete, library list and filters, detail with signed
    URL (4 h), PATCH, trash and restore, page ranges with the gist exclusion constraint, progress, reservation expiry in the tick,
    duplicate detection by hash, platform documents. Error codes per PRD 9.1 (413, 415, 422, 429 with details).
11. Derived content: `filecontent`, `filepage` with tsvector (`english` or `simple` when Devanagari over 30 percent), native text
    extraction job (chunks of 20 pages), in-document and global PDF search endpoints, `GET pages/text`.
12. Annotations (migration 0004): model, geometry v1 validation in `domain/geometry.py` with golden fixtures
    `geometry_cases.json` shared with a TypeScript twin, services (single, batch up to 100, delta feed with `change_seq`, tombstones),
    conflict rules ERD 3.6 (field compare-and-set, 3-way text merge, geometry last-write, edit beats delete), anchoring domain
    (`anchoring.py`), chapter inheritance from page ranges, tags on marks and documents, counts into `counts_for_chapters`,
    aggregate and search extended with marks, `notes_chapter_counts_changed` emitted for highlights.
17. OCR: Tesseract chunks of 10 pages, progressive, resumable, content-level dedupe, monthly OCR page charge and refund,
    `words` boxes in the normalised frame, `eng` and opt-in `eng+hin`.
18. Flattened export job (pikepdf overlay, `/Rotate` aware, Noto fonts) and "Download my notes" zip; export quota; 24 h links.
19. Recall port and platform document service (section 2).
Also: `delete_all_for_user` and `export_for_user` extended to documents, marks, files (objects purged within 24 h);
RLS tests automatically cover new tables; throttle scopes `notes_upload`, `notes_export`.

**Web (`apps/web/src/modules/notes`, `packages/design-system`):**
13. `lib/pdf-engine` adapter (pdfjs worker, range requests with signed-URL refresh, text layer, OCR text layer), reader shell,
    virtualised continuous scroll (about 5 canvases), fit-width, pinch and double-tap zoom, resume page and zoom, distraction-free
    chrome, outline, scrubber, page tone, in-document search, large-document mode, password prompt (browser only), per-page error state.
    Lazy-load the reader chunk from `app.notes.pdf.$docId` only.
14. Annotation layer: highlight, underline, area, sticky, bookmark; `SelectionToolbar`, `FloatingToolbar`, `SwatchPicker` (colour
    legend with student-defined meanings), annotation list sheet and side panel (also the screen-reader alternative), edit and
    delete with 10 s undo, local-first writes and delta sync through the shared offline queue (scope per document), conflict sheet
    reuse, tags, chapter chips, "Needs attention".
15. Pen and text box with stylus handling (stylus draws, finger scrolls unless "finger draws"), palm rejection, RDP simplification.
16. Library screens `/app/notes/library`, upload flow with every failure state (reserve, progress chip that survives navigation,
    cancel, retry, quota sheet showing five largest documents, duplicate prompt, rejected reasons), `FileDropzone`, document card,
    metadata edit, trash, scanned banner with OCR estimate, OCR progress, export dialog, "Download my notes".
17-18. UI for OCR, export and global PDF search results grouped by document.
Routes: `app.notes.library`, `app.notes.pdf.$docId`, tabs `highlights|documents` on subject and chapter views now show data.
Analytics: PRD 10.1 R2 events only, no text, titles, filenames, ids or queries.

## 5. Quality bar (non-negotiable, from CLAUDE.md)
Modular with barrels; views -> services/selectors -> models; routes thin; containers vs presentational; DRY (extract a shared helper
the third time); semantic tokens only, icons from `@artha/design-system`; every screen has loading, empty, error, success states;
works in Reading, Light, Dark, System themes; WCAG 2.2 AA (keyboard path in FR-F03-71, aria-live sync, 44 px targets, reduced
motion); 320 to 1280 px with no horizontal scroll; no PII in Sentry, PostHog or logs (filenames never in storage paths).
Tests: geometry parity fixtures (Python and TypeScript), anchoring, merge convergence property tests, quota concurrency on Postgres,
exclusion constraint, delta feed monotonic `seq`, edit-beats-delete, chapter inheritance, original file hash unchanged after random
edits and export, upload pipeline with a fake storage and fake worker, worker unit tests with fixture PDFs (text, scanned,
encrypted, corrupt, 1,000 pages), component tests, flag gating, RLS. Run `pnpm check`, `pytest`, `ruff check .`, contrast check.
Capacity checks from ERD section 8 go in `docs/F-03-ROLLOUT.md` as a runbook (device matrix, 50 MB and 1,000 page files, write load
test, search p95); run what can be run locally and list the rest as manual.

## 6. Deliverables and reporting
Update `docs/F-03-ROLLOUT.md` (R2 migrations 0003 onward, flags, env vars, worker deploy, tick), `docs/F-03-API-CONTRACT.md`,
`docs/F-03-WORKER.md`, `docs/SETUP.md`, `.env.example`, and the CLAUDE.md product-status paragraph (what is implemented, flags,
routes, rollout doc). Work slice by slice and tell me when each slice is green. Final report (under 40 lines): what shipped, test
results, deviations from the ERD with reasons, manual steps for me (Render service creation, env vars, PostHog flags `notes_pdf`,
bucket creation, tick scheduler, counsel sign-off on Q-F03-3 before launch), and what remains for R3.
