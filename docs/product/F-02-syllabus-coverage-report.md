# F-02 Syllabus coverage report (PRD vs ERD vs code vs content)

Date: 5 Oct 2026. Scope: PRD `F-02-syllabus-structure-and-coverage`, its ERD, the `syllabus` and `coverage` modules, and the syllabus content loaded into Django admin.

## 1. Result in one view

| Area | Status |
| --- | --- |
| PRD requirements present in the ERD | 30 of 30 present; 4 only partly (FR-5, FR-8, FR-29, FR-30), clarified in the ERD below |
| Requirements implemented in code | 21 yes, 9 partial, 0 missing (details in section 3) |
| Syllabus content: CMA (3 levels, 22 papers) | Loaded from the CMA Syllabus 2022 PDF: 231 chapters, 1,132 topics |
| Syllabus content: CS (CSEET, Executive, Professional) | Loaded from the ICSI Syllabus 2022 PDF: 4 + 7 + 16 papers, 407 chapters, 2,772 topics |
| Syllabus content: CA (Foundation, Intermediate, Final, SPOM) | Loaded from the 36 ICAI paper PDFs: 4 + 6 + 6 + 16 papers, 304 chapters, 1,478 topics. No marks per chapter (ICAI does not publish them) |

## 2. What was wrong and what was changed

1. The seed files were placeholders: paper names only for 9 levels, plus a memory-based CA Intermediate sample. They are replaced by one file per level (10 files).
2. The model had no place for the Section or Part a chapter belongs to (CMA Section A/B with weightage, CS Part I/II with marks, CA Section A/B and Part I/II), nor for the source document of a paper. Added `Chapter.section` and `Subject.source_url` (migration `0004`), exposed in admin, API, JSON import and export.
3. ICAI Self-Paced Online Modules had no level. Added CA level `spom` (migration `0005`, idempotent).
4. ERD brought in line: new columns, `spom`, seed content table, FR-5 "new/removed" are derived, `coverage_enrollment.level_id` documented.
5. Tests: `test_seed_content.py` (papers per level, key and length limits, section weights, load, export and import round trip); the seed command test and the public courses test were updated. API suite: 154 passed, ruff clean, no pending migrations (after the per-level exam terms, elective choice, admin filters and chapter navigation work).

## 3. PRD to ERD to code (requirements)

| ID | ERD | Code | Gap |
| --- | --- | --- | --- |
| FR-1 hierarchy | yes | yes | |
| FR-2 stable keys | yes | yes | |
| FR-3 marks weightage | yes | partial | Chapters with no marks weigh 1 in the weighted view. Mitigated for CMA by giving every chapter a weight (section 5) |
| FR-4 scheme versions | yes | yes | |
| FR-5 chapter mapping | partial | partial | ERD stores same/split/merged/partial; "new/removed" are derived (now documented). Default map only links equal keys; topics carry over only on equal keys |
| FR-6 public pages + OG | yes | partial | OG image is the default one; no per-course or per-chapter image. `/courses` and `/courses/$course` read the static catalog |
| FR-7 sitemap | yes | yes | |
| FR-8 admin edit/publish | partial | partial | Reordering is a number field, no drag and drop |
| FR-9 idempotent seed | yes | yes | |
| FR-10 report wrong item | yes | partial | Link missing on course/level pages and on `/app/syllabus` screens |
| FR-11 exam terms | yes | yes | Term dates are empty until confirmed from the institutes |
| FR-12 to FR-16 | yes | yes | |
| FR-17 chapter targets | yes | partial | Editable only on the full chapter form |
| FR-18, FR-19, FR-20, FR-21, FR-22 | yes | yes | |
| FR-23 weighted toggle | yes | partial | Subject screen ignores `?view` |
| FR-24 catch-up | yes | yes | |
| FR-25 settings | yes | yes | Total shows red when not 100; server rejects it |
| FR-26 event ledger | yes | yes | |
| FR-27 tracker time | yes | yes | No `tracking` module yet, so nothing calls it |
| FR-28 scheme switch | yes | partial | Summary shows counts, not the list of carried and new chapters |
| FR-29 export, delete | partial | yes | |
| FR-30 feature flag | partial | partial | Web only; API not gated; defaults on when PostHog is not loaded |

Also checked: all 21 PRD endpoints exist under the same paths, all PRD screens have a route, all 12 analytics events are emitted. Not in the ERD: the feature flag behaviour, analytics events, offline queue (not built), per-course OG images. The ERD claim "a test asserts RLS" has no test yet.

These partial items are about the student features, not the syllabus content. None block the content in Django admin; they are the follow-up list.

### Added after the first audit

Exam terms per level; elective choice (onboarding step, syllabus map picker, `PUT coverage/enrollments/{id}/electives/`); `--prune-legacy` cleanup of the placeholder schemes; section grouping, paper PDF link and SPOM on the web; Paper and Chapter filters in the Topic and Chapter admin lists; topic counts, previous and next chapter links and a chapter search box (papers over 8 chapters) in the API and web.

## 4. Content coverage

### CMA (ICMAI, CMA Syllabus 2022)

| Level | Groups | Papers | Chapters | Topics |
| --- | --- | --- | --- | --- |
| Foundation | none | 4 (Papers 1 to 4) | 22 | 114 |
| Intermediate | Group I, Group II | 8 (Papers 5 to 12) | 74 | 419 |
| Final | Group III, Group IV, Electives | 7 (Papers 13 to 19) + 3 electives (20A, 20B, 20C) | 135 | 599 |

Checks done: the module list in each paper's weight table equals the chapters found in the body for all 22 papers, and sub-item numbering has no gaps. Chapters without sub-items are real: the source lists only the module title (for example Linear Programming, Duty Drawback).

### CS (ICSI, Syllabus 2022)

| Level | Papers | Chapters | Topics |
| --- | --- | --- | --- |
| Foundation (CSEET, 4 parts) | 4 | 24 | 178 |
| Executive (Group 1: papers 1 to 4, Group 2: papers 5 to 7) | 7 | 122 | 776 |
| Professional (Group 1, Group 2, electives 4.1 to 4.6 and 7.1 to 7.5) | 16 | 261 | 1,818 |

Lessons ICSI marks as deleted from the Executive Programme are left out and listed in the scheme notes; Part headings and marks are in `section`.

### CA (ICAI, new scheme NSET)

| Level | Papers | Chapters | Topics |
| --- | --- | --- | --- |
| Foundation | 4 | 46 | 158 |
| Intermediate (Group I, Group II) | 6 | 50 | 357 |
| Final (Group I, Group II) | 6 | 66 | 290 |
| Self-Paced Online Modules (Sets A to D) | 16 | 142 | 673 |

Source: the 36 paper PDFs the founder downloaded from ICAI (kept in `docs/syllabus-sources/ca/`, links in `docs/syllabus-sources/ca-pdf-links.json`); the ICAI site cannot be fetched automatically from this workspace. Chapter = numbered content item, topic = sub-item (deeper levels read "Parent: item"), Section or Part with marks in `section`. Papers published as two PDFs (Intermediate Taxation and FM & SM, Final Indirect Tax Laws, Set D Psychology & Philosophy) are merged into one paper.

Review points: Intermediate Paper 1 chapter 3 and Final Paper 4 chapter 1 have no title in the source (names derived); Intermediate Paper 2 lists the Companies Act chapters as one numbered item, so they are topics of "The Companies Act, 2013"; Final Paper 3 notes ("covered in depth at Intermediate level") are not loaded; Final Paper 6 chapters are the seven subjects it integrates, without topics; prose-only chapters were split on commas or semicolons into topics, so check a few against the PDF.

### Elective papers

CMA Final has one elective to choose from 20A, 20B and 20C. CS Professional has one elective for Paper 4 (six options) and one for Paper 7 (five options). CA has none in NSET. Students choose in onboarding (an Electives step, shown only for these levels, with "I will decide later") and can change it on the syllabus map. Coverage counts only the chosen option: the other options are excluded through the existing exclusion ledger, progress in them is kept, and a slot with no choice counts nothing until chosen. Tests: `coverage/tests/test_electives.py` (slot derivation, create with choices, change of choice, pending state, invalid choices, carry-over on scheme switch, rebuild, export and delete).

## 5. Marks and weights

CMA chapters carry the module weight from the syllabus table (`weight_source = official`, 150 chapters). Where the table gives one weight for a group of modules, or only the section total, the rest of the section weight is split evenly and marked `analysis` (indicative). CS and CA have no per-chapter weights in the sources, so those stay empty (`unknown`).

## 6. Things to review in Django admin

1. Every scheme loads as a draft. Open Syllabus, Schemes, check papers and chapters, then publish.
2. Chapters with the `analysis` weight source: confirm or edit.
3. CS Professional Paper 1 chapters 19 and 20 and Elective 7.3 chapter 9 have no title in the source; their names were derived from their bullets.
4. CS Elective 4.5 (Advanced Direct Tax) has no bullets in the source; its topics came from splitting running text.
5. Exam terms are now per level. Dates are loaded only where announced and reported: CA Foundation 3 to 9 Jan 2027, CA Intermediate 2 to 12 Jan 2027, CMA Foundation 13 Dec 2026, CMA Intermediate and Final 10 to 17 Dec 2026. Check them against the institutes' schedules; other terms (CA May and September 2027, CMA June and December 2027, all CS terms) have no dates yet, and CS terms are still the same three for every level.

## 7. Still open

Code (student features, from section 3): chapter map links only equal keys (FR-5); per-course and per-chapter OG images and `/courses` still read the static catalog (FR-6); drag and drop ordering (FR-8); report-a-wrong-item link on level pages and `/app/syllabus` screens (FR-10); chapter targets editable only on the full admin form (FR-17); subject screen ignores `?view` (FR-23); switch summary shows counts, not lists (FR-28); API not gated by the feature flag (FR-30); no test asserts RLS; no persisted offline queue; no web component tests for the elective step and picker; `electives_chosen` analytics event is not in the PRD event table.

Content and data: CA and CS chapters have no marks; term dates for CS and for later CA and CMA attempts; admin review of the derived chapter names and split topics listed above; CA Final Paper 3 notes not loaded.

Operations: run `migrate` (coverage `0002`, syllabus `0006` to `0008`), `load_syllabus_seed --prune-legacy`, review and publish drafts, run `pnpm check` (vitest) on a Mac.
