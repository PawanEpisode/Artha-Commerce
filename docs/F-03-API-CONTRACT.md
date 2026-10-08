# F-03 Smart Notes: API contract for the web (R1 typed notes, R2 PDF library, reader, annotations, OCR, export)

Backend: `apps/api/modules/notes` (R1, flag `notes`). Source of truth for behaviour: `docs/product/prd/F-03-notes-and-pdf-editor.md`
sections 6 to 9 and `docs/product/erd/F-03-notes-and-pdf-editor.md` sections 2 to 3. This file fixes the exact request and
response shapes. All paths are under `/api/v1/notes/`. Auth: `Authorization: Bearer <Supabase JWT>`. Detail routes answer 404
for anything the caller does not own. Ids are UUID strings, timestamps are ISO 8601 UTC.

## Conventions

- **Errors:** `{"error": {"code": str, "message": str, "details": any|null}}`. Codes used here: `feature_disabled` (403, flag `notes` off;
  `GET export/` and `DELETE /notes/` are never gated), `not_found` (404), `validation_error`/field map (400), `invalid_body` (422, lint),
  `unknown_chapter` (422), `quota_exceeded` (429), `note_conflict` (409), `tag_exists` (409), `rate limit` (429 `throttled`).
- **Lists:** cursor pagination `{"items": [...], "next_cursor": str|null}`; send `?cursor=<next_cursor>&limit=<1..100>`.
  Cursors are opaque.
- **Throttles (per student):** reads 300/min (`notes_read`), writes 600/min (`notes_write`), search 60/min (`notes_search`).
- **Idempotency:** every create takes a client generated `client_id` (UUID); a replay returns the stored row with 200 instead of 201.
- **Link object** (`link`), on every note, always present, all keys null when the note is "Unfiled":
  `{level_id, subject_id, subject_key, subject_name, chapter_id, chapter_key, chapter_name, topic_id, topic_key, topic_name, moved_or_removed}`.
  Grouping is by `(level_id, subject_key, chapter_key)`, so notes follow a syllabus scheme switch. `chapter_id` and the names are those of the level's
  current published scheme when the key still exists there; otherwise they are the stored ones and `moved_or_removed` is `true`.

## Shapes

`NoteSummary` (lists, search, aggregate): `{id, kind: "note"|"exam_summary", origin: "typed"|"clip"|"ai_summary"|"import", title, snippet (<= 200 chars of plain text),
body_chars, pinned, is_current_summary, link, tags: [{id, name, color_key}], rev, created_at, updated_at, deleted_at|null, purge_after|null}`

`Note` = `NoteSummary` + `{client_id, body_md, lang, clip_source: {module, ref, label}|null, image_ids: [uuid]}`

`Tag`: `{id, name, color_key: str|null, count}` (`count` = live items carrying it)

## Notes

| Method and path | Body or query | Success | Errors |
| --- | --- | --- | --- |
| `GET notes/` | `?subject=<key>&level=<uuid>&chapter=<key>&topic=<key>&tag=<uuid>&unfiled=1&kind=note&pinned=1&trashed=1&q=<text>&cursor&limit` (`subject`, `chapter`, `topic` need `level`) | 200 `{items: NoteSummary[], next_cursor}` ordered by `updated_at` desc, `id` desc (trash: `deleted_at` desc). Pinned first is the client's job (`pinned=1` filter) | 400 |
| `POST notes/` | `{client_id, title?, body_md?, chapter_id?, topic_id?, tag_ids?: uuid[]}` (R1 creates `kind=note`) | 201 `Note` (200 on replay) | 422 `invalid_body` details `{errors:[{code,message,line}]}`; 422 `unknown_chapter`; 429 `quota_exceeded` |
| `GET notes/{id}/` | | 200 `Note` (also for trashed notes) | 404 |
| `PATCH notes/{id}/` | `{base_rev (required), title?, body_md?, base_body_md?, base? {title?, pinned?, chapter_id?, topic_id?: the values you last saw, used to report `overwritten`}, chapter_id? (null unfiles), topic_id?, pinned?, tag_ids?, source?: "autosave"\|"manual" (default autosave), resolution?: "mine"\|"theirs"\|"both"}` | 200 `Note` plus `merged: bool` (true when the server 3-way merged a stale `base_rev`), `restored: bool` (the note was in the trash and this edit brought it back), `overwritten: string[]` (scalar fields where another device's newer value was replaced; needs `base` `{field: value you last saw}` in the request) | 409 `note_conflict`; 422; 429 (restoring beyond quota not applicable) |
| `DELETE notes/{id}/` | | 200 `{id, deleted_at, purge_after}` (trash, 30 days; undo with restore) | 404 |
| `POST notes/{id}/restore/` | | 200 `Note` | 404; 429 `quota_exceeded` |
| `GET notes/{id}/versions/` | | 200 `{items: [{rev, title, source, chars, created_at}]}` newest first (max 200) | 404 |
| `GET notes/{id}/versions/{rev}/` | | 200 `{rev, title, body_md, source, created_at}` | 404 |
| `POST notes/{id}/versions/{rev}/restore/` | | 200 `Note` (a new head with that text; source `restore`) | 404 |
| `GET notes/changes/` | `?since=<next_since>&limit<=500` | 200 `{items: Note[] (including trashed ones, `deleted_at` set), next_since, has_more}`; start without `since`, keep calling while `has_more` | |
| `POST clips/` | `{client_id, text_md, source: {module, ref, label}, chapter_id?, topic_id?, tag_ids?}` | 201 `{note: Note, created: true}` (200 `created: false` on replay) | 422, 429 |

**Conflicts.** Send `base_rev` (the `rev` you last received) and, when you can, `base_body_md` (the body at that rev). If `base_rev` equals the stored `rev` the save is accepted.
If it is older the server merges text (3-way, fields by compare-and-set; scalar fields last write wins). A clean merge answers 200 with `merged: true` and the merged
`body_md`. An overlap answers 409 `note_conflict`, `details: {"theirs": {rev, title, body_md, updated_at}, "mine": {title?, body_md?}, "merged": {body_md}|null}`
(`merged` is a best effort starting point, or null). Nothing is written. Resolve by resending with `base_rev = theirs.rev` and `resolution`:
`mine` (your fields win), `theirs` (no-op, returns the stored note), `both` (theirs, a `---` line, then yours). If `base_body_md` is missing and the server no longer holds that
version the answer is also 409 with `merged: null`: retry once with `base_body_md`.
Autosaves within 60 seconds of the previous autosave update one version row (a burst of typing is one version).

**Quota exceeded details:** `{"kind": "notes"|"tags"|"storage", "used": int, "limit": int, "plan": "free"}`.

## Aggregate, counts, chapter overview, search

| Method and path | Query | Success |
| --- | --- | --- |
| `GET aggregate/` | `level` (uuid, required when `subject`), `subject`, `chapter`, `topic` (keys), `tab=all\|notes\|highlights\|documents` (R1: only `all` and `notes` return items), `tag` (uuid), `from`, `to` (dates, filter `updated_at`), `q`, `unfiled=1`, `cursor`, `limit<=100` (default 30) | 200 `{items: [{type: "note", ...NoteSummary}], next_cursor}` keyset `(updated_at desc, kind_rank, id)`; later releases add `type` `highlight`, `document` |
| `GET aggregate/counts/` | `level` (required), `subject` (key, required) | 200 `{subject_key, chapters: [{chapter_id, chapter_key, name, notes, highlights, marks, documents, has_summary, last_noted_at}] (in syllabus order, zero rows included), unfiled: int, moved_or_removed: [{chapter_key, chapter_name, notes, highlights, marks, documents}]}` with a weak `ETag`; send `If-None-Match` for 304 |
| `GET chapters/{chapter_key}/overview/` | `level` (required), `subject` (key, required) | 200 `{chapter: {id, key, name, subject_key, subject_name, level_id}, counts: {notes, highlights, marks, documents}, has_summary, last_noted_at, current_summary: NoteSummary|null, recent: NoteSummary[<=5], documents: []}`; 404 when the key is not in the level's current scheme |
| `GET search/` | `q` (required, 1..200 chars), `scope=all\|notes\|highlights\|pdf` (default `all`), `level`, `subject`, `chapter`, `limit<=50`, `cursor` | 200 `{items: [{type: "note", id, title, snippet, link, rank, updated_at}], next_cursor}`; `scope=pdf` answers 403 `feature_disabled` until `notes_pdf` is on, then `{items: [], next_cursor: null}` (R2) |

## Tags, suggestions, settings, usage, account

| Method and path | Body | Success | Errors |
| --- | --- | --- | --- |
| `GET tags/` | | 200 `{items: Tag[]}` (all of the student's tags, by name) | |
| `POST tags/` | `{name (1..30), color_key?}` | 201 `Tag` (200 with the existing tag when the normalised name exists) | 429 `quota_exceeded` kind `tags` (200 tags) |
| `PATCH tags/{id}/` | `{name?, color_key?}` | 200 `Tag` | 404; 409 `tag_exists` |
| `DELETE tags/{id}/` | | 204 | 404 |
| `PUT items/tags/` | `{item_type: "note", item_id, tag_ids: uuid[]}` replaces the item's tag set | 200 `{item_type, item_id, tags: Tag[]}` | 404; 400 |
| `POST items/chapter-suggest/` | `{text, level_id?}` (no AI, pure text match against the chapters of the student's enrolled syllabus, or the level's current scheme) | 200 `{suggestions: [{chapter_id, chapter_key, chapter_name, subject_id, subject_key, subject_name, score}]}` max 3 | |
| `GET settings/`, `PUT settings/` (partial) | `{color_legend?: {y,g,b,p,o: name 1..24 chars, unique}, default_color?, page_tone?: "original"\|"paper"\|"night", finger_draws?, ocr_default?: "ask"\|"always"\|"never", ocr_lang?: "eng"\|"eng+hin"}` | 200 settings object with the same keys plus `legend_schema` | 400 |
| `GET usage/` | | 200 `{plan, limits: {max_storage_mb, max_file_mb, max_pages, max_documents, max_notes, max_note_chars, max_note_images, max_marks_per_document, max_tags, ocr_pages_per_month, ai_ocr_pages_per_month, ai_summaries_per_month, exports_per_month, max_share_links, max_offline_documents}, used: {storage_bytes, documents, notes, tags, share_links, ocr_pages, ai_ocr_pages, ai_summaries, exports, uploads}, resets_on: "YYYY-MM-DD"}` (month figures in India time) | |
| `GET export/` | | 200 JSON of everything the student owns in notes (notes with versions, tags, settings, usage) | never gated |
| `DELETE /api/v1/notes/` | | 200 DeleteReport `{notes, versions, tags, images, settings}` counts; image objects are removed within 24 hours | never gated |

## Images (media, used by note bodies)

`![alt](attachment:<uuid>)` in `body_md`. Upload flow (module `media`, not flag gated by itself):

| Method and path (under `/api/v1/`) | Body | Success |
| --- | --- | --- |
| `POST media/uploads/` | `{kind: "note_image", mime: "image/png"\|"image/jpeg"\|"image/webp", bytes}` | 201 `{attachment: {id, kind, status: "reserved", bytes, mime}, upload: {url, method: "PUT", headers, expires_at}}`; 415 `unsupported_type`; 413 `file_too_large`; 429 `quota_exceeded` |
| `POST media/uploads/{id}/complete/` | | 200 `{attachment: {id, status: "clean"}}` (R1 note images need no scan) |
| `GET media/attachments/{id}/url/` | | 200 `{url, expires_at}` signed read URL (1 hour) |

## Cron

`POST` (or `GET`, which is what Vercel Cron sends) `internal/tick/` with header `X-Notes-Tick-Secret: $NOTES_TICK_SECRET` or `Authorization: Bearer $NOTES_TICK_SECRET`; the original line follows: with header `X-Notes-Tick-Secret: $NOTES_TICK_SECRET` (constant-time check). Not for browsers. Runs trash purge, version thinning,
usage reconcile, reservation expiry and queued light jobs; each run is bounded to 20 seconds and safe to repeat.


---

# Release R2 (flag `notes_pdf`): PDF library, reader, annotations, OCR, export

Backend: `apps/api/modules/notes` (documents, annotations, worker jobs). Sources of truth for behaviour: PRD sections 5, 6, 9 and
ERD sections 2, 3, 6. This section fixes the exact shapes. Same conventions as R1 (error envelope, cursor lists, 404 for what the
caller does not own, ids are UUID strings). Every endpoint below answers 403 `feature_disabled` when `notes_pdf` is off, except
`GET export/`, `DELETE /notes/`, `GET usage/` and `GET settings/`, which stay open. `notes_ai`-only features (`mode: "ai"` OCR,
summaries, share links, replace edition, offline packs, resumable upload, unlock for search) answer 403 `feature_disabled` in R2. They are specified in the R3 section at the end.

## R1 follow-up: the client owns the note id

- `POST notes/` body gains optional `id` (UUID). When present it is the primary key; `client_id` defaults to it. Old clients that
  send only `client_id` keep working (server generated id, same idempotency as before).
- `PUT notes/{id}/` is an idempotent create: same body as `POST notes/` (without `id`). Row absent: 201 `Note`. Row present for the
  same student: 200, the stored `Note` unchanged (edits go through `PATCH`, so a replayed create never overwrites a later edit).
  The id belongs to another student (or exists in any state outside this student's rows): 404, never a hint that it exists.
- Offline order: `PUT` (create) -> `PUT items/tags/` -> `PATCH` (base_rev 1) replay in that order; a parked conflict never blocks them.

## Shapes

`Link`: same object as R1 (`level_id`, `subject_*`, `chapter_*`, `topic_*`, `moved_or_removed`).

`DocumentSummary`: `{id, origin: "upload"|"platform", title, original_filename, source_kind: "institute_material"|"coaching"|"own_notes"|"handwritten"|"other",
edition_label|null, status: "reserved"|"scanning"|"inspecting"|"ready"|"needs_password"|"rejected"|"expired"|"failed",
status_reason|null ("type_mismatch"|"malware"|"pdf_corrupt"|"too_many_pages"|"too_large"|"decode_failed"|"policy"), bytes, page_count|null,
is_scanned|null, is_encrypted, can_copy|null, can_modify|null, text_status, text_pages_done, ocr_status, ocr_pages_done, ocr_pages_total, ocr_mode, ocr_lang,
last_page, last_zoom, page_tone|null, last_opened_at|null, marks_count, cover_url|null (signed, 1 h), duplicate_of: uuid|null, link: Link, tags: Tag[],
rev, created_at, updated_at, deleted_at|null, purge_after|null}`

`Document` = `DocumentSummary` + `{client_id, can_open: bool, file_url|null, file_url_expires_at|null, page_meta: [{w, h}]|null (points, intrinsic rotation applied),
outline: OutlineNode[]|null, has_javascript, change_seq, ranges: PageRange[]}`.
`file_url` is present when the file is clean and the status is `inspecting`, `ready` or `needs_password` (a stuck inspection still opens, ERD 6.5); signed, TTL 4 h.
`OutlineNode`: `{title, page, children: OutlineNode[]}`. `PageRange`: `{id, page_from, page_to, source: "user"|"outline"|"ai", chapter_id, chapter_key, subject_key, subject_name, chapter_name, topic_id|null, topic_key|null, topic_name|null}`.
`duplicate_of` is the id of an earlier live document of the same student with the same file hash (computed at read time), else null.

`Annotation`: `{id, document_id, page, kind: "highlight"|"underline"|"ink"|"textbox"|"sticky"|"bookmark"|"area", geometry (ERD 3.5), color|null, comment, quote_exact|null,
quote_prefix|null, quote_suffix|null, text_start|null, text_end|null, anchor_engine: "pdfjs"|"ocr"|null, link: Link, chapter_source: "explicit"|"range"|"document"|"none",
tags: Tag[], recall_card_id|null, rev, seq, device_id|null, created_at, updated_at, deleted_at|null}`. A tombstone has `deleted_at` set and is returned by the delta feed.

`ExportJob`: `{id, kind: "pdf"|"archive", document_id|null, status: "queued"|"running"|"done"|"failed"|"expired", progress (0..100), page_count|null,
error_code|null ("export_too_large"|"restricted"|"locked"|"failed"), download_url|null (signed, 24 h, only when done; fetch `GET exports/{id}/` again for a fresh link), expires_at|null (when the file is deleted: 7 days after it was built; a `done` job past it reads `expired`), options, created_at, details|null}`.
`details` is `{suggested_pages: "1-640"}` when `error_code` is `export_too_large` (a page range that should fit), else null. `options` is the canonical form of what was sent (`pages` as `"1-3,7"`, omitted when it covers the whole file, `include` in fixed order)

## Documents

| Method and path | Body or query | Success | Errors |
| --- | --- | --- | --- |
| `POST documents/` | `{client_id, filename, bytes, mime: "application/pdf", page_count_hint?, source_kind?, chapter_id?, topic_id?}` throttle `notes_upload` 30/h | 201 `{document: Document (status "reserved"), upload: {url, method: "PUT", headers, expires_at}}`; 200 same body on a replayed `client_id` | 413 `file_too_large` details `{limit_mb}`; 415 `unsupported_type`; 422 `too_many_pages` details `{limit}`; 429 `quota_exceeded` details `{kind: "storage"\|"documents", used, limit, plan, largest_documents: [{id, title, bytes}] (5)}` |
| `POST documents/{id}/complete/` | | 200 `Document` (status `scanning`, or `rejected`); idempotent | 404; 409 `not_uploaded` (object not in storage yet) |
| `POST documents/{id}/abort/` | | 200 `{id, status: "expired"}`; releases the reservation | 404 |
| `GET documents/` | `?subject=<key>&level=&chapter=<key>&tag=<uuid>&status=&source=&q=&trashed=1&sort=recent\|title&cursor&limit<=100` | 200 `{items: DocumentSummary[], next_cursor}` (recent = `last_opened_at` desc nulls last then `created_at` desc; "Continue reading" = `?status=ready&limit=3`) | 400 |
| `GET documents/{id}/` | | 200 `Document` | 404 |
| `PATCH documents/{id}/` | `{base_rev?, title?, source_kind?, edition_label?, chapter_id?, topic_id?, tag_ids?}` | 200 `Document` | 404; 409 `document_conflict` (stale `base_rev`; details `{theirs: Document}`); 422 `unknown_chapter` |
| `DELETE documents/{id}/` | `?permanent=1` | 200 `{id, deleted_at, purge_after}` (trash 30 days, quota still counted); `permanent=1` purges now and frees quota (object removed within 24 h): 200 `{id, purged: true}` | 404 |
| `POST documents/{id}/restore/` | | 200 `Document` | 404; 429 `quota_exceeded` |
| `PUT documents/{id}/chapters/` | `{ranges: [{page_from, page_to, chapter_id, topic_id?, source?}]}` replaces the set | 200 `{ranges: PageRange[], relinked: int}` | 409 `ranges_overlap`; 422 `unknown_chapter`, `invalid_range` |
| `PUT documents/{id}/progress/` | `{last_page, last_zoom: "fit"\|"<percent>", page_tone?: "original"\|"paper"\|"night"\|null}` | 200 `{last_page, last_zoom, page_tone, last_opened_at}` (last write wins, idempotent) | 404; 400 |
| `GET documents/{id}/processing/` | | 200 `{status, status_reason, text_status, text_pages_done, ocr_status, ocr_pages_done, ocr_pages_total, page_count, is_scanned}` (cheap poll) | 404 |
| `GET documents/{id}/pages/text/` | `?from=&to=` (at most 20 pages) | 200 `{pages: [{page, text, source: "native"\|"ocr"\|"ai", conf|null, words: [[x, y, w, h, "word"]]\|null}], text_status, ocr_status}` (`words` only for OCR pages, normalised frame, 4 decimals) | 404; 400 |
| `GET documents/{id}/search/` | `?q=&limit<=50` | 200 `{items: [{page, snippet, rank}], text_status, ocr_status, indexed_pages, page_count}` | 404; 400 |
| `POST documents/{id}/ocr/` | `{mode: "tesseract", lang?: "eng"\|"eng+hin", pages?: "1-40,50"}` | 202 `{status, ocr_pages_total, charged_pages, estimate_seconds}` (monthly OCR pages charged once per content and page range, for the pages that need reading and are not already queued by an earlier request: `charged_pages` is that count, `0` with `status: "done"` when the content was already read, as for a second student with the same file; `status` is `pending`, `running`, `partial` or `done`; asking for `eng+hin` on text read as English redoes and charges those pages too; always 202) | 403 `feature_disabled` (`mode: "ai"`); 404; 409 `locked` (needs a password); 409 `not_ready` (not inspected yet); 422 `not_scanned_or_no_pages` (every page has text); 422 `invalid_pages` (details `{reason}`); 422 `ocr_not_allowed` (the file forbids copying its text); 429 `quota_exceeded` details `{kind: "ocr", used, limit, plan, resets_on}` |
| `POST documents/{id}/exports/` | `{client_id, options: {pages?: "1-40", include?: ["highlight","underline","ink","textbox","sticky","area"], colors?: [key], tags?: [uuid], appendix?: bool}}` throttle `notes_export` 6/h | 202 `{export: ExportJob}` (200 on replayed `client_id`) | 404; 422 `export_not_allowed` details `{reason: "restricted"\|"locked"\|"not_ready"}` (restricted = the file's flags forbid copying or modifying); 422 `invalid_options` details `{field}`; 429 `quota_exceeded` details `{kind: "export", used, limit, plan, resets_on}` |
| `POST export/archive/` | `{client_id}` ("Download my notes": a zip of notes as Markdown with front matter and a highlight digest per document as Markdown and CSV; documents only when `notes_pdf` is on; flag `notes`; not charged to the monthly exports) | 202 `{export: ExportJob (kind "archive")}`; 200 with the stored job on a replayed `client_id` or while an earlier archive of the student is still being built | 429 (throttle `notes_export`) |
| `GET exports/{id}/` | | 200 `ExportJob` (flag `notes`; a `pdf` export also needs `notes_pdf`, an `archive` does not) | 404 |
| `POST documents/{id}/replace/` | see R3 | see R3 | |

Platform documents (`origin: "platform"`, created only by the service `open_platform_document`) appear in the library and open in the reader like any
document; they count no bytes, cannot be re-uploaded, and `DELETE` removes only the student's row, marks and tags, never the shared object.

### Documents: implementation notes (API-1b)

- `POST documents/` replay (`client_id` seen before): 200 with the stored `Document`; `upload` is a fresh signed URL while the file is still expected
  (status `reserved`) and `null` afterwards. Order of refusals: 415, 413 `{limit_mb}`, 422 `too_many_pages` `{limit}`, 429 (storage or documents, with `largest_documents`).
- `title` defaults to the file name without its extension; `page_count_hint` is stored as `page_count` until the inspection replaces it.
- A reservation not confirmed within 30 minutes becomes `expired` (quota released) and stays visible by id for a day; `GET documents/` hides `expired` unless `?status=expired`.
  `POST complete/` on an expired document is 409 `not_uploaded`. `POST abort/` after the file was confirmed is 409 `not_abortable`; `DELETE` of a still `reserved` document is 409 `not_trashable` (abort it).
- `GET documents/` paginates with an opaque offset cursor (a library holds at most 100 documents). `?trashed=1` orders by `deleted_at` desc. `q` matches title and original file name.
- `PATCH`: a `base_rev` that is not the stored `rev` is 409 `document_conflict` with `details.theirs` (the stored `Document`); without `base_rev` the write wins. Changing the default chapter re-links the marks that inherit it.
- `PUT chapters/`: `422 invalid_range` (bad page numbers, past the last page when the count is known, more than 500 ranges), `409 ranges_overlap` (`details {a, b}` indexes of the two ranges); `relinked` counts marks whose chapter changed (explicit links are never touched).
- `GET search/`: `scope=pdf` answers up to 100 hits (no `next_cursor`); `scope=highlights` up to 100 marks; `scope=all` appends the top `limit` marks and the top `limit` PDF pages after the notes of the FIRST page only.
  PDF and mark hits also carry `document_title`; snippets are plain text (no markup: the web marks the words), `ts_headline` for the top 20 pages and a cut around the first match for the rest.
  `meta.not_searchable` lists live documents without text and why: `locked` (password), `scanned` (no OCR yet), `pending` (text still being extracted or inspected).
- `GET documents/{id}/search/`: `items` are pages ranked best first (`limit` default 50); `indexed_pages` counts stored pages of the file.
- A document's cover is a `note_image` attachment made by the inspection (240 px WebP); `cover_url` is null until it exists and is clean.

## Annotations

| Method and path | Body or query | Success | Errors |
| --- | --- | --- | --- |
| `GET documents/{id}/annotations/` | `?since_seq=0&limit<=500` | 200 `{items: Annotation[] (with tombstones, ordered by seq), change_seq, next_since_seq, has_more}` | 404 |
| `PUT annotations/{id}/` | `{document_id, kind, page, geometry, color?, comment?, quote_exact?, quote_prefix?, quote_suffix?, text_start?, text_end?, anchor_engine?, chapter_id?, topic_id?, tag_ids?, device_id?, base_rev (omit or 0 on create), base?: {field: value last seen}, resolution?: "mine"\|"theirs"\|"both"}` | 201 on create, 200 otherwise: `{annotation, merged, restored, overwritten: string[]}` | 404; 409 `annotation_conflict` details `{mine, theirs: Annotation, device_label, theirs_updated_at}`; 422 `invalid_geometry` details `{errors: [{code, message}]}`; 429 `quota_exceeded` kind `marks` |
| `DELETE annotations/{id}/` | `{base_rev}` | 200 `{annotation (tombstone), edit_wins: false}`; when the stored `rev` is newer the mark stays: 200 `{annotation (live), edit_wins: true}` | 404 |
| `POST annotations/{id}/restore/` | | 200 `{annotation}` | 404 |
| `POST annotations/batch/` | `{document_id, ops: [{op: "upsert"\|"delete"\|"restore", id, ...PUT fields or {base_rev} for delete}]}` at most 100, in order, one document lock | 200 `{results: [{id, status: "ok"\|"conflict"\|"rejected", annotation?, merged?, restored?, overwritten?, edit_wins?, error?: {code, message, details}}], change_seq}` | 404; 413 `batch_too_large` |
| `POST annotations/{id}/card/` | `{client_id, kind?: "formula"\|"rule"\|"definition"\|"example"\|"doubt"\|"fact"}` | 200 `{card_id, existing}` | 503 `recall_unavailable` (no provider registered); 404; 422 `no_text` |
| `GET settings/` | gains `capabilities: {recall: bool, ocr_hindi: true, ai_ocr: false}` | | |
| `GET usage/` | gains `largest_documents: [{id, title, bytes}]` (5, trashed ones included, for the quota sheet) | | |

Rules the server applies (ERD 3.6): same `base_rev` accepts; different fields union; same scalar last write wins (`overwritten` lists the fields); geometry last write
wins; `comment` 3-way merge (clean merge `merged: true`, overlap 409); edit beats delete (`restored: true`); duplicate create returns the stored row with 200; every accepted
write increments `documents.change_seq` under the document row lock and stamps `seq`. Chapter inheritance: an explicit `chapter_id` wins (`chapter_source: "explicit"`),
else the page range, else the document default, else none. A mark's own text and `quote_*` never leave the API in analytics.

Implementation notes for the web (marks), all additive to the table above:

- **Response extras.** `PUT`, `DELETE`, `restore` answer `{annotation, merged, restored, overwritten, edit_wins, change_seq, marks: {count, limit, near_limit}}` (`edit_wins` is only ever true on `DELETE`);
  the batch answers `{results, change_seq, marks}`. `marks.near_limit` is true from 95% of the plan's marks per document: show the quiet notice. A batch result is `{id, status, annotation, merged, restored, overwritten, edit_wins}`
  for `ok` and `{id, status, error: {code, message, details}}` for `conflict` (`annotation_conflict`, details as for `PUT`) and `rejected` (`invalid_geometry`, `quota_exceeded`, `unknown_chapter`, `unknown_tag`, `invalid_mark`,
  `validation_error`, `not_found` for a mark that is not the student's or no longer exists). A rejected or conflicting op consumes no `seq`.
- **What to send.** `base_rev` omitted or 0 means create; an existing id then answers 200 with the stored row (a replayed create), never an overwrite. Send only the fields that changed, and a `base` entry for each of them
  (the value last seen): a field without a `base` entry on a stale `base_rev` is written as is, and a `comment` without one that differs from the stored text is a 409. `kind` never changes (422 `invalid_mark`).
  `DELETE` without `base_rev` is unconditional. `chapter_id: null` clears an explicit chapter (the mark re-inherits); `topic_id` follows the same rule. `tag_ids` replaces the set; another student's tag id is 422 `unknown_tag`.
- **Conflicts.** `details.device_label` is the first 8 characters of the other device's `device_id` (the server has no friendly names) or null. To resolve, resend with `base_rev` = `details.theirs.rev` and `resolution`;
  `theirs` keeps the stored comment, `mine` replaces it, `both` stores theirs, a `---` rule, then mine.
- **Delta feed.** Order is `seq`; a page never ends inside a group of rows sharing a `seq` (a page-range change re-links many marks under one new `seq`), so it may hold slightly more than `limit`. Resume from `next_since_seq`;
  when caught up it is the document's `change_seq`. Tombstones are purged 30 days after deletion: a device whose last sync is older than that resyncs from `since_seq=0`. Setting a mark's recall card id also advances `seq` (no `rev` bump).
- **Counts.** `highlights` = live highlight, underline and area marks; `marks` = every live mark; `documents` = live documents (not reserved, expired, rejected or trashed) whose default link or page range is in the chapter, once each.
  Marks of a trashed document count nowhere. `unfiled` is notes, listed marks and documents with neither a chapter nor a range. Aggregate rows: `{type: "highlight", ...Annotation}` and `{type: "document", ...DocumentSummary}`;
  `color` and `doc` filter marks only (notes and documents step aside while either is set).
- **Recall.** `recall_card_id` is null while `settings.capabilities.recall` is false. `POST annotations/{id}/card/` checks ownership first (404), then the provider (503 `recall_unavailable`), then the text (422 `no_text`); the tap is idempotent per mark and kind.

## Search (R2 additions)

`GET search/?scope=pdf|all|highlights`: items gain `{type: "pdf", document_id, document_title, page, snippet, rank, link}` and `{type: "highlight", annotation_id, document_id,
page, snippet, color, link}` (at most 5 pages per document, 100 hits in total, ranked). The response gains `meta: {indexing_documents: int, not_searchable: [{document_id, reason: "locked"\|"scanned"\|"pending"}]}` for `scope=pdf|all`.
`scope=pdf` with `notes_pdf` off answers 403 `feature_disabled` as before. Reference-style queries (`17(5)`, `Ind AS 115`) are phrase matched (ERD 6.3). `aggregate/?tab=highlights|documents|all`
now returns `{type: "highlight", ...}` rows (text kinds only: highlight, underline, area, sticky, textbox) and `{type: "document", ...}` rows; `aggregate/counts/`, `chapters/{key}/overview/`
fill `highlights`, `marks`, `documents`, `last_noted_at` and `documents: DocumentSummary[]` from live data. `?color=<key>&doc=<uuid>` filter marks.

## Jobs and domain events (server only)

Job types: `notes.scan`/media scan, `notes.inspect`, `notes.extract_text` (20-page chunks), `notes.ocr` (10-page chunks, `dedupe_key = notes.ocr:<content_id>` for the first job of a request, `notes.ocr:<content_id>:<chain>:<first page>` for the chunks it chains), `notes.export_pdf`, `notes.export_archive`,
`notes.expire_reservations`, `notes.expire_exports` (light, in the tick: exports past 7 days become `expired` and their files are deleted). Events: `notes_document_ready` `{document_id, pages, scanned, encrypted, stage: "readable"|"searchable"}`, `notes_export_ready`, plus `notes_chapter_counts_changed` for
highlights (created, trashed, restored, re-linked). The worker host runs `python manage.py run_worker`; the tick (`POST internal/tick/`, every 5 minutes) runs only the light jobs.


# R3: AI help, Replace edition, Unlock for search, resumable upload (flag `notes_ai`, FAILS CLOSED)

Every endpoint below needs the `notes` flag and `notes_ai` (fail closed: only an explicit "on" counts; a missing key or a PostHog outage means off, 403 `feature_disabled`). Replace edition, unlock and resumable upload also need `notes_pdf`. Taking things back never needs the flag: `DELETE ai/consent/`, `POST ai/summary/{id}/discard|cancel/`, `POST ai/ocr/{id}/cancel/`. Share links (`notes_share`), offline packs and the recall bridge are NOT built: their routes are not present.

`GET settings/` `capabilities` gains `ai_ocr`, `ai_summary`, `unlock` and `resumable_upload` (false when this deployment lacks the key, tier, approved wording, kill switch, budget, Fernet key or S3 credentials).

## AI consent and gates

| Endpoint | Body | Success | Errors |
| --- | --- | --- | --- |
| `GET ai/consent/` | | 200 `{version, text: {title, points: [{heading, text}], checkbox}, consented, consented_version, consented_at}` | |
| `PUT ai/consent/` | `{version}` | 200 consent state | 409 `consent_version_mismatch` |
| `DELETE ai/consent/` | | 200 `{consent, discarded_drafts, cancelled_jobs}` (drafts deleted, queued jobs cancelled and refunded) | |

AI is available only when ALL hold: `GEMINI_API_KEY`, `GEMINI_DATA_TIER=paid`, `NOTES_AI_CONSENT_APPROVED` equals the consent version in code, the kill switch of the feature (`NOTES_AI_SUMMARY_ENABLED`, `NOTES_AI_OCR_ENABLED`) is on, `NOTES_AI_DAILY_BUDGET_PAISE` is above 0 and not spent today (India day), and the student agreed to the current version. Otherwise 503 `ai_unavailable` / `ai_budget_exhausted` (nothing charged), or 403 `ai_not_consented` `{version}`.

## AI exam summary of a chapter

| Endpoint | Body | Success | Errors |
| --- | --- | --- | --- |
| `POST ai/summary/` | `{client_id, chapter_id, include?: ["notes","highlights"]}` throttle `notes_ai` 20/h | 202 `SummaryJob` (200 when the same inputs were summarised before: `cached: true`, nothing charged) | 403 `ai_not_consented`; 422 `not_enough_material` `{items, chars, min_items, min_chars}`; 429 `quota_exceeded` `{kind: "ai_summary", used, limit, resets_on}`; 503 |
| `GET ai/summary/?chapter_id=` | | 200 `{job: SummaryJob\|null}` (latest) | |
| `GET ai/summary/{id}/` | | 200 `SummaryJob`: `{id, kind, status: queued\|running\|ready\|accepted\|discarded\|error\|expired\|cancelled, chapter, item_count, estimate_seconds, cached, error_code, charged, created_at, finished_at, expires_at, draft: {title, body_md, sources: [{n, kind, id, page, document_id, label}], dropped}\|null, result_note_id}` | 404 |
| `POST ai/summary/{id}/accept/` | `{title?, body_md?}` | 200 `{job, note}` (a normal note filed under the chapter, sources linked; only here does anything become a note) | 409 |
| `POST ai/summary/{id}/discard/`, `.../cancel/` | | 200 `SummaryJob` (cancel refunds the quota if still queued) | 404; 409 |

A draft is never a note until accepted and expires after 14 days. Model output is parsed as data only; every claim carries a source number and unsourced lines are dropped (`dropped`).

## AI page reading ("Improve this page")

`POST documents/{id}/ocr/` with `{mode: "ai", pages: "3"|"1-5"}` (at most 10 pages, flag `notes_ai`): 202 `{job, charged_pages, estimate_seconds, skipped: {already_read: [], has_text: [], in_progress: []}}`, or 200 with `job: null` when every page was skipped. Pages that already have text of their own (native or a better read) are skipped and not charged. Errors: 403 `ai_not_consented`; 409 `locked` / `not_ready`; 422 `invalid_pages`, `nothing_to_do`, `not_openable`; 429 `quota_exceeded` `{kind: "ai_ocr_pages"}`; 503. `GET ai/ocr/{id}/` returns `{id, status, done: {page: "clear"|"partial"}, failed: {page: code}, charged_pages, refunded_pages, ...}` (never page text); `POST ai/ocr/{id}/cancel/` stops the rest and refunds the pages not yet read. A page stored with source `ai` ranks above `ocr` and `native` never loses to it.

## Replace edition

| Endpoint | Body | Success | Errors |
| --- | --- | --- | --- |
| `POST documents/{id}/replace/` | `{client_id, filename, bytes, mime, page_count_hint?, edition_label?}` throttle `notes_upload` | 201 `{document, upload}` exactly like `POST documents/` (200 on a replayed `client_id`). The new document has `replaces_document_id`, `reanchor_status: "waiting"`, the old one's title, chapter, source kind and tags. Then the ordinary `complete/` | 404; 409 `not_replaceable` (old document in the trash or not ready); every refusal of an upload (413, 415, 422, 429) |
| `GET documents/{id}/attention/` | `?status=open\|kept\|noted\|dismissed` | 200 `{document_id, replaces_document_id, status: none\|waiting\|running\|done\|failed, stats: {total, attached, moved, needs_attention, ranges_copied}\|null, items: [{id, source_annotation_id, kind, page, color, quote, comment, reason, status, new_annotation_id, result_note_id, resolved_at}]}` | 404 |
| `POST documents/{id}/attention/{item_id}/` | `{action: "keep"\|"note"\|"dismiss", page?}` | 200 item. `keep` puts the mark on the new edition (same shape, `page` or its old page); `note` saves quote and comment as a note; repeating the same decision is fine | 404; 409 `already_resolved`; 422 `page_out_of_range`, `nothing_to_save` |

`Document` gains `replaces_document_id`, `reanchor_status`, `reanchor` (the stats). The old edition is never changed. When the new file is ready the inspection queues `notes.reanchor`: text marks are found again by their quote (nearest page first, fuzzy within 5 pages, exact beyond) and redrawn with the new words' rectangles; other marks follow their page only when its native text is unchanged; everything else becomes an item. Carried marks have id `uuid5(new document, old mark)`, so the job and "keep" are idempotent. Page ranges are copied when both editions have the same number of pages. Event `notes_reanchor_done` `{document_id, attached, needs_attention}`.

## Unlock for search

`POST documents/{id}/unlock/` `{password}` (throttle `notes_unlock` 20/h; five wrong passwords in an hour lock the document for an hour): 202 `{document_id, unlock_status: "waiting"}`. Errors: 404; 409 `not_locked` (not waiting for a password, or in the trash), 409 `unlock_in_progress`; 429 `too_many_attempts`; 503 `unlock_unavailable` (no `NOTES_UNLOCK_FERNET_KEYS`). `Document` gains `unlock_status` (`none|waiting|running|done|failed`) and `unlock_reason` (`wrong_password|restricted|unreadable|expired`); poll `GET documents/{id}/`. The password is sealed with Fernet into the job payload (token life one hour), used in memory by the worker and removed from the row when the job ends; a light job clears any left over. No unprotected copy of the file is made: the text is stored on a private content row of this document (identical files of other students get nothing). A PDF whose owner forbids copying text is `restricted`. On success the document becomes `ready` (still encrypted: the reader asks for the password as before) and searchable.

## Resumable upload

When the deployment has S3 credentials and `notes_ai` is on, the reservation answer for a file of 16 MiB or more carries `upload.resumable: {document_id, part_size: 8 MiB, parts}`. The browser then (instead of the single PUT): `POST documents/{id}/resumable/` (opens the multipart upload, or answers `{part_size, parts, done: [{number, etag, size}]}` with what storage already holds) , `POST documents/{id}/resumable/parts/` `{numbers: [<=20]}` -> `{parts: [{number, url}]}` (one PUT URL per part, one hour), PUT each part, `POST documents/{id}/resumable/complete/` `{parts: [every number]}` -> `{joined}`, then the ordinary `POST documents/{id}/complete/`. The server joins with storage's own ETags and refuses unless every part is there at its full size (422 `parts_incomplete`). Errors: 404; 409 `not_resumable` (not a waiting reservation); 503 `resumable_unavailable`. Abort or expiry aborts the multipart upload. Without S3 credentials nothing changes: one signed PUT.

## R3 jobs and events

Heavy (worker): `notes.summarize`, `notes.ocr_ai`, `notes.reanchor`, `notes.unlock`. Light (tick): `notes.expire_ai` (drafts past 14 days), `notes.expire_unlock` (password tokens past one hour). Events: `notes_summary_ready`, `notes_reanchor_done`, `notes_document_ready` (also after an unlock).
