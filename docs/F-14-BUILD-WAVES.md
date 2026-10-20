# F-14 Amendments: Build Waves

Source:
- `docs/product/prd/F-14-amendments.md`
- `docs/product/erd/F-14-amendments.md`
Written: 2026-10-19. R1 delivers the standalone statutory amendments engine (`amendments`), term and paper applicability, change cards, student dashboard, public SEO pages, and coverage integration.

---

## 0. What the repo already has, and how that shapes the plan

| Finding | Effect on the plan |
| --- | --- |
| `X-04` Ingestion scraping pipeline is not yet built. | **F-14 is completely standalone.** Provenance is stored by value (`ingestion_item_id`, `provenance_snapshot_id`) as defined in ERD section 0. Staff review, draft staging, and release work directly via the Django admin, management seed commands, and services. When X-04 is built later, it registers F-14's `AmendmentChangePublisher` without modifying F-14 schema or UI. |
| `core/events.py` is a synchronous event bus with JSON Schema contracts in `apps/api/core/event_schemas/`. | Standardise event schemas: `amendment_published.v1.json`, `amendment_corrected.v1.json`, `amendment_retracted.v1.json`. |
| `apps/api/modules/syllabus` provides complete CA, CS, and CMA taxonomy. | F-14 links directly to `syllabus.Course`, `Level`, `Subject`, `Chapter`, `Topic`, `Scheme`, and `ExamTerm`. |
| `apps/api/modules/coverage` tracks student enrollment and chapter progress. | In Wave 5, coverage subscribes to `amendment_published` to flag started chapters as "Needs re-read" without changing progress percentages. |
| `src/lib/offline-queue` exists for client-side offline persistence. | Student review actions ("mark reviewed", "bookmark") queue with scope `amendments` and sync idempotently on reconnect. |
| PostHog flag `amendments`. | Fail-closed for authenticated student routes (403 `feature_disabled`); public SEO and marketing pages remain accessible. |

---

## 1. Waves (R1 Scope)

Each wave is independently shippable: automated tests green, behind the flag, nothing student-visible until its flag is on.

| Wave | Slices | Delivers | Exit check |
| :--- | :--- | :--- | :--- |
| **W1 Models & Pure Domain (API)** | F-14 S1, S2 | `amendments` app with schema (`Amendment`, `Revision`, `RevisionSubject`, `RevisionTerm`, `Change`, `ChangeVersion`, `ChangeMap`, `CardState`, `AuditLog`), pure domain logic (`applicability.py`, `card_key.py`, `checklist.py`), admin models, constraints and RLS tests. | `pytest apps/api/modules/amendments` green; migrations apply cleanly; pure domain applicability and card key tests pass. |
| **W2 Life-cycle Services & Seed (API)** | F-14 S4, S6 | Services (`create_draft`, `stage_card`, `release_revision`, `reissue_document`, `retract_revision`, `correct_revision`), atomic release under row lock, `seed_amendments` management command, event schemas. | Concurrency release test passes; seed command idempotently populates CA Inter/Final sample amendments; event schemas validate. |
| **W3 Read API & Public Contract (API)** | F-14 S5, S7, S9 | Selectors (student `my_amendments`, public listings, chapter amendments), student actions (`reviewed`, `saved`), public views, allow-list privacy leak test, `docs/F-14-API-CONTRACT.md` with drift test. | 401/403/404/200 matrix verified; public endpoints never leak evidence quotes; contract drift test green. |
| **W4 Web Student Experience** | F-14 S10 | Web module `apps/web/src/modules/amendments`, TypeScript twin `applicability.ts`, components (`ChangeCard`, `ApplicabilityFilter`, `GroupingTabs`, `OfficialPdfButton`), `/app/amendments` dashboard, `/app/amendments/$cardId`, offline queue integration. | `pnpm check` and `pnpm check:contrast` green; all 4 themes verified at 320 to 1280 px; offline actions sync cleanly. |
| **W5 Public SEO, Coverage & Launch** | F-14 S8, S11, S14 | Public routes (`/amendments/...`), OG cards (`/og/amendments/...`), JSON-LD, coverage subscriber for "Needs re-read" flags, account erasure registry (`core.registry`), catalog feature entry live, `docs/F-14-ROLLOUT.md`. | Full repo check (`pnpm check`, `pnpm lint:api && pnpm test:api`) green; catalog flipped to live; beta runbook written. |

---

## 2. Open Items for the Owner

| Item | Needed by | Notes |
| --- | --- | --- |
| Create PostHog flag `amendments` at 0% | Wave 2 | Fail-closed on API student endpoints. |
| Run `python manage.py migrate` | Wave 1 | Applies migration `amendments.0001`. |
| Review seeded amendments | Wave 2 | Verify against official ICAI/ICMAI publications in Django admin. |
| Legal notice review | Wave 5 | Confirm standard non-affiliation and source disclaimer before public launch. |
