# F-02 rollout and content admin: exact steps

Do the parts in order. Part A is code hygiene for every change. Parts B to E are one-time. Part F is the everyday editor workflow.

## A. Every code change (developers and Claude)

1. Delete a stale `.git/index.lock` first (only if no git process is running): `find .git -maxdepth 3 -name "*.lock" -delete`.
2. `git switch -c feat/<short-name>` (never work on `main`).
3. API: `cd apps/api && uv run ruff format . && uv run ruff check . && uv run pytest && uv run python manage.py makemigrations --check --dry-run`. If you changed a model: `python manage.py makemigrations`, commit the migration, then the last command must say "No changes detected". The row-level security test needs Postgres (`DATABASE_URL`); it skips on SQLite and runs in CI.
4. Web: `pnpm check` from the repo root (typecheck, lint, format, contrast, tests, build). If you added routes, the build regenerates `apps/web/src/routeTree.gen.ts`; commit it.
5. Commit with a conventional message (`feat(syllabus): ...`), push, open a PR, wait for CI green, merge. Vercel makes a preview per PR.

## B. API environment (Vercel, project `arthacommerce-api`)

Add these in Settings -> Environment Variables (Production and Preview), then redeploy:

| Name | Value |
| --- | --- |
| `DJANGO_ADMIN_PATH` | a hard-to-guess path, for example `studio-x7k2` |
| `CSRF_TRUSTED_ORIGINS` | `https://api.yourdomain.com` (your real API origin) |
| `POSTHOG_API_KEY` | the PostHog project key (the same `phc_` key the web uses). Without it the `syllabus_coverage` flag is not checked on the API and My Coverage stays on |
| `POSTHOG_HOST` | optional, default `https://us.i.posthog.com` |

Optional tuning: `POSTHOG_FLAG_TIMEOUT_SECONDS` (default 1.5) and `FEATURE_FLAG_CACHE_SECONDS` (default 60).

Everything else (`DJANGO_SECRET_KEY`, `DATABASE_URL`, `DIRECT_DATABASE_URL`, ...) is already set per `docs/SETUP.md`.

## C. Database migration (once per environment, from your computer)

1. `cd apps/api`, export `DJANGO_SECRET_KEY` (any value locally) and `DIRECT_DATABASE_URL` (Supabase direct string, port 5432).
2. `python manage.py migrate`. It also applies `syllabus.0009` (chapter map review fields; existing maps become `manual`, not flagged). This creates the profile role, syllabus, coverage, admin, session and auth tables, loads the courses, levels and exam terms, turns on Row Level Security, and creates the two staff groups.
3. Create your own login: `python manage.py createsuperuser` (this is a Django staff account, separate from the student sign-in).
4. Deploy the API (merge the PR). Open `https://<api>/<DJANGO_ADMIN_PATH>/` and log in. If the page has no styling, check that the deploy finished.

## D. Load the content

If Django admin still lists schemes named `indicative` or `2023-sample`, they are leftovers from the first placeholder seed files: run `python manage.py load_syllabus_seed --prune-legacy --dry-run` to preview and without `--dry-run` to delete them (schemes with enrolled students are kept). Exam terms (attempts and dates) belong to a level, so add them per level in Django admin under Exam terms; the CA and CMA dates loaded by migration `0007` come from press reports of the institutes' announcements, so check them against the official schedule. Seed files, one per level, live in `apps/api/modules/syllabus/seed/<course>/<level>/`: CMA and CS (full chapters and topics from the official 2022 syllabi), and CA (papers, groups, sections, chapters and topics extracted from the 36 ICAI paper PDFs in `docs/syllabus-sources/ca/`; links in `docs/syllabus-sources/ca-pdf-links.json`). Coverage summary: `docs/product/F-02-syllabus-coverage-report.md`.

Pick one:

- From the admin: Syllabus -> Schemes -> **Import scheme from JSON**, upload a file from the seed folder. It lands as a **draft**.
- From the command line: `python manage.py migrate` (adds the chapter section and paper source link fields and the CA Self-Paced Online Modules level), then `python manage.py load_syllabus_seed` (drafts only, safe to repeat).

If an earlier load left the old placeholder drafts (scheme code `indicative` or `2023-sample`), delete those drafts in Syllabus -> Schemes first (drafts can be deleted).

Then open each draft scheme, check papers and chapters against the official syllabus, fix names and marks, and only then publish (Part F, step 5). Chapters whose weight source is `analysis` carry an indicative split of a section weight; confirm or edit them.

## E. Web (Vercel, project `arthacommerce-web`)

1. Confirm `VITE_API_URL` is your API origin (no trailing slash). Redeploy the web project after the API is live.
2. Optional: in PostHog create the feature flag `syllabus_coverage`. Without it My Coverage is on for everyone; set it to false to hide it. The API evaluates the same flag for the same user (needs `POSTHOG_API_KEY`, Part B), so a flag that is off also blocks the API and the web shows "not available yet".
3. Check: `/courses` and `/courses/ca` show the API's course text; `/courses/ca/intermediate` shows grouped papers; a subject and a chapter page open; `/sitemap.xml` lists them; open `/og/courses/ca` and a chapter's `/og/courses/...` URL (each must be a PNG, not a redirect), then share one chapter URL in WhatsApp and look at the preview.
4. Sign in, open `/app/syllabus` (it sends you to onboarding first), finish the catch-up, tick a topic, log a revision, change settings, and switch all four themes.
5. In Google Search Console, submit `https://yourdomain.com/sitemap.xml` once.

## F. Everyday editor workflow (in the admin)

1. **Give people access.** Authentication and authorization -> Users -> Add. Tick **Staff status**, then add the user to **Syllabus editors** (edit content, handle reports) or **Syllabus publishers** (also publish and retire). Only superusers can create users.
2. **New scheme.** Syllabus -> Schemes -> Add (level, code such as `2025`, name, source link, applicable exam terms). Or import JSON. Save, then add papers in the inline table.
3. **Add chapters fast.** Open a paper. In "Add chapters in bulk" paste one chapter per line, with optional marks: `GST Basics | 5-8`. Save.
4. **Add topics fast.** Open a chapter. In "Add topics in bulk" paste one topic per line, optionally with a type: `Blocked credit | section`. Save. Use the Chapters list to edit marks, the practice, revision and mock targets, and on/off for many chapters at once. To change the order, filter the list to one paper (papers, chapters and topics all work the same way) and drag a row by its handle, or focus the handle and press Alt with the arrow keys; the new order is saved at once and the siblings are renumbered.
5. **Publish.** Syllabus -> Schemes, tick the scheme, action **Publish**. It fails with a clear message if the scheme has no papers or overlaps another published scheme for the same terms.
6. **When the institute changes the syllabus.** Create a new scheme (or import an edited JSON: export the old one with the **Download as JSON** action, edit, import under a new code). Tick the new scheme, run **Create chapter map from the previous scheme** (it matches by key, then by name and position, and proposes merges and splits; the message says how many rows need review), open Chapter maps (the review queue is sorted with the rows to check first), fix relations and carry ratios in the list, tick the rows you have checked and run **Mark as reviewed (keep as proposed)**, then publish the new scheme (it warns while rows still need review) and retire the old one. Students move over from Coverage settings and keep their progress.
7. **Handle reports.** Syllabus reports shows what students flagged, with a link to the item. Fix it, then mark the report fixed or rejected.
8. **Elective papers.** CMA Final (Paper 20) and CS Professional (Papers 4 and 7) have optional papers. Mark each option paper with kind *Elective* (or tick *Is optional*) and give the options of one choice the same group and paper number; the app then asks the student to pick one in onboarding and on the syllabus map, and counts only that one. Nothing else to configure. After deploying, run the migration (it adds one table); existing students on these levels are asked to choose on their syllabus map and until then no elective counts.
9. **Rules to remember.** Published nodes cannot be deleted; switch them off instead (progress is kept). Edits to a published scheme are live immediately and the admin warns you. Exam terms and levels are under their own lists.

## G. Support

- Enrolments and Coverage events are read-only. Superusers can run **Rebuild progress from the ledger** on an enrolment if a student reports wrong percentages.
- Profiles: superusers can set a student's `role` (student, editor, admin) for the API editor endpoints.

## H. Not built yet (known)

Two-factor login for the admin, single sign-on with Supabase, and an audit trail beyond Django's built-in history log. The offline queue covers tick and log writes only; catch-up and settings still need a connection.
