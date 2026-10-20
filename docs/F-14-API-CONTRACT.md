# F-14 Amendments: API contract (Wave 3)

What `/api/v1/amendments/` answers. The web workspace and public SEO pages build against this file. It is checked by `modules/amendments/tests/test_contract.py`: if the code and this page disagree, that test fails, so change both together. PRD section 6 and ERD section 3 are the source.

## Rules for every endpoint

- Bearer Supabase token for student endpoints (`me/*`, `cards/*` except report). No token or bad token: `401`.
- Flag `amendments` off: `403` with code `feature_disabled` on authenticated student endpoints (`me/*`, `cards/*`, `chapters/*`). `me/data/` (erasure) and `me/export/` (export) are always allowed. Public endpoints (`public/*`) are unauthenticated and never behind the flag.
- Errors have one shape: `{"error": {"code", "message", "details"}}`.
- Public endpoints never expose `evidence_quote`, `anchor`, or internal ingestion tracking fields.
- Throttle scopes: `amendments_read` 120 per minute, `amendments_state` 120 per minute, `amendments_bulk` 10 per minute, `amendments_report` 10 per day, `amendments_public` 120 per minute.

## Endpoints

<!-- contract:endpoints -->

| Method | Path | Purpose | Throttle |
| --- | --- | --- | --- |
| GET | `me/summary/` | Summary of applicable amendments, review progress, and breakdowns | `amendments_read` |
| GET | `me/cards/` | Student's applicable and archive cards with filters, search, and pagination | `amendments_read` |
| GET | `me/cards/<str:public_id>/` | Card detail with student review state and affected chapters | `amendments_read` |
| GET | `me/archive/` | Term archive with document and card counts for the student | `amendments_read` |
| DELETE | `me/data/` | DPDP central account erasure: deletes student card interaction states | none |
| GET | `me/export/` | DPDP central account export: exports student card interaction states | none |
| POST | `cards/<str:public_id>/reviewed/` | Mark card as reviewed or unreviewed | `amendments_state` |
| POST | `cards/<str:public_id>/saved/` | Mark card as saved or unsaved | `amendments_state` |
| POST | `cards/bulk-reviewed/` | Bulk mark cards as reviewed | `amendments_bulk` |
| POST | `cards/<str:public_id>/report/` | File an editorial or error report on a card | `amendments_report` |
| GET | `chapters/<uuid:chapter_id>/` | Live cards mapped to a specific chapter for embed panel | `amendments_read` |
| GET | `public/hub/` | Latest documents and courses overview | `amendments_public` |
| GET | `public/documents/<slug:slug>/` | Single document details, revision history, and cards | `amendments_public` |
| GET | `public/cards/<str:public_id>/` | Single public card detail with verification notice | `amendments_public` |
| GET | `public/sitemap/` | Sitemap entries with lastmod for public pages | `amendments_public` |
| GET | `public/<str:course_code>/<str:level_code>/` | Level hub with available terms and papers | `amendments_public` |
| GET | `public/<str:course_code>/<str:level_code>/<str:term_code>/` | Term archive with cut-off dates, papers, and documents | `amendments_public` |
| GET | `public/<str:course_code>/<str:level_code>/<str:term_code>/<str:subject_key>/` | Paper amendments grouped by chapter | `amendments_public` |

<!-- /contract:endpoints -->

## Contract Keys

### My Summary Keys
<!-- contract:keys:my_summary -->
target_term, total_cards_count, reviewed_count, saved_count, breakdown_by_paper, breakdown_by_type
<!-- /contract:keys:my_summary -->

### My Card Keys
<!-- contract:keys:my_card -->
public_id, card_key, change_type, law_label, provision_label, title, summary_old, summary_new, effective_text, source_page, materiality, revision_effect, subject_key, applicability, is_reviewed, is_saved, is_updated, document, mappings
<!-- /contract:keys:my_card -->

### Public Card Keys
<!-- contract:keys:public_card -->
public_id, card_key, tombstone, status, change_type, law_label, law_key, provision_label, title, summary_old, summary_new, effective_text, effective_from_term_code, source_page, materiality, document, terms, chapters, notice
<!-- /contract:keys:public_card -->

### Public Document Keys
<!-- contract:keys:public_document -->
slug, title, short_title, issuer_label, kind, course, level, revision_no, issued_on, official_url, terms, papers, notice
<!-- /contract:keys:public_document -->

### Forbidden Public Fields (Privacy Leak Assertion)
<!-- contract:forbidden_public_fields -->
evidence_quote, evidence_hash, anchor, ingestion_item_id, ingestion_item_version_id, provenance_snapshot_id, reviewed_by, released_by, checks, extraction, diff_summary
<!-- /contract:forbidden_public_fields -->
