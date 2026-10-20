# F-14 Amendments Engine: Rollout & Operations Runbook

## 1. Feature Overview

The **F-14 Amendments Engine** provides an end-to-end statutory and academic amendment tracking pipeline for CA, CS, and CMA examination preparation. It breaks complex statutory documents (e.g. ICAI revision test papers, statutory updates, Ministry gazettes) into discrete **Change Cards** mapped directly to individual syllabus chapters and examination attempts.

---

## 2. Architecture & Components

```
                ┌────────────────────────────────────────────────┐
                │          Student Workspace & Public Web        │
                │ (/app/amendments, /amendments, /og/amendments) │
                └───────────────────────┬────────────────────────┘
                                        │ HTTPS / API
                                        ▼
                ┌────────────────────────────────────────────────┐
                │          Django REST Framework Layer           │
                │ (Throttled, Flag-guarded, DPDP-compliant)      │
                └───────┬───────────────┬────────────────┬───────┘
                        │               │                │
                        ▼               ▼                ▼
                 [ Views & URLs ]  [ Selectors ]   [ Services ]
                        │               │                │
                        ▼               ▼                ▼
                 [ Domain Rules: Applicability, CardKey, Checklist ]
                                        │
                                        ▼
                 [ Models & Migrations (PostgreSQL + RLS) ]
                                        │
                                        ▼
                 [ Outbox Events: Published, Corrected, Retracted ]
```

### Key Modules:
- **Backend**: `apps/api/modules/amendments/`
  - `models.py`: `Amendment`, `Revision`, `Change`, `ChangeVersion`, `ChangeMap`, `StudentCardState`, `CardReport`
  - `domain/`: `applicability.py` (PRD 5.3 attempt decision tree), `card_key.py`, `checklist.py`
  - `services.py`: Lifecycle transitions, ingestion, 4-eye editorial approval, revision publishing, DPDP erasure/export
  - `selectors.py`: Student workspace projections (`my_summary`, `my_cards`, `my_archive`), chapter embeds, public SEO projections
  - `public_serializers.py`: Strict leak-proof serializers guarded by `assert_no_leaks`
  - `management/commands/seed_amendments.py`: Deterministic seed data loader
- **Frontend**: `apps/web/src/modules/amendments/`
  - `lib/applicability.ts`: Pure TypeScript twin of the domain applicability engine
  - `lib/api.ts`: API client with `writeOrQueue` offline queue resilience
  - `containers/`: `AmendmentsShell`, `MyAmendmentsContainer`, `MyCardDetailContainer`, `ArchiveContainer`, `PublicAmendmentsHubContainer`, `PublicDocumentContainer`, `PublicCardDetailContainer`
  - `routes/`:
    - `/app/amendments/`: Student amendments hub
    - `/app/amendments/$cardId`: Student amendment detail
    - `/app/amendments/archive`: Student historical term archive
    - `/amendments/`: Public SEO hub
    - `/amendments/documents/$slug`: Public document view
    - `/amendments/cards/$publicId`: Public change card view
    - `/og/amendments/$cardId`: Dynamic server-side OpenGraph preview card
    - `/sitemap.xml`: Merged public sitemap including all live amendment paths

---

## 3. Operational Safety, Security & Compliance

1. **Fail-Closed Feature Flag**:
   - PostHog flag: `amendments`
   - Frontend: `useFeatureFlag('amendments', { strict: true })`
   - Backend: `check_amendments_flag` (answers `403` with code `feature_disabled` on student endpoints).
   - Public SEO routes remain unauthenticated and accessible without leaking private fields.

2. **Row-Level Security (RLS)**:
   - Tenant isolation enforced on `StudentCardState` and `CardReport`.
   - Verified by `apps/api/core/tests/test_row_level_security.py`.

3. **Privacy & Anti-Leak Guarantees**:
   - `evidence_quote`, `anchor`, internal ingestion IDs, reviewer IDs, and editorial checks are **never** exposed on public endpoints.
   - Verified by `test_contract.py::TestContractGuarantees::test_public_card_never_leaks_forbidden_fields`.

4. **DPDP Statutory Compliance**:
   - `DELETE /api/v1/amendments/me/data/`: Central erasure of student review states.
   - `GET /api/v1/amendments/me/export/`: Central export of student review states.

5. **Offline Queue Resilience**:
   - `reviewCardOrQueue` and `saveCardOrQueue` queue mutations locally when offline and synchronize upon reconnection via `writeOrQueue`.

---

## 4. Rollout Checklist

### Phase 1: Database & Migrations
- [x] Run database migrations:
  ```bash
  cd apps/api && python manage.py migrate
  ```
- [x] Verify RLS tables and policies:
  ```bash
  python -m pytest apps/api/core/tests/test_row_level_security.py
  ```

### Phase 2: Seed & Ingest Statutory Packages
- [x] Seed amendments:
  ```bash
  python manage.py seed_amendments
  ```
- [x] Verify 4-eye verification states and live revision links in Django admin.

### Phase 3: Contract & Backend Testing
- [x] Execute complete backend test suite:
  ```bash
  pytest apps/api/modules/amendments
  ```
  *(All 39 tests passing: models, domain, services, selectors, views, contract, zero-drift, zero-leak).*

### Phase 4: Web Workspace & Public Verification
- [x] Web TypeScript typecheck:
  ```bash
  pnpm --filter @artha/web typecheck
  ```
- [x] Web vitest suite:
  ```bash
  pnpm --filter @artha/web test
  ```
- [x] WCAG Contrast checks:
  ```bash
  pnpm check:contrast
  ```

### Phase 5: Phased Traffic Release (PostHog)
1. Keep `amendments` flag at `0%` during initial deploy.
2. Enable internal dogfooding (`amendments` = `true` for staff/admin user IDs).
3. Verify student interactions:
   - Marking cards as reviewed
   - Bookmarking cards
   - Submitting error/drift reports
   - Bulk reviewing papers
4. Scale rollout: 10% -> 25% -> 50% -> 100%.

---

## 5. Maintenance & Troubleshooting

- **Handling Errata / Reissues**:
  - Use `services.stage_reissue(document_id, ...)` to create a new revision.
  - Review and publish via `services.publish_revision(revision_id, ...)`.
  - Prior published cards will automatically receive `is_updated = True` notice for students who had already reviewed the prior version.
- **Reporting Inaccuracies**:
  - Student reports arrive via `POST /amendments/cards/<id>/report/` and are logged in `CardReport` for CA editorial review.
- **Cache Invalidation**:
  - Public endpoints use HTTP cache headers (`Cache-Control: public, s-maxage=120` for documents/cards, `s-maxage=3600` for sitemap).
