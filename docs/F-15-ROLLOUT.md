# F-15 Flashcards and Spaced Revision, release R1 (flag `recall_system`): build and rollout runbook

Status: written 2026-10-09, **waiting for owner approval; no F-15 code exists yet** (Wave 0 below is the only code changed, and it is a prerequisite fix, not F-15).
Specs: `docs/product/prd/F-15-recall-system.md` (the PRD), `docs/product/erd/F-15-recall-system.md` (the ERD). This file says in what order R1 is built, what each wave changes, how it is proved, how it is rolled back and what you must arrange. R2 (quick revision, sharing, AI, deck sync) and R3 (parameter fit) are not in this file.

R1 ships: seven card kinds, FSRS-6 as a pure versioned function in Python and TypeScript with shared golden vectors, an append-only idempotent review log, the review player (keyboard, swipe, undo, edit in place), daily limits, catch-up, rebalance, vacation, early review, forgotten list and leech notices, stats, platform decks edited in Django admin (copy-on-subscribe), offline review, export and delete-all, and the Notes provider (`create_card_from_source`, `cards_for_source`). **Not in R1:** AI (`recall_ai`), sharing (`recall_sharing`), quick revision and exam horizon, deck update sync (R2), the Notes "highlight to card" button, the F-13 Today registration (`provide_today` exists as a selector, nothing registers it), billing.

## 0. Status check (verified 2026-10-08, against the code)

| Item | State |
| --- | --- |
| Notes R1 to R3, `core/recall_port.py` (+ its use in `modules/notes`, 503 `recall_unavailable`, `capabilities.recall`) | Present |
| `core/jobs` + worker + 5-minute tick, `core/registry.py` (erase and export), `core/feature_flags.py` (strict mode), base classes in `core/errors.py` and `core/permissions.py`, Sentry `before_send` scrubbing, syllabus selector extensions, `src/lib/offline-queue`, coverage selectors (`get_active_enrollment`, `exam_date_of`, `due_for_revision`) | Present |
| `core/richtext` `card` profile (and its web twin) | **Missing, fixed in Wave 0** |
| Flag lookup failure caching and `CACHES` (AUD-003, W0L.2) | **Missing, fixed in Wave 0** |
| Design-system `RatingButtons`, `FlipCard`, `ProgressCounter`, `DatePicker` | Absent (built in Wave 7) |
| Billing selector | None. `plan_code_for` is a stub inside `notes/services/quota.py` (recall may not import notes); Wave 3 adds `core/plans.py` |
| F-13 Today, coverage `recall` source value | Absent, by design (R1 does not need them) |
| `core.events` | Synchronous in-memory `subscribe(name, fn)` / `emit(name, **payload)`; the ERD's `register_subscriber(..., mode=)` signature does not exist. R1 emits `recall_session_completed`, `recall_leech_detected` through the stand-in; no subscriber is registered yet |
| Worker host | `fly.toml` and `render.yaml` both exist; R1 adds **no** job type and does not touch the worker |

## 1. Decisions

Taken by you on 2026-10-08/09:

| Id | Decision |
| --- | --- |
| Q-F15-1 | FSRS-6, `scheduler_version = "fsrs-6.0"` |
| Q-F15-3 | Study day starts 04:00 in the student's time zone, `day_start_hour` configurable 0 to 6; the tracker is unchanged |
| Q-F15-4 | Two pilot subjects, about 12 chapters, 40 cards each, written by your editors in our own wording (`rights_status = original`). We ship the loader, a template and one example seed, not the content |
| Q-F15-5 | Free plan limits from PRD 8.3: 1,500 own cards, 500 cards per deck, 100 decks, offline pack 300. A `pro` row is seeded (20,000 / 2,000 / 500 / 500) and unused until billing exists. Reviewing is never limited |
| Q-F15-9 | Recall streak: a study day counts at 5 or more reviews, or when the planned queue was cleared; vacation days neither count nor break it; separate from the tracker streak |
| Q-F15-10 | 10 new cards a day (0 to 100). "Unlock with coverage" is stored as the subscription default, but the coverage gate is R2: in R1 every subscribed card is offered under the daily cap |
| Q-F15-11 | Early review: when all caught up, "Review ahead 10 cards", lowest retrievability first, logged as `mode = review_ahead` |
| Tests | Golden vectors shared by both languages, property tests, and an oracle against `py-fsrs` and `ts-fsrs` in dev only (never runtime; skipped when not installed) |
| Other | R1 only, behind `recall_system` (fails closed), closed beta, counsel review deferred (no student content is shared in R1) |

Taken by me, to confirm when you approve this file (each is small and reversible):

| Id | Decision | Why |
| --- | --- | --- |
| D1 | Plans are read through one function, `core.plans.plan_code_for(user_id)` (default `free`, a provider can be registered, the same shape as `core.recall_port`). Recall reads limits from `recall_quotaplan` by that code, never from constants. Notes is left alone; billing later points both at the same function | The billing plan says `plan_code_for` becomes `billing.selectors.active_plan`. One seam, no recall change |
| D2 | The port's kinds (`formula, rule, definition, example, doubt, fact`) are Notes vocabulary. The provider maps them to F-15 kinds: `formula` to formula, `definition` to definition, `rule` to section-less pointer, `example`, `doubt`, `fact` to pointer. The port kind is stored on the item (`origin_kind`) so idempotency is exactly `(user, source ref_id, port kind)` and also on `client_id` | The ERD has no column for it. This adds `recall_item.origin_kind` and one partial unique index |
| D3 | Recall has its own light tick, `POST /api/v1/recall/internal/tick/` (header `X-Recall-Tick-Secret`, env `RECALL_TICK_SECRET`, may equal the notes secret). It auto-closes sessions idle 60 minutes. The 5-minute scheduler you already run for notes calls both URLs | Keeps R1 off `core_job` and the worker |
| D4 | Data export and delete-all stay open with the flag off (as Notes does, DPDP); every other endpoint answers 403 `feature_disabled`. The parametrised flag test lists exactly these two exceptions | PRD FR-F15-74 says "every endpoint"; erase and export must never be blockable by a rollout switch |
| D5 | On SQLite (unit tests) `recall_reviewlog` is created as an ordinary table with the same columns; on Postgres it is hash partitioned with the immutability trigger. Partition, trigger, RLS and concurrency tests are Postgres-only and skip on SQLite. I can run Postgres 17 in the build sandbox (own data directory under `/tmp`), so these tests do run here before each wave closes | Services stay testable everywhere; the guarantees are tested where they exist |
| D6 | Deterministic fuzz seed is FNV-1a (32-bit) over the UTF-8 bytes of `"{card_id}:{reps}"`, mapped to a factor in [-1, 1); identical in Python and TypeScript, pinned by vectors. Oracle tests against the libraries run with fuzz off | The libraries' fuzz is random; ours must replay |
| D7 | Time rules for parity: all instants are UTC; `elapsed_days` is whole days (floor) between the previous counted review and now, as py-fsrs; intervals are rounded half up to whole days, clamped to `[1, max_interval_days]`; stability and difficulty are doubles in the domain and rounded to `real` only on write | One rule, in `domain/limits.py` and `lib/limits.ts` with a parity test |
| D8 | `py-fsrs` is added to `requirements-dev.txt` and `ts-fsrs` to `apps/web` devDependencies (one `pnpm-lock.yaml` change). Neither is imported by runtime code | Oracle only |
| D9 | List columns (`tags`, `reference_keys`, `flags`, `learning_steps_min`, `relearning_steps_min`, `weights`) are JSON lists, not PostgreSQL arrays. The repo has no array columns and its quick tests run on SQLite. The two searched lists get `jsonb_path_ops` GIN indexes on PostgreSQL; the 21-weight length check is a PostgreSQL check constraint plus the domain validator | Same data, one schema on both databases | 

## 2. How each wave is worked

One change set per wave, in this order; each ends with a short report and a "for you to do" list. Every wave: `ruff check . && ruff format --check .` and `pytest` (SQLite, `DJANGO_DEBUG=true`) in `apps/api`; for web waves `pnpm typecheck`, `eslint --max-warnings=0`, `prettier --check`, `vitest` and `build` run in a scratch copy under `/tmp` (the mounted `node_modules` is macOS-only), with changed module files rsynced back; Postgres tests run against a private Postgres in `/tmp` where the wave touches the database. Nothing is committed or pushed; I propose a Conventional Commit message per wave (scopes `api`, `web`, `ds`, `docs`, `db`) with the trailers. Docs, `docs/BUILD-TRACKER.md`, `apps/api/.env.example` and `docs/SETUP.md` are updated in the wave that changes them.

| Wave | Content | PRD slices | Size |
| --- | --- | --- | --- |
| W0 | Prerequisite fixes (done) | | small |
| W1 | Pure Python domain: scheduler, folding, queue planning, kinds, cloze, limits, golden vectors | 1, 2, part of 6 | large |
| W2 | TypeScript twin of the same, same vectors | 3 | medium |
| W3 | Schema, migrations, plans seam, quotas, RLS, partitioned log | 4, 5 | medium |
| W4 | Card services, endpoints, kind registry, Notes provider | 6, 12 | large |
| W5 | Review services: submit, batch, undo, replay, sessions, rollups, events, tick | 7 | large |
| W6 | Read side: today, queue, pack, forgotten, stats, settings, `provide_today` | 8 | medium |
| W7 | Design-system components | 9 | medium |
| W8 | Web lib: offline store, sync, hooks | 10 (part) | large |
| W9 | Web screens: hub, review player, summary, stats, settings | 10 (part) | large |
| W10 | Cards browser, creator, detail, bulk, duplicate warning | 11 | medium |
| W11 | Platform decks: admin editor, publish, seed loader, subscribe, library UI, reports, export and erase | 13 | large |
| W12 | End-to-end script, capacity note, privacy checks, docs, tracker, close-out | | medium |

## 3. Waves

### W0. Prerequisite fixes (done 2026-10-09)

- `core/richtext.py`: profile `CARD` (4,000 characters, no images, no headings, no rules, no task lists, tables up to 10 rows by 6 columns, up to 40 formulas of 1,000 characters). Twin in `apps/web/src/lib/richtext/profiles.ts` (`'card'`). Seven corpus cases in `core/tests/richtext_cases.json`. Python 107 tests and web 105 tests green.
- `core/feature_flags.py`: a failed PostHog lookup is now remembered for 15 seconds (AUD-003), so an outage costs one slow call per student per interval instead of one per request. A flag that fails closed (`strict=True`, `recall_system`) therefore answers fast during an outage. Tests updated and one added.
- `config/settings.py`: explicit `CACHES` (local memory). Nothing correctness-critical lives there.
- Not done on purpose: `NUM_PROXIES` for throttles (affects every module; separate change). Throttles stay per instance, as the ERD accepts; quotas are database facts.

### W1. Pure domain (Python) (done 2026-10-09)

Files in `apps/api/modules/recall/domain/` (no Django imports): `fsrs6.py` (`retrievability`, `interval_days`, `review`, `preview`, `cap_stability`, bounds check of the 21 weights), `folding.py` (`fold` over reviews and schedule events in `(time, kind order, id)` order, ignoring voided and `counts_for_scheduling = false`), `scheduling.py` (`plan_queue`, `catchup_state`, `days_to_clear`, `priority`, `forgetting_score`, `streak`, `forecast`, plus the R2 helpers `horizon`, `r_exam`, `quick_set`, `pacing` only as stubs that raise `NotImplementedError` so R2 has a place; they are not wired), `cards.py` (kind specs and field validators for the seven kinds, `render`, cloze parser with `{{c1::text::hint}}`, `suggest_kind`, `fingerprint`), `limits.py` (every constant of ERD section 4).
Tests (`domain/tests/`): golden vectors `vectors/fsrs6_cases.json` (at least 40: first review of each rating, learning steps, graduation, review-state Again/Hard/Good/Easy at several retrievabilities, same-day reviews, relearning, max interval, fuzz on and off), `folding_cases.json`, `queue_cases.json`; property tests with Hypothesis (incremental application equals `fold` under 200 random orders with duplicates and undos; interval monotone in rating and in stability); oracle test against `py-fsrs` on 10,000 random histories (state within 1e-6, equal intervals, fuzz off), skipped with a clear message when the library is absent.
Vectors are generated by a checked-in script that runs `py-fsrs` for the rows where both agree and our own code for the fuzz rows, then reviewed; the file is the contract the TypeScript twin must pass.
Exit: all green, `recall_check_vectors` (added in W5) can run them.

### W2. Pure domain (TypeScript twin) (done 2026-10-09)

`apps/web/src/modules/recall/lib/`: `fsrs6.ts`, `folding.ts`, `queue.ts`, `cloze.ts`, `render.ts`, `kinds.ts` (field forms), `limits.ts`. The vector files are the same bytes as the API's (a copy at `apps/web/src/modules/recall/lib/vectors/` and a test that fails if the two differ, so no cross-package import). Vitest runs every vector, a parity test for `limits.ts`, a property test for fold equals incremental, and an oracle test against `ts-fsrs` (dev dependency, fuzz off).
Exit: same 40+ vectors give the same state within 1e-6 and the same intervals in both languages.

### W3. Schema, plans and quotas (done 2026-10-09)

- `core/plans.py` (D1) and `recall_quotaplan` (rows `free`, `pro`), `modules/recall/services/quota.py` in the notes pattern: one conditional `UPDATE` per reservation (cards, decks, cards per deck), never read then write; usage counters in `recall_quotausage`; reconcile command later. Reviewing is never limited.
- Migrations (ERD section 8): `0001_content` (item incl. `origin_kind`, itemversion, deck, deckversion, deckversionitem, deckitem), `0002_student_state` (params + default row equal to py-fsrs defaults, settings, subscription, card, session, scheduleevent, quotaplan seed), `0003_reviewlog` (partitioned on Postgres, plain on SQLite; `managed = False` model; indexes; trigger `recall_reviewlog_immutable` with `recall.replaying` and `recall.erasing`), `0004_rollups` (daily and chapter rollups, auditlog). Sharing, report and AI tables are created in R2, not now (the ERD's `0004` bundles them; I split it so R1 ships no dead tables except `recall_report`, which FR-F15-52 needs, so that one is in `0004`).
- Post-migrate RLS already runs on every public table; a new test asserts `relrowsecurity` on each `recall_*` table and on all 16 partitions.
Tests: constraint tests (every enum check, `(state = 0) = (stability is null)`), partition routing and trigger (delete refused, fact update refused, derived columns updatable only under `recall.replaying`, delete allowed under `recall.erasing`), RLS, default weights equal the library's. Postgres-only tests skip on SQLite and are run on the private Postgres.
Built: `0001_content`, `0002_student_state` (seeds `default` params and the `free` and `pro` plans), `0003_reviewlog` (DDL in `modules/recall/reviewlog_sql.py`), `0004_rollups` (rollups, report, audit log). `services/log_guard.py` has the `replaying()` and `erasing()` switches; they reset themselves because `SET LOCAL` outlives a savepoint. `QuotaExceeded` moved to `core.errors` (Notes keeps its own copy for now). Chapter rollup uniqueness is two partial indexes instead of `coalesce`, so SQLite and PostgreSQL agree.
Rollback: drop the `recall_*` tables; nothing else changes.

### W4. Cards: services, endpoints, provider

`modules/recall/`: `registry.py` (`register_card_kind`), `adapters/` (`syllabus.py`, `coverage.py`; selectors only, never foreign models; a test greps that no `recall` file imports `modules.<other>.models`), `services/cards.py` (`create_card` idempotent on `(user, client_id)` with duplicate warning and `force`, `create_card_from_selection` as a thin wrapper, `update_card` with `base_rev` and 409 `edit_conflict`, `set_card_status`, `bulk_update` all or none up to 200, soft delete with 10-second undo token), `selectors/cards.py`, serializers, views, `urls.py`, throttles (`recall_review` 600/min, `recall_write` 120/min, `recall_export` 6/hour), flag permission `flag_required("recall_system", strict=True)`, errors from `core`.
Provider: `RecallProvider` registered in `RecallConfig.ready()` through `core.recall_port.register_recall_provider`; `create_card_from_source` (D2) and `cards_for_source`. Notes then reports `capabilities.recall = true` and "Make a card" works; no Notes UI is edited. Note for you: this switches the Notes endpoint from 503 to live for anyone with the `recall_system` flag off too, because the port does not know the flag. The provider therefore checks the flag for that student and raises `RecallUnavailable` (Notes answers 503) when it is off, and `cards_for_source` returns `{}`.
Tests: every endpoint (401, happy, 400, other student's data is 404), kind validators, cloze, quota edge, idempotency on `client_id`, provider idempotency on `(user, ref_id, port kind)`, flag-off parametrised test (D4).

### W5. Reviews

`services/reviews.py` exactly as ERD 3.5: `submit_review` (idempotent insert `ON CONFLICT DO NOTHING`, row lock on the card, stale-content and late handling, fast path and replay path, rollups only for newly inserted rows, sibling burying, leech), `submit_reviews` (up to 100), `undo_review` (last 10 within 30 minutes, compensating event), `replay_card`, `open_session` and `close_session` (emits `recall_session_completed`), `rebalance`, `set_vacation`, `update_settings` (changing retention never reschedules), rollup maintenance with `INSERT ... ON CONFLICT DO UPDATE`. Endpoints `reviews/`, `reviews/batch/`, `reviews/undo/`, `sessions/`, `sessions/{id}/close/`, `catchup/rebalance/`, `vacation/`. The light tick (D3). Commands `recall_replay`, `recall_rebuild_rollups`, `recall_check_vectors`.
Tests: duplicate event is a no-op, late event replays, two devices rating one card equal the fold, clock skew clamp, 30-day cutoff, deleted card, stale content, undo, rollups incremental equals rebuilt after random sequences, **Postgres concurrency** (two concurrent reviews of one card, two batch syncs with overlapping ids), throttles named and tested, no card text in any log line (a log-capture test).
Exit: the append-only guarantees hold on Postgres; replay of a card from the log equals its stored state.

### W6. Read side

`selectors/`: `today.py` (`today_plan`: counts, mode normal/catchup/vacation, `days_to_clear`, `est_minutes`, kind tiles, forgotten top 5), `queue.py` (`build_queue` for sources `today`, `chapter`, `deck`, `forgotten`, `catchup`, `review_ahead`; `quick` and `cram` answer 422 `not_in_this_release`), `pack.py` (up to the plan's pack size, with weights, settings, counters, `pack_id`, `expires_at`), `forgotten.py`, `stats.py` (summary, retention, forecast, chapters, 60-second `ETag`), `cards.py`, plus `provide_today` returning the F-13 result shape locally defined as a dataclass (no import of F-13; nothing registers it) and `due_counts`, `recall_strength`. Endpoints `today/`, `queue/`, `pack/`, `forgotten/`, `stats/*`, `settings/` (GET, PUT with ranges).
Tests: `assertNumQueries` per endpoint with a 5,000-card fixture, catch-up thresholds, limits and "Do 20 more", interleaving, burying, GETs never write (a test counts writes), queue p95 target recorded by the capacity script in W12.

### W7. Design system

`packages/design-system/src/components/ui/`: `rating-buttons.tsx` (four equal buttons, label, interval preview, key hint, roving focus, `aria-keyshortcuts`, 44 px minimum), `flip-card.tsx` (front and back, reduced-motion crossfade of 0 ms, announces the change, swipe handlers with a button alternative), `progress-counter.tsx` (`aria-live="polite"`), `date-picker.tsx` (native input base, used for vacation end; exam date is R2). Exported from the barrel, added to the showcase, contrast tokens checked with `pnpm check:contrast`, tests for keyboard and ARIA. Icons only from the package.
Exit: all four themes, WCAG 2.2 AA, 320 to 1280 px without horizontal scroll (checked in the showcase by an automated test where possible, otherwise recorded as a checklist item you will not run manually, see section 6).

### W8. Web lib, offline and sync

`apps/web/src/modules/recall/`: `lib/eventStore.ts` (IndexedDB: pack, pending events up to 5,000, sessions; ordered, batched flush of 100), `lib/sync.ts` (per-event result codes, card replacement from responses, merge summary), `lib/api.ts` (typed, zod at the edge), hooks (`useTodayPlan`, `useQueue`, `useReviewSession` local-first, `useSync`, `useSettings`, `useCards`), server clock offset helper reused from the tracker pattern. Follows the persisted-queue pattern of `src/lib/offline-queue` but does not reuse its writer (ordering and volume differ, as the ERD says). Public barrel `index.ts`.
Tests (vitest, fake-indexeddb): offline session of 100 cards gives the same intervals as the server fold, 250 queued events flush in three batches, a dropped response retried creates no duplicates, quota of 5,000 events refuses new ones with a message, stale pack (older than 48 h) warning.

### W9. Web screens

Routes (thin): `/app/recall`, `/app/recall/review` (search params `source`, `chapter`, `deck`, `kind`, `tier`, `n`, session `s`), `/app/recall/review/summary/$sessionId`, `/app/recall/stats`, `/app/recall/forgotten`, `/app/settings/recall`; all `noindex`. Containers and presentational components per ERD 9. States: zero cards, all caught up, huge backlog (never a red giant number), vacation, offline, sync conflict, flag off, error, loading skeletons. Review player: keyboard (Space/Enter, 1 to 4, U, E, S, B, ?), swipe (left Again, right Good, always with buttons), bottom thumb controls, visual-viewport layout, first-time intro, honest-rating hint, leech chip, "Review ahead 10 cards". PostHog events from PRD 10.1 with an allow-list of properties (no card text); `useFeatureFlag('recall_system')` with the fail-closed rule.
Tests: component tests for each state, keyboard path completes a session, axe checks, event allow-list test.

### W10. Cards screens

`/app/recall/cards`, `/app/recall/cards/new` (prefill via `?kind=&chapter=&topic=&deck=&from=selection&draft=`), `/app/recall/cards/$cardId`: browser with filters in the URL and cursor pagination, bulk select, creator with the seven kind forms and live KaTeX preview, duplicate warning, field counters, offline save queued, edit with `base_rev` and the 3-way conflict dialog, card memory stats, review history, suspend, bury, reset, delete with undo toast.
Tests: form validation per kind, conflict dialog, duplicate flow, URL-driven filters.

### W11. Platform decks, export, erase

Django admin (`recall/admin.py`): item and version editor (change kinds, importance tiers, `rights_status`, `unknown` blocks publish, `source_label`), deck editor with draft versions, **atomic publish** (`publish_deck_version`: computes `change_vs_prev`, supersedes the old live version, a failure leaves the previous live version served), reports queue, quota plan editor, read-only views of cards and log (no card text of students). Permissions from `profiles.role` (scopes `recall.deck.author`, `recall.deck.publish`). `manage.py load_recall_seed [--publish]` (drafts, idempotent on `external_ref`), `seed/_TEMPLATE.json` and one example file clearly marked sample. Student side: `decks/library/`, `decks/{id}/subscribe/` (copy-on-subscribe in one transaction up to 500 cards, advisory lock, idempotent), unsubscribe (archive, progress kept) and resubscribe, report a platform item (FR-F15-52), `/app/recall/decks`, `/app/recall/decks/$deckId`. `services/erasure.py` (`delete_all_for_user`, `export_for_user`) registered in `RecallConfig.ready()` through `core/registry.py`; CSV exports of cards and reviews are streamed with a cursor and no silent cap. Pinned subscribers, follow-updates and diffs are R2: R1 subscribes at the live version and shows "A newer version exists" only as a count.
Tests: publish atomicity, rights gate, double-tap subscribe, resubscribe restores progress, export of 20,000 reviews is complete, erase leaves no row (cards, items, log through `recall.erasing`, sessions, rollups, settings), Postgres test for the advisory lock.
Exit: R1 core complete.

### W12. Close-out

`scripts/e2e/recall-r1/run.py` (functional check on Postgres: seed a deck, subscribe, review 200 cards online and 100 offline with two devices, undo, catch-up, rebalance, export, erase; exits 1 on any failure) and `capacity.py` (reviews/min, queue and pack latency at 5,000 cards, 8 concurrent reviewers; numbers are indicative), a capacity note in this file, the privacy checks (Sentry scrubbing test for `recall` routes, PostHog property allow-list, log capture), `.env.example`, `docs/SETUP.md`, `docs/BUILD-TRACKER.md` (new section for F-15 R1 and its owner tasks), CLAUDE.md product status line, the catalog entry left at `soon` until the flag is fully on, and `docs/F-15-API-CONTRACT.md` with the endpoint shapes.

## 4. Environment and flags

| Name | Where | Value |
| --- | --- | --- |
| PostHog `recall_system` | PostHog | create at **0%** before the first merge. Fails closed: a missing key, an unknown flag or an outage means off, on both API (`strict=True`) and web |
| `RECALL_TICK_SECRET` | API | long random value; empty means the tick refuses everyone (sessions then close only when the student closes them) |
| `RECALL_PACK_MAX` | API | upper bound on the offline pack, default 500 (the plan row decides the real size) |
| `RECALL_DEFAULT_WEIGHTS_VERSION` | API | `fsrs-6.0` |
| Throttles | `config/settings.py` | `recall_review`, `recall_write`, `recall_export` (new rates) |
| Web | | no new `VITE_*` values |

## 5. Rollback

Turn `recall_system` off: the web hides recall, every endpoint except data export and delete-all answers 403 `feature_disabled`, the Notes provider answers 503 for students whose flag is off, data stays intact. Stop the tick call: nothing breaks. Migrations are additive and touch no existing table; to remove the feature drop the `recall_*` tables and remove the app from `INSTALLED_APPS`. A scheduler bug is fixed by shipping `fsrs-6.1` and running `recall_replay`; the log is the source of truth, so no history is lost.

## 6. Risks

| Risk | Mitigation |
| --- | --- |
| Python and TypeScript drift | one vector file, byte-equality test, oracle tests, property tests; a CI failure on any difference |
| Replay or merge corrupts state | state is a cache of the log; `recall_replay`; random-order property tests; Postgres concurrency tests |
| Partitioned log is Postgres-only | D5; Postgres tests run here and in CI; SQLite stays usable for services |
| Wall of new cards after subscribing | 10 a day, catch-up, rebalance, vacation; coverage gating arrives in R2 |
| Dishonest ratings (Hard for forgotten) | first-session tip, hint under the buttons, rating split and true retention in stats |
| PostHog outage | flag errors cached 15 s (W0); review endpoints never wait on PostHog beyond that |
| Copyright of platform cards | our own wording, `rights_status` gate, no student content shared in R1; counsel review deferred by you, revisit before R2 sharing |
| No manual device checks (your standing rule) | automated component, keyboard and axe tests, the e2e script, the capacity note; fix on the first real report. Accepted risk, recorded here |
| Notes provider goes live on registration | flag-aware provider (W4) so Notes stays 503 for students outside the beta |
| Disk in the build sandbox | scratch copy under `/tmp`, one `node_modules`, private Postgres deleted after each wave |

## 7. What you must arrange (in order)

1. Approve this file, and say if any of D1 to D8 should change.
2. Create the PostHog flag `recall_system` at 0% before the first merge.
3. Editors for the two pilot subjects and Django admin accounts with the `profiles.role` that carries `recall.deck.author` and `recall.deck.publish` (before the beta, not before the build).
4. The closed beta list (the same 50 students as F-01, F-02, F-03).
5. A scheduler entry for `POST /api/v1/recall/internal/tick/` every 5 minutes, beside the notes tick (W5 gives the exact header and secret).
6. Run `pytest` once against your own Postgres before the flag goes up (the sandbox run is evidence, not a substitute), and the e2e script from your computer.
7. Counsel review of the copyright posture and the terms line for student-written cards: deferred, needed before R2 sharing.
