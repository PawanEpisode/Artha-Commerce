# F-03 Smart Notes, release R1: API contract for the web

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
