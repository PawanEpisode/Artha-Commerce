# Hosted past-paper PDFs

Past papers and suggested answers are hosted by us, not linked from the institute's site. The PDF goes into the private
`notes-private` Supabase bucket as a platform-owned file, the paper's link points at it, and a student opens it from the paper
page in the PDF reader (read, highlight, pen, text box). Marks are private to each student; the file is shared.

## How it works

- `modules/pyq/domain/sources.py` finds the PDFs in `docs/source-material/question-bank/cma-final/pyqs` by folder and file
  name (`P13 - ... / June 24 / ... Question Paper ... .pdf`). A "Question & Answers" file is one combined paper link.
- `publish_pyq_pdfs` uploads each file to `platform/pyq/<id>.pdf`, creates a clean `media.Attachment` owned by
  `PLATFORM_OWNER_ID`, and a `PaperLink` with an empty `url` and `attachment_id` set. The paper becomes `delivery=hosted`,
  `rights_basis=institute_material`.
- `POST /pyq/papers/<paper>/links/<link>/open/` calls `notes.open_platform_document` for the student and returns
  `{document_id}`; the web opens `/app/notes/pdf/<document_id>`. Needs the student's `notes` and `notes_pdf` flags.
- The bucket stays private. The reader gets a short-lived signed URL after the access check.
- A re-import of a paper keeps its hosted PDF.

## Steps to run (once per environment)

1. `apps/api/.env` has `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (and the `NOTES_S3_*` values the notes reader already uses).
2. Supabase dashboard, Storage, Settings: raise the **global file size limit to at least 100 MB** (the largest paper is about 59 MB;
   the default is 50 MB). Pro plan needed above 50 MB.
3. `python manage.py ensure_notes_buckets` (creates `notes-private` if missing).
4. `python manage.py migrate` (adds `pyq_paperlink.attachment_id`).
5. Papers must exist first: `python manage.py load_question_bank_seed --dry-run`, read it, then run it.
6. `python manage.py publish_pyq_pdfs --dry-run`, read the list (every line is "would host ..."; "no paper loaded" means step 5
   is missing that paper; "skipped" lists files that did not map).
7. `python manage.py publish_pyq_pdfs`. Run it again any time: papers that already have their PDF are left alone;
   `--force` replaces one.
8. Turn on the `notes` and `notes_pdf` flags for the students who should read papers in the reader.
9. Clean the old rows: `python manage.py seed_cma_pyq` (removes empty legacy shells) and `python manage.py seed_mcq_bank`
   (removes the fabricated link-out booklets).

## Not hosted yet

MCQ banks and numerical workbooks in source-material (16 PDFs) use the same mechanism but are not wired to their sets yet.
Intermediate papers have no source files, so none are listed.
