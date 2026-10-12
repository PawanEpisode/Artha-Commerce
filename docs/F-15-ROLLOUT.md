# F-15 Flashcards and Spaced Revision, release R1 (flag `recall_system`): build and rollout runbook

Status (2026-10-11): **R1 is built (waves W0 to W12 done) and verified by automated tests and two end-to-end scripts; it has not been run on your own Postgres, and no student can see it** (flag `recall_system` is fail closed and off). What is left is yours: section 7.
Specs: `docs/product/prd/F-15-recall-system.md` (the PRD), `docs/product/erd/F-15-recall-system.md` (the ERD). This file says in what order R1 is built, what each wave changes, how it is proved, how it is rolled back and what you must arrange. R2 waves W2 (living decks), W3 (coverage, tracker, Today, import) and W4 (update history, own words, mistakes) are sections 8 to 10 below; the rest of R2 (sharing, AI) and R3 (parameter fit) are not in this file.

R1 ships: seven card kinds, FSRS-6 as a pure versioned function in Python and TypeScript with shared golden vectors, an append-only idempotent review log, the review player (keyboard, swipe, undo, edit in place), daily limits, catch-up, rebalance, vacation, early review, forgotten list and leech notices, stats, platform decks edited in Django admin (copy-on-subscribe), offline review, export and delete-all, and the Notes provider (`create_card_from_source`, `cards_for_source`). **Not in R1:** AI (`recall_ai`), sharing (`recall_sharing`), quick revision and exam horizon, deck update sync (R2), the Notes "highlight to card" button, the F-13 Today registration (`provide_today` exists as a selector, nothing registers it), billing.

## 0. Status

R1 is built and closed out (W12, 2026-10-11): `ruff check` and `ruff format --check` are clean over 725 files; the API suite passes on PostgreSQL 16 (4,091 passed, 1 skipped) and on SQLite (4,015 passed, 76 skipped; the one failure there is a Notes OCR test that needs PostgreSQL full-text search and only runs where `tesseract` is installed, which this sandbox has and a plain SQLite run does not); the web recall, observability and features tests pass (295) and `pnpm check` passes (3,006 web tests, build); `recall-seed-check.py` and the CMA Final Paper 13 dry run are clean (11 files, 786 items); `run.py` passes 43 checks and `capacity.py` runs on PostgreSQL. Not done, on purpose: manual device and browser checks (your standing rule, an accepted risk, section 6), your own Postgres run, the beta cohort and the counsel review. The table below is the original check against the code (2026-10-08); every "missing" row has since been built, as noted.

### 0.1 Original check (2026-10-08)

| Item | State |
| --- | --- |
| Notes R1 to R3, `core/recall_port.py` (+ its use in `modules/notes`, 503 `recall_unavailable`, `capabilities.recall`) | Present |
| `core/jobs` + worker + 5-minute tick, `core/registry.py` (erase and export), `core/feature_flags.py` (strict mode), base classes in `core/errors.py` and `core/permissions.py`, Sentry `before_send` scrubbing, syllabus selector extensions, `src/lib/offline-queue`, coverage selectors (`get_active_enrollment`, `exam_date_of`, `due_for_revision`) | Present |
| `core/richtext` `card` profile (and its web twin) | Was missing, fixed in Wave 0 |
| Flag lookup failure caching and `CACHES` (AUD-003, W0L.2) | Was missing, fixed in Wave 0 |
| Design-system `RatingButtons`, `FlipCard`, `ProgressCounter`, `DatePicker` | Were absent, built in Wave 7 |
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
| D10 | `core.recall_port.RecallUnavailable` is now a `CodedError` (503 `recall_unavailable`) instead of a bare `Exception`. Notes only turns "no provider" into 503; it does not catch the exception a provider raises, so a flag-off provider would have produced a 500. With the change a flag-off student gets the same 503 Notes already gives when no provider is registered, and Notes is untouched | The runbook assumed Notes answers 503 for a raising provider; it does not |
| D11 | Notes `capabilities.recall` is now flag aware: `core.recall_port.recall_available(user_id)` asks the provider's optional `available_for`, and Notes' `capabilities(user_id)` uses it (owner approved this Notes change). Flag off means `false` and 503 on "Make a card"; a provider without `available_for` counts as on | The port cannot see the student's flag otherwise |
| D12 | `RecallItem.course` is filled from `syllabus.selectors.get_chapter(...)` (`subject.scheme.level.course_id`), because `ChapterRef` carries no course id. `cards/undo-delete/` handles both token kinds so there is one undo endpoint | Keeps the endpoint list of the PRD |
| D13 | `rebalance` reading: candidates are active review cards due before the end of today (overdue or due today). The mandatory ones with retrievability under 0.7 stay; the rest are ranked by `scheduling.priority`; the top `reviews_per_day` stay today and the others go `reviews_per_day` per day over days 1 to N (N at most 14) by `postponed_until` plus a `postpone` event (reason `rebalance`). Cards beyond the window stay due today. It does not look at what is already due on the later days | ERD wording is "spread"; this is the simplest rule that never drops a card |
| D14 | `set_vacation` accepts today to 60 days ahead (60 is mine, the ERD gives no limit). Cards due before the day after it ends get a `postpone` event (reason `vacation`); ending it early writes `unpostpone` events. No cards are created, no streak rules change | A vacation needs a defined effect on due dates |
| D15 | The log insert is the ORM `create` in a savepoint that catches `IntegrityError`, after an `exists` check made under the card's row lock, not `ON CONFLICT DO NOTHING`; rollups use update-then-create-in-savepoint, not `ON CONFLICT DO UPDATE`. Same guarantees (one row per event id, one count), one code path for SQLite and PostgreSQL | The quick tests run on SQLite; the composite-key table is unmanaged |
| D16 | Replay and the fast path use the student's current settings and weights. A late event on a card after a retention change therefore re-derives that card's due date with the new retention (changing a setting alone never moves anything; tested) | The log holds facts, not the settings in force at the time; storing them is an R2 question |
| D17 | A batch locks every card it touches in id order before applying events, so two overlapping syncs cannot deadlock. Undo "last 10" is ranked by review time within the session (the student's session-less reviews when none) | Found while writing the Postgres race test |
| D18 | Leech only sets `leech = true` and emits `recall_leech_detected`; it does not suspend the card (the `LEECH_SUSPEND_DAYS` constant is unused in R1) | The PRD slice only asks for the flag and the event |
| D19 | `recall_check_vectors` reuses the vector tests' own assertions, so the command and the tests cannot disagree | One definition of "matches" |
| D20 | The daily "maximum reviews" counts reviews of graduated cards (review and relearning phases); learning-step repeats and new cards do not use it, new cards have their own limit. "Do 20 more" is `queue/?extra=20` (0 to 100), which lifts the review limit for that call only | The PRD does not say what the limit counts; counting step repeats would cut a student off mid-learning |
| D21 | `chapter`, `deck` and `catchup` queue sources ignore the daily review limit (catch-up uses it as its size); `deck` covers a student's own decks until W11 adds platform subscriptions. `quick` and `cram` answer 422 `not_in_this_release` | Practice by chapter or deck is not "today's plan" |
| D22 | `PUT settings/` is a partial update of the keys it carries (400 for an unknown key, 422 naming the field for a bad value). `vacation_until` is not accepted there: it has `PUT vacation/`, which also moves due dates. `GET settings/` never creates the row | One way to change each thing; GETs never write |
| D23 | Stats `ETag` is built from the newest `updated_at` among the rollup rows in range, and for `forecast` and `chapters` also the newest card `updated_at`, because creating or editing a card changes them without a review | Rollups alone would serve a stale forecast after a card is added |
| D24 | The pack holds due reviews and learning cards due by the end of tomorrow's study day, then the new-card allowance (none in catch-up), up to the smaller of the plan's `pack_size`, `RECALL_PACK_MAX` and the requested `limit`. It ignores the daily review limit so an offline day is not cut short | FR-F15-66 |
| D25 | Not built in W6: `quick_revision_plan` and `GET params/` (R2), `reviewed_by_subject_kind` (waits for F-13). `provide_today` returns local dataclasses (`ProviderResult`, `RecallTask`) and nothing registers it | Runbook says nothing registers it |
| D26 | `tz` is accepted on `today/`, `queue/` and `stats/*` and overrides the stored zone for that call (422 for an unknown zone). The forgotten list needs a score of at least 2 and ignores undone reviews | PRD 9.1 lists `tz?` |
| D27 | The queue endpoint returns the same memory fields as the pack (`stability`, `difficulty`, `due_scheduled_at`, `last_review_at`, `step`, `reps`, `lapses`) so the local player can schedule any queue | W8 offline player needs them |
| D28 | `open_session` creates the session with `id = client_id`, so an offline device can tag reviews before the server has seen the session | Offline sessions |
| D29 | The review route file is `app.recall.review.index.tsx` so the summary route can nest under it | TanStack file routes |
| D30 | `axe-core` added as a devDependency of `@artha/web` (already a transitive dependency at 4.13.0); needs `pnpm install` | Axe checks in component tests |
| D31 | No navigation entry yet: the layout module needs owner approval before it is touched | Module rules |
| D32 | The `E` key and Edit card button in the review player open the card page (wired in W10; they were hidden in W9) | Card editor exists now |
| D33 | `useDecks`, `useSubscription`, `useQuickPlan`, `useSuggestions` and `useShare` are not built: they belong to R2 or later | Scope |
| D34 | `FlipCard` gained `focusOnFlip` (default off) so the keyboard path moves focus to the answer when the card is turned by a key | Review player |
| D35 | 320 px width is checked in jsdom by class assertions only, not by a real layout | jsdom has no layout |
| D43 | Swipe in the player is tested at screen level (left = Again, right = Good, no swipe before the flip, short drags ignored), offline against a stored pack | Closes the gap noted after W10 |
| D36 | `GET cards/{id}/` now also returns a `memory` block (stability, difficulty, due, reps, lapses, step), and a new `GET cards/{id}/reviews/` returns her last 50 reviews of the card (undone ones left out) | PRD 9.2 lists no history read; the card page needs both |
| D37 | A chapter picker (course, level, paper, chapter) is in the creator, on the card page and in the bulk Move to chapter. It reads the syllabus through that module's barrel and skips a step when there is only one choice. Topics and decks still come from the URL only; the picker does not restore the path of an already filed card | Chapter only; topics are fine-grained, decks are R2 |
| D38 | Cards written offline wait in local storage (50 at most, one `client_id` each), not IndexedDB | A few small cards; the event store is for reviews |
| D39 | An edit to an existing card made offline is kept in local storage (`cardEditQueue`, 50 at most, one per card, first base revision kept) and sent when she is back. A clean three-way merge is sent quietly; a real conflict, a card deleted elsewhere, or a refused text is kept and flagged: a notice on the Cards list and the dialog or message on opening the card | Same reasoning as D38; nothing is lost silently |
| D40 | Bulk actions in the browser: pause, mark as must know, move to chapter, add one tag, delete (with a confirmation). Add to deck waits for decks (R2). Moving a single card to another chapter needs a connection | Scope |
| D41 | The live preview uses the shared `card` rich-text profile and the W2 `render` twin; the server stays the authority and may refuse a text the preview accepted | One renderer, no copy |
| D42 | W9 test review found three faults, now fixed: the offline pack read was paused by TanStack Query's default network mode, an error loading the pack never reached the player, and going offline mid-session briefly dropped the pack | `networkMode: 'always'` on local reads, `packState.error` in the effect deps, `keepPreviousData` |
| D44 | Staff permissions come from `profiles.role` through the person's e-mail: a Django staff login is matched, ignoring case, to the one `profiles` row with the same address. `editor` carries `recall.deck.author` (items, versions, draft deck versions, reports); `admin` carries author plus `recall.deck.publish` (publish, quota plans, read-only student state); a superuser has both; a login with no matching or an ambiguous profile sees nothing. `profiles` gained `selectors.role_for_email`, `services.set_staff_role` and `manage.py grant_staff_role` | Django logins and Supabase users are separate tables; the address is the only link, and a missing or duplicate match never grants anything |
| D45 | The review log has a composite primary key, which Django's admin cannot list, so it is a read-only page under Cards (`/admin/recall/recallcard/review-log/?user=<id>`): facts only (ids, rating, times), never card text | Admin limitation |
| D46 | `load_recall_seed` without file names reads only the top level of `recall/seed/` and skips files starting with `_` and `sample_` unless `--include-sample` (papers live in folders and are loaded by naming the folder or the files), and a file marked `"sample": true` is never published unless `--include-sample` is also given. An edited item becomes a new draft version; a deck holding an `unknown` rights item loads as a draft and is reported as not published | A demo file must not reach students by accident |
| D47 | Unsubscribe archives every card of the deck, including ones she paused by hand; resubscribe brings them back active with their memory. A card whose item is also in another active deck stays active and moves to that deck | Simple rule; the manual pause is the one thing lost |
| D48 | Resubscribe adds no new items (that is R2 sync); resubscribe and subscribe-after-unsubscribe answer 201 when cards came back, 200 when nothing changed | R1 has no pinned subscribers or follow-updates |
| D49 | Platform card text is never in the CSV or JSON export: those cards are listed by ids, state and schedule; her own cards carry their fields. The closing line `#complete,<rows>` (or `#next,<cursor>`) says whether a CSV is whole, and the web refuses to save one without it | The platform's words are not exported in bulk; no silent cut |
| D50 | A report is `POST items/{id}/report/` with reason `wrong`, `outdated`, `copyright` or `other` and an optional note of 500 characters; one open report per student and item, a second tap changes nothing; `handled_by` is not set because a Django login is not a student id | FR-F15-52 |
| D51 | `GET decks/subscribed/` (her decks) and `GET decks/library/` (live platform decks, filters course, level, subject, chapter, tier, cursor) replace a single `decks/` list in R1 | Two different questions |
| D52 | Audit rows written from the admin (`deck_publish`, `quota_change`) carry no actor id, for the same reason as D50; they hold ids and counts only | Same |
| D53 | Export and erase stay reachable with `recall_system` off (D4), also on the web: the recall settings screen shows "Your revision data" under the "not available yet" message. A successful erase also clears the recall data kept on this device (offline pack, review events, queued cards and edits) and every cached answer | A rollout flag must never block erasure |
| D54 | The design system gained the `Flag` icon (used by "Report this card") | One curated icon list |

## 2. How each wave is worked

One change set per wave, in this order; each ends with a short report and a "for you to do" list. Every wave: `ruff check . && ruff format --check .` and `pytest` (SQLite, `DJANGO_DEBUG=true`) in `apps/api`; for web waves `pnpm typecheck`, `eslint --max-warnings=0`, `prettier --check`, `vitest` and `build` run in a scratch copy under `/tmp` (the mounted `node_modules` is macOS-only), with changed module files rsynced back; Postgres tests run against a private Postgres in `/tmp` where the wave touches the database. Nothing is committed or pushed; I propose a Conventional Commit message per wave (scopes `api`, `web`, `ds`, `docs`, `db`) with the trailers. Docs, `docs/BUILD-TRACKER.md`, `apps/api/.env.example` and `docs/SETUP.md` are updated in the wave that changes them.

| Wave | Content | PRD slices | Size |
| --- | --- | --- | --- |
| W0 | Prerequisite fixes (done) | | small |
| W1 | Pure Python domain: scheduler, folding, queue planning, kinds, cloze, limits, golden vectors | 1, 2, part of 6 | large |
| W2 | TypeScript twin of the same, same vectors | 3 | medium |
| W3 | Schema, migrations, plans seam, quotas, RLS, partitioned log | 4, 5 | medium |
| W4 | Card services, endpoints, kind registry, Notes provider (done) | 6, 12 | large |
| W5 | Review services: submit, batch, undo, replay, sessions, rollups, events, tick | 7 | large |
| W6 | Read side: today, queue, pack, forgotten, stats, settings, `provide_today` | 8 | medium |
| W7 | Design-system components | 9 | medium |
| W8 | Web lib: offline store, sync, hooks | 10 (part) | large |
| W9 | Web screens: hub, review player, summary, stats, settings | 10 (part) | large |
| W10 | Cards browser, creator, detail, bulk, duplicate warning | 11 | medium |
| W11 | Platform decks: admin editor, publish, seed loader, subscribe, library UI, reports, export and erase | 13 | large |
| W12 | End-to-end script, capacity note, privacy checks, docs, tracker, close-out (done) | | medium |

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

### W4. Cards: services, endpoints, provider (done 2026-10-09)

`modules/recall/`: `registry.py` (`register_card_kind`), `adapters/` (`syllabus.py`, `coverage.py`; selectors only, never foreign models; a test greps that no `recall` file imports `modules.<other>.models`), `services/cards.py` (`create_card` idempotent on `(user, client_id)` with duplicate warning and `force`, `create_card_from_selection` as a thin wrapper, `update_card` with `base_rev` and 409 `edit_conflict`, `set_card_status`, `bulk_update` all or none up to 200, soft delete with 10-second undo token), `selectors/cards.py`, serializers, views, `urls.py`, throttles (`recall_review` 600/min, `recall_write` 120/min, `recall_export` 6/hour), flag permission `flag_required("recall_system", strict=True)`, errors from `core`.
Provider: `RecallProvider` registered in `RecallConfig.ready()` through `core.recall_port.register_recall_provider`; `create_card_from_source` (D2) and `cards_for_source`. Notes then reports `capabilities.recall = true` and "Make a card" works; no Notes UI is edited. Note for you: this switches the Notes endpoint from 503 to live for anyone with the `recall_system` flag off too, because the port does not know the flag. The provider therefore checks the flag for that student and raises `RecallUnavailable` (Notes answers 503) when it is off, and `cards_for_source` returns `{}`.
Tests: every endpoint (401, happy, 400, other student's data is 404), kind validators, cloze, quota edge, idempotency on `client_id`, provider idempotency on `(user, ref_id, port kind)`, flag-off parametrised test (D4).

Built: `registry.py` (`KindSpec`, `register_card_kind`, `get_kind` with 422 `unknown_kind`; the seven kinds wrap `domain.cards`), `adapters/syllabus.py` (chapter and topic to link columns, stable keys and course/level/scheme/subject ids through `modules.syllabus.selectors` only; `adapters/coverage.py` is a docstring until W6), `services/cards.py` (`create_card`, `create_card_from_selection`, `update_card`, `set_card_status`, `undo`, `bulk_update`), `services/student.py` (settings row created on first read, the study clock), `selectors/cards.py` (`get_card`, `list_cards` with keyset cursor and the PRD 9.2 filters, `card_for_source`, `cards_for_source`), `serializers.py`, `views.py`, `urls.py`, `permissions.py` (`recall_system`, fails closed), `provider.py` (D2 mapping, flag aware), `vocab.py`. Endpoints under `/api/v1/recall/cards/`: list, create, `from-selection/`, `{id}/` (GET, PATCH with `base_rev`, DELETE), `suspend/`, `unsuspend/`, `bury/`, `reset/`, `recheck-ok/`, `undo-delete/`, `bulk/`. Throttle scopes `recall_review`, `recall_write`, `recall_export` and env names `RECALL_TICK_SECRET`, `RECALL_PACK_MAX`, `RECALL_DEFAULT_WEIGHTS_VERSION` are in place (only `recall_write` is used so far).
Behaviour worth knowing. Quota is reserved first inside a savepoint, so any later failure (duplicate `client_id`, bad deck, constraint) rolls the reservation back with it; `deck.card_count` counts cards (faces), not items. A text edit makes a new live version (the old one becomes `superseded`), repoints every face and bumps `rev` once; a cloze edit may add faces at the end or remove them from the end. Delete is soft and applies to the whole item (all faces of a cloze); the undo token is a signed, stateless value (`recall.undo`, 10 seconds) and `cards/undo-delete/` accepts both kinds of token (a delete token restores and re-reserves quota, a create token from `from-selection/` deletes the card). Selection cards are never shareable; their locator keeps ids, numbers and short offsets only. A bulk call is one transaction. The list defaults to hiding deleted cards and sorts `newest`, `oldest` or `updated` (a "due" sort belongs to W6).
Tests: 148 new in `modules/recall/tests` (plus one in `core/tests`) (create, edit, state and undo, bulk, list, selection, flag and auth matrix over every URL, provider, layering grep, registry) plus a Postgres-only concurrency file (one `client_id` sent eight times makes one card, eight racers for three slots create exactly three, the provider is idempotent under a race). `makemigrations --check` shows no change: W4 adds no model.
Rollback: remove `modules.recall.urls` from `config/urls.py` and the provider registration from `RecallConfig.ready`; no data migration to undo.

### W5. Reviews (done 2026-10-09)

`services/reviews.py` exactly as ERD 3.5: `submit_review` (idempotent insert `ON CONFLICT DO NOTHING`, row lock on the card, stale-content and late handling, fast path and replay path, rollups only for newly inserted rows, sibling burying, leech), `submit_reviews` (up to 100), `undo_review` (last 10 within 30 minutes, compensating event), `replay_card`, `open_session` and `close_session` (emits `recall_session_completed`), `rebalance`, `set_vacation`, `update_settings` (changing retention never reschedules), rollup maintenance with `INSERT ... ON CONFLICT DO UPDATE`. Endpoints `reviews/`, `reviews/batch/`, `reviews/undo/`, `sessions/`, `sessions/{id}/close/`, `catchup/rebalance/`, `vacation/`. The light tick (D3). Commands `recall_replay`, `recall_rebuild_rollups`, `recall_check_vectors`.
Tests: duplicate event is a no-op, late event replays, two devices rating one card equal the fold, clock skew clamp, 30-day cutoff, deleted card, stale content, undo, rollups incremental equals rebuilt after random sequences, **Postgres concurrency** (two concurrent reviews of one card, two batch syncs with overlapping ids), throttles named and tested, no card text in any log line (a log-capture test).
Exit: the append-only guarantees hold on Postgres; replay of a card from the log equals its stored state.

Built: `services/engine.py` (settings, `Cfg` and weights once per request), `services/reviews.py` (`submit_review`, `submit_reviews`, `undo_review`, `replay_card`), `services/rollups.py` (daily and chapter counters, `rebuild`), `services/sessions.py` (`open_session`, `close_session`, `close_idle`), `services/catchup.py` (`rebalance`), `services/preferences.py` (`update_settings`, `set_vacation`), `domain/folding.fold_trace` (the fold plus a per-review trace; `fold` is untouched and a test checks both end in the same state). Endpoints under `/api/v1/recall/`: `reviews/` (201, or 200 for a duplicate), `reviews/batch/`, `reviews/undo/`, `sessions/`, `sessions/{id}/close/`, `catchup/rebalance/`, `PUT vacation/`, and the tick `internal/tick/` (GET or POST, header `X-Recall-Tick-Secret` or `Authorization: Bearer`, env `RECALL_TICK_SECRET`; open whatever the flag says; closes sessions idle for 60 minutes; excluded from CORS). Commands `recall_replay (--user [--card] | --all)`, `recall_rebuild_rollups (--user | --all) [--from]`, `recall_check_vectors` (exit 1 on a mismatch). The settings endpoint itself is W6; `update_settings` is the service behind it.
Behaviour worth knowing. One transaction per review: the card row is locked first, a repeated event id returns `duplicate` and counts nothing, then the event is classified: a time more than 5 minutes ahead is clamped to now (`clamped_time`), older than 30 days is logged but not scheduled (`late`, result `late_unapplied`), a version older than a substantive or amendment change is logged but not scheduled and marks the card `needs_recheck` (`stale_content`), a deleted card is logged with `deleted_card` and changes nothing, cram never schedules, review-ahead does. When the event is the newest fact about the card it takes the fast path (one `fsrs6.review`, derived log columns written in the same insert); otherwise it is inserted and the card is folded again (`merged: true`). Replay rewrites only derived log columns (under `log_guard.replaying()`), moves a rollup count when a review's phase changes, and leaves `rev` alone when nothing changed. Rollups and session counters move only for a newly inserted row; undo applies the negative of the voided row on its own day, voids it (`counts_for_scheduling` false) and replays. Sibling burying applies only to reviews made today. Events: `recall_session_completed` (counts and ids only) and `recall_leech_detected`, both after commit. No card text is read into a log line or an event; a log-capture test checks it.
Tests: 6 new test files plus `fold_trace` in `domain/tests/test_properties.py` and the flag matrix extended: 444 recall tests pass on SQLite (30 skipped, the PostgreSQL ones) and 472 on PostgreSQL 17 (2 skipped). Covered: duplicate, late, two devices in any order equal the fold, clamp, 30-day cutoff, deleted card, stale and typo-only content, cram, review-ahead, leech, siblings, batch (100 cap, bad events, same id twice), undo (idempotent, once, last 10, 30 minutes, other student), incremental rollups equal a rebuild after random sequences with undo and replay, replay repairs a drifted card, sessions (open, close once, tick), rebalance, vacation, settings (every refusal names its field; retention change reschedules nothing), the tick (secret, flag off, no secret configured, CORS), throttle scopes and a real 429 at 601 reviews, the commands, no card text in logs or events, and on PostgreSQL: two concurrent reviews of one card, eight racers with one event id, two overlapping batch syncs with opposite card order, the log refusing updates and deletes while a replay may rewrite derived columns only. `makemigrations --check` shows no change: W5 adds no model.
Rollback: remove the W5 routes from `modules/recall/urls.py` and `RECALL_TICK_SECRET` from the scheduler; no data migration to undo.

### W6. Read side (done 2026-10-09)

`selectors/`: `today.py` (`today_plan`: counts, mode normal/catchup/vacation, `days_to_clear`, `est_minutes`, kind tiles, forgotten top 5), `queue.py` (`build_queue` for sources `today`, `chapter`, `deck`, `forgotten`, `catchup`, `review_ahead`; `quick` and `cram` answer 422 `not_in_this_release`), `pack.py` (up to the plan's pack size, with weights, settings, counters, `pack_id`, `expires_at`), `forgotten.py`, `stats.py` (summary, retention, forecast, chapters, 60-second `ETag`), `cards.py`, plus `provide_today` returning the F-13 result shape locally defined as a dataclass (no import of F-13; nothing registers it) and `due_counts`, `recall_strength`. Endpoints `today/`, `queue/`, `pack/`, `forgotten/`, `stats/*`, `settings/` (GET, PUT with ranges).
Tests: `assertNumQueries` per endpoint with a 5,000-card fixture, catch-up thresholds, limits and "Do 20 more", interleaving, burying, GETs never write (a test counts writes), queue p95 target recorded by the capacity script in W12.

Built: `selectors/study.py` (settings or in-memory defaults, `Cfg`, weights, today's counters, the study clock), `selectors/queue.py` (`build_queue`, `plan_today`, rendering and the four interval previews), `selectors/today.py` (`today_plan`, `provide_today`), `selectors/pack.py`, `selectors/forgotten.py`, `selectors/stats.py` (`stats_summary`, `stats_retention`, `stats_forecast`, `stats_chapters`, `recall_strength`, `due_counts`). Endpoints under `/api/v1/recall/`: `today/`, `queue/` (`source`, `chapter_id`, `deck_id`, `kind`, `tier`, `limit` up to 50, `exclude`, `extra`, `tz`), `pack/`, `forgotten/`, `stats/summary|retention|forecast|chapters/` (ETag, 304), `settings/` (GET, PUT). Every one is flag gated and none writes.
Behaviour worth knowing. A student with no settings row gets the defaults in memory and no row is created by a GET. Vacation gives an empty plan, queue and pack and mode `vacation`. Catch-up (more than twice the daily limit due, or the oldest card more than 3 days late with more than a day of work) pauses new cards unless `pause_new_in_catchup` is off. Interleaving off treats all subjects as one. Buried, suspended and deleted cards are never served. The previews are computed by the same function a review applies, and a test checks that the preview for Good equals what the review then schedules. Streak and series use the 04:00 study day.
Tests: 83 new in `test_read_side.py` and `test_stats.py` plus the flag matrix extended to every new URL. 527 recall tests pass on SQLite (30 skipped) and 555 on PostgreSQL 17 (2 skipped). Covered: defaults without a row, validated updates, other students' data, empty library, counts and tiles, catch-up thresholds and the pause switch, limits and "Do 20 more", vacation, time zone, queue order, interleave on and off, burying, `exclude` and `limit`, quick and cram refused, chapter, deck, catch-up and review-ahead sources, previews equal the review, source and badges, forgotten ranking with undo, pack content, cut to plan size and environment cap, no new cards in catch-up, summary, streak rules, true retention, retention, forecast, chapter strength, ETag and 304 for each report, `provide_today`, `due_counts`. **No GET writes** (every read endpoint is run under a query capture that fails on INSERT, UPDATE or DELETE) and **the number of queries is the same with 40 and with 5,000 cards** (at most 20 per endpoint). The p95 latency target is recorded by the capacity script in W12. `makemigrations --check` shows no change.
Rollback: remove the W6 routes from `modules/recall/urls.py`; no data migration to undo.

### W7. Design system (done 2026-10-09)

`packages/design-system/src/components/ui/`: `rating-buttons.tsx` (four equal buttons, label, interval preview, key hint, roving focus, `aria-keyshortcuts`, 44 px minimum), `flip-card.tsx` (front and back, reduced-motion crossfade of 0 ms, announces the change, swipe handlers with a button alternative), `progress-counter.tsx` (`aria-live="polite"`), `date-picker.tsx` (native input base, used for vacation end; exam date is R2). Exported from the barrel, added to the showcase, contrast tokens checked with `pnpm check:contrast`, tests for keyboard and ARIA. Icons only from the package.
Exit: all four themes, WCAG 2.2 AA, 320 to 1280 px without horizontal scroll (checked in the showcase by an automated test where possible, otherwise recorded as a checklist item you will not run manually, see section 6).

Built: the four components, exported from the barrel and shown together in the showcase (`RecallPrimitivesShowcase`). `RatingButtons`: one tab stop that lands on Good, arrows, Home and End move focus without wrapping, `aria-keyshortcuts` 1 to 4, optional page-wide keys 1 to 4 (off while typing and with Ctrl, Meta or Alt), the interval is part of the accessible name ("Good, next in 5 d"), `min-h-14 min-w-11`, status colours are only a second cue next to the word. `FlipCard`: the 3D turn exists only under `motion-safe`, under reduced motion the faces swap at 0 ms; the hidden face is `inert` and `aria-hidden`; a polite status says "Answer shown"; focus moves to the answer when the Show answer button turned the card; swipe is reported only after the flip, as `left` or `right`, and the buttons stay the primary path. `ProgressCounter`: the figures are a polite live region and the bar repeats them as value text. `DatePicker`: native `type=date`, labelled, hint and error wired with `aria-describedby`, `aria-invalid`, typed values clamped to `min` and `max`, null when cleared. Tests: pure logic in `packages/design-system` (node), jsdom keyboard and ARIA tests in `apps/web/src/modules/design-showcase/RecallPrimitives.test.tsx`. `pnpm check:contrast` passes for all four themes. 320 px: no component sets a fixed width and the showcase container is `w-full max-w-xl`, which a test asserts; a real layout width check is not run (jsdom has no layout), so it is a checklist item for W9 review screen tests, not a manual one.

### W8. Web lib, offline and sync (done 2026-10-09)

`apps/web/src/modules/recall/`: `lib/eventStore.ts` (IndexedDB: pack, pending events up to 5,000, sessions; ordered, batched flush of 100), `lib/sync.ts` (per-event result codes, card replacement from responses, merge summary), `lib/api.ts` (typed, zod at the edge), hooks (`useTodayPlan`, `useQueue`, `useReviewSession` local-first, `useSync`, `useSettings`, `useCards`), server clock offset helper reused from the tracker pattern. Follows the persisted-queue pattern of `src/lib/offline-queue` but does not reuse its writer (ordering and volume differ, as the ERD says). Public barrel `index.ts`.
Tests (vitest, fake-indexeddb): offline session of 100 cards gives the same intervals as the server fold, 250 queued events flush in three batches, a dropped response retried creates no duplicates, quota of 5,000 events refuses new ones with a message, stale pack (older than 48 h) warning.

### W9. Web screens (done 2026-10-09)

Built (W8 and W9): `lib/` (IndexedDB event store with a 5,000-event quota and 48 h stale-pack warning, ordered sync in batches of 100 with per-event result codes, zod-typed API, pure local-first player that folds like the server, fail-closed analytics allow-list), hooks (`useTodayPlan`, `useQueue`, `useReviewSession`, `useSync`, `useSettings`, `useCards`, stats, forgotten, pack), and six `noindex` routes: hub, review, summary, stats, forgotten, settings. All states are covered (zero cards, caught up, huge backlog in days not a number, vacation, offline, sync conflict, flag off, error, skeletons). Review player: Space/Enter, 1 to 4, U, S, B, ?, swipe with buttons always present, bottom thumb bar, visual-viewport height, first-time intro, honest-rating hint, leech chip, "Review ahead 10 cards". Tests: offline 100-card session equals the server fold, 250 events flush in three batches, a retried dropped response creates no duplicates, quota and stale-pack messages, keyboard-only session, axe on each screen, event allow-list. The three vector-file parity tests pass against `apps/api`.

Routes (thin): `/app/recall`, `/app/recall/review` (search params `source`, `chapter`, `deck`, `kind`, `tier`, `n`, session `s`), `/app/recall/review/summary/$sessionId`, `/app/recall/stats`, `/app/recall/forgotten`, `/app/settings/recall`; all `noindex`. Containers and presentational components per ERD 9. States: zero cards, all caught up, huge backlog (never a red giant number), vacation, offline, sync conflict, flag off, error, loading skeletons. Review player: keyboard (Space/Enter, 1 to 4, U, E, S, B, ?), swipe (left Again, right Good, always with buttons), bottom thumb controls, visual-viewport layout, first-time intro, honest-rating hint, leech chip, "Review ahead 10 cards". PostHog events from PRD 10.1 with an allow-list of properties (no card text); `useFeatureFlag('recall_system')` with the fail-closed rule.
Tests: component tests for each state, keyboard path completes a session, axe checks, event allow-list test.

### W10. Cards screens (done 2026-10-09)

Built: `/app/recall/cards` (filters in the URL: search, kind, importance, status, chapter, deck, order; cursor pagination; select with a pause, must-know and delete bar; empty, no-match, loading and error states), `/app/recall/cards/new` (seven kind forms from the W2 specs, field counters, live preview of every face, duplicate warning with "Keep both", server field errors, plan limit message, prefill from `kind`, `chapter`, `topic`, `deck`, `from=selection`, `draft`, offline queue with a stable `client_id`), `/app/recall/cards/$cardId` (edit with `base_rev`, quiet three way merge and a per-field conflict dialog, memory in plain words, review history, pause, bring back, skip to tomorrow, reset memory with confirmation, delete with an undo toast). A "Cards" tab joins the recall tabs, and "Revision" joins the study links in the workspace menu behind `recall_system` (approved by the owner 2026-10-09). Tests: form validation for all seven kinds, the three way merge, failure mapping, the offline queue, URL filters, and component tests for the browser, creator and card page (including the conflict dialog and the duplicate flow). The missing W9 review player tests were added: keyboard-only session, offline and sync, 48 h warning, 5,000-event refusal, intro, shortcuts, analytics allow-list.

`/app/recall/cards`, `/app/recall/cards/new` (prefill via `?kind=&chapter=&topic=&deck=&from=selection&draft=`), `/app/recall/cards/$cardId`: browser with filters in the URL and cursor pagination, bulk select, creator with the seven kind forms and live KaTeX preview, duplicate warning, field counters, offline save queued, edit with `base_rev` and the 3-way conflict dialog, card memory stats, review history, suspend, bury, reset, delete with undo toast.
Added after review: chapter picker, bulk move to chapter and add tag, offline edits queued with a needs-attention notice, swipe tests (D37, D39, D40, D43).
Tests: form validation per kind, conflict dialog, duplicate flow, URL-driven filters, chapter picker, bulk move and tag, offline edit queue and flush, swipe.

### W11. Platform decks, export, erase (done 2026-10-09)

Built (API): `recall/admin.py` (platform items, item versions with draft-only editing and the kind's rules checked in the form, decks, deck versions edited as a list of `ref` or `ref@version` lines with Save and publish, reports queue with actioned, dismissed and flag-for-check actions, quota plans, read-only cards, review log and audit log; D44, D45), `services/decks.py` (atomic `publish_deck_version`), `services/subscriptions.py` (copy-on-subscribe up to 500 cards under a per-student-and-deck advisory lock, idempotent, unsubscribe and resubscribe), `services/reports.py`, `services/seed.py` and `manage.py load_recall_seed`, `services/erasure.py` and `selectors/export.py` (JSON and streamed CSV), and 11 new endpoints (all in the flag matrix test; export and erase stay open with the flag off). Built (web): `/app/recall/decks` and `/app/recall/decks/$deckId` (library with tier filter and show-more, her decks, add with "all, important and must know, or must know only", remove and bring back, "A newer version exists" as a count, too-large message, report a card), a Decks tab, and "Your revision data" (JSON, cards CSV, reviews CSV, erase with a typed word) on the recall settings screen. Tests: API 88 new tests (publish, subscribe, report, erasure, export of 20,000 reviews, seed loader, admin, staff roles, three Postgres-only concurrency tests) plus the 11 new URLs in the flag matrix; web screen tests with axe and 320 px class checks. See decisions D44 to D54.

Plan for the wave (kept for the record):

Django admin (`recall/admin.py`): item and version editor (change kinds, importance tiers, `rights_status`, `unknown` blocks publish, `source_label`), deck editor with draft versions, **atomic publish** (`publish_deck_version`: computes `change_vs_prev`, supersedes the old live version, a failure leaves the previous live version served), reports queue, quota plan editor, read-only views of cards and log (no card text of students). Permissions from `profiles.role` (scopes `recall.deck.author`, `recall.deck.publish`). `manage.py load_recall_seed [--publish]` (drafts, idempotent on `external_ref`), `seed/_TEMPLATE.json` and one example file clearly marked sample. Student side: `decks/library/`, `decks/{id}/subscribe/` (copy-on-subscribe in one transaction up to 500 cards, advisory lock, idempotent), unsubscribe (archive, progress kept) and resubscribe, report a platform item (FR-F15-52), `/app/recall/decks`, `/app/recall/decks/$deckId`. `services/erasure.py` (`delete_all_for_user`, `export_for_user`) registered in `RecallConfig.ready()` through `core/registry.py`; CSV exports of cards and reviews are streamed with a cursor and no silent cap. Pinned subscribers, follow-updates and diffs are R2: R1 subscribes at the live version and shows "A newer version exists" only as a count.
Tests: publish atomicity, rights gate, double-tap subscribe, resubscribe restores progress, export of 20,000 reviews is complete, erase leaves no row (cards, items, log through `recall.erasing`, sessions, rollups, settings), Postgres test for the advisory lock.
**Folded in here (owner, 2026-10-09):** the editors for the first platform decks, the Django admin accounts with the roles that carry `recall.deck.author` and `recall.deck.publish`, and the closed beta list (same 50 students as F-01, F-02, F-03) are part of this wave: the admin and seed loader above, a documented way to create the accounts and roles, and a documented way to put the beta students on the PostHog flag.
Exit: R1 core complete.

#### W11 operations: staff accounts, roles, seed files and the beta list

**Create an editor or admin (once per person).**
1. The person signs in to the web app once, so a `profiles` row with their e-mail exists.
2. On a machine that can reach the production database (the API's shell on your host, or your computer with `DIRECT_DATABASE_URL` set), run, from `apps/api`:
   `NEW_PW='a-long-password' python manage.py grant_staff_role --email person@example.com --role editor --admin-login --password-env NEW_PW`
   Use `--role admin` for someone who may also publish. The command sets `profiles.role` and creates (or updates) a Django staff login with the **same e-mail**; without `--password-env` the login has no password and you give one with `python manage.py changepassword <username>`. `--role student` takes both the role and the staff flag away (a superuser keeps hers).
3. They sign in at `/<DJANGO_ADMIN_PATH>/` (default `/admin/`). The roles: `editor` = scope `recall.deck.author`, `admin` = `recall.deck.author` + `recall.deck.publish`, a Django superuser = both. If the e-mail on the login and on the profile differ, or two profiles share an address, the person sees nothing; fix the address and run the command again.

#### Command cheat sheet (run from `apps/api`, with the venv active)

| Need | Command |
| --- | --- |
| Make someone an editor (writes decks, cannot publish) | `NEW_PW='long-password' python manage.py grant_staff_role --email person@example.com --role editor --admin-login --password-env NEW_PW` |
| Make someone an admin (also publishes, edits plans) | `NEW_PW='long-password' python manage.py grant_staff_role --email person@example.com --role admin --admin-login --password-env NEW_PW` |
| Change only the role, leave the login alone | `python manage.py grant_staff_role --email person@example.com --role editor` |
| Take staff access away (a superuser keeps hers) | `python manage.py grant_staff_role --email person@example.com --role student` |
| Set or reset a staff password | `python manage.py changepassword <username>` (the username is the lower-case e-mail) |
| Create a Django superuser (full access, no profile role needed) | `python manage.py createsuperuser` |
| Look at a seed file without saving anything | `python manage.py load_recall_seed path/to/file.json --dry-run` |
| Load a seed file as drafts | `python manage.py load_recall_seed path/to/file.json` |
| Load every chapter of one paper as drafts | `python manage.py load_recall_seed apps/api/modules/recall/seed/cma-final-paper13` (add `--dry-run` first) |
| Load and publish (rights gate applies) | `python manage.py load_recall_seed path/to/file.json --publish` |
| Include the shipped sample deck | add `--include-sample` (a sample is never published without it) |
| Who has which role (Django shell) | `python manage.py shell -c "from modules.profiles.models import Profile as P; print(list(P.objects.exclude(role='student').values_list('email','role')))"` |
| User ids for a PostHog cohort CSV | `python manage.py shell -c "from modules.profiles.models import Profile as P; print('distinct_id'); [print(i) for i in P.objects.filter(email__in=['a@x.com','b@x.com']).values_list('id', flat=True)]"` |
| Run the recall tests | `python -m pytest modules/recall modules/profiles -q -p no:warnings` (add `DATABASE_URL=postgres://...` to include the Postgres-only lock tests) |

Notes: a superuser already has every recall permission, so `grant_staff_role` is only needed for other people. The person must have signed in to the web app once before the command can find their profile. Never put the password on the command line; pass it through the environment variable named by `--password-env`.

**Editing in the admin.** *Recall > Items*: add an item (pick the kind, paste its fields as JSON; the fields of each kind are listed below). Changing text never edits a live version: *Item versions* makes a draft, one at a time. *Decks*: create a deck (title, slug, chapter), then *Deck versions*: start a draft, list the items one per line (`ref` or `ref@3` to pin a version), and press **Save and publish** (needs `recall.deck.publish`). Publishing is all or nothing: an item with `rights_status = unknown`, or an item that is withdrawn, blocks it and the admin says which; the previous live version keeps being served. *Reports* is the queue students feed with "Report this card".

**Fields per kind.** Fields marked "line" are plain one-line text, up to 200 characters; all others are Markdown with `$KaTeX$`, up to 4,000 characters. `pointer`: prompt_md, answer_md. `formula`: name (line), expression_md, variables_md (optional), when_md (optional). `section`: act (optional line), reference (line), prompt_md, gist_md, exceptions_md (optional). `definition`: term (line), definition_md, source_ref (optional line). `mnemonic`: mnemonic (line), expands_md, topic (optional line). `case_law`: case_name (line), citation, court and year (optional lines), facts_md (optional), held_md. `cloze`: `text_md` with `{{c1::answer}}` or `{{c1::answer::hint}}` markers; one card per number.

**Seed files.** One folder per paper, named `<course>-<level>-<paper>` (for example `apps/api/modules/recall/seed/cma-final-paper13/`), with one file per chapter named by the chapter key (`the-companies-act-2013.json`); the deck slug inside stays `<course>-<level>-<paper-short>-<chapter-key>` style (CMA Final Paper 13: `cma-final-cel-<chapter-key>`) and never changes. Copy `apps/api/modules/recall/seed/_TEMPLATE.json` into the paper's folder, rename it without a leading underscore, fill it in (`ref` per item and `slug` per deck must never change: that is how a second load finds them), then `python manage.py load_recall_seed path/to/file.json` (or the paper's folder, which loads every `*.json` in it) loads drafts, `--publish` also publishes (rights gate applies), `--dry-run` rolls everything back, and the sample file loads only with `--include-sample` (D46). Safe to repeat.

**Put the 50 closed-beta students on `recall_system`.** The flag is fail closed, so it must be created **at 0% for everyone** and then opened for the beta group only:
1. PostHog > Feature flags > `recall_system` > release condition: *Match by* `User ID` (the distinct id is the Supabase user id; the web calls `identify(user.id)` and the API evaluates the flag for the same id).
2. Create a static cohort *Recall closed beta* (PostHog > People > Cohorts > new static cohort) and upload a CSV with one column `distinct_id` holding the 50 Supabase user ids. You can list them with `select id, email from profiles where email in (...)` on the production database, using the same 50 e-mails as for F-01, F-02 and F-03.
3. Release condition: *Cohort* is *Recall closed beta*, rollout 100%. Leave the other conditions out. To add a student later, add them to the cohort; to switch the feature off for everyone, disable the flag (export and erase keep working, D53).
Check with one beta account (the Revision entry appears in the study menu) and one account outside the cohort (it does not, and `GET /api/v1/recall/today/` answers 403 `feature_disabled`).

### W12. Close-out (done 2026-10-11)

Built: `scripts/e2e/recall-r1/run.py` (functional check on PostgreSQL; 43 PASS lines, exit 1 on any failure, no card text printed), `scripts/e2e/recall-r1/capacity.py` (reviews per minute, queue, today and pack latency, 5,000 cards, 8 concurrent reviewers), `scripts/e2e/recall-r1/serve.py` (runs the API with the flag answered locally), the privacy checks below, `apps/api/.env.example`, `docs/SETUP.md` (section 9.1), `docs/BUILD-TRACKER.md` (section 4.3 and 4.4), the CLAUDE.md status line, and `docs/F-15-API-CONTRACT.md` with `modules/recall/tests/test_api_contract.py`, which fails when a documented path no longer resolves or a route is undocumented.

What `run.py` covers: a generated 320-card deck loaded with `load_recall_seed --publish`; one test student subscribes (201, then 200 on a repeat); 200 reviews online (150 backdated to create a backlog); an undo (and a repeat of it); 120 offline events over 100 cards from two devices ("phone" and "laptop") with 20 shared cards sent out of time order, so the replay and merge path runs; every event resent (all `duplicate`); a batch of 101 refused (422 `batch_too_large`); an export that holds every review exactly once; reps per card checked; `recall_replay --user` reports no change; Today shows catch-up mode, the rebalance moves cards and a second one moves none; queue, pack, stats ETag and 304, forgotten, settings, vacation and the tick with and without the secret; the two CSV exports end in `#complete,<rows>`; erase with the wrong word is refused, the real erase leaves no row in any recall table, including every partition of the review log, and the export is empty afterwards; the server log holds no card text. Export and erase share the 6 per hour `recall_export` throttle and the script uses exactly six calls.

**Privacy checks (hard rule: no card text, note text, deck titles or ids in logs, Sentry or PostHog).**
- Sentry, API: `core/sentry.py` did not scrub recall events (the ERD promised it); it now does. A recall event (URL, route, transaction or any frame in recall code) loses its request body, cookies, query string, `Authorization` header, breadcrumbs, extra data, frame variables and span data, and card, item and version ids in URLs, messages and exception values become `{id}`. `before_send_transaction` applies the same rules to performance events. `core/tests/test_sentry.py` (30 tests, 20 recall routes in one parametrized test) and `modules/recall/tests/test_privacy.py` (a real Sentry SDK with a capturing transport over create, edit, search, review, batch and selection requests that fail with a 500 while carrying card text) prove it.
- Logs: Django's `django.request` lines for 4xx and 5xx responses carried card ids in the path; `core/privacy.py` (`MaskRecallIds`, attached in `config/settings.py` `LOGGING`) masks them. `test_privacy.py` captures every log record and stdout and stderr over a create, review, batch, edit, 409, 422, selection, search, queue, pack, export, CSV and erase flow and searches them for the text, the selection text and the card, item and version ids.
- Sentry, web: `apps/web/src/modules/observability/sentryScrub.ts` (new, wired into `ObservabilityProvider.tsx` through `beforeBreadcrumb`, `beforeSend` and `beforeSendTransaction`) masks ids in recall URLs and drops console and input breadcrumbs on recall pages. 5 tests.
- PostHog: `modules/recall/lib/analytics.ts` rejects any property not on the allow-list and any id-like string; `analytics.test.ts` snapshots the exact events and properties, sweeps leak candidates (text, titles, uuids, hex ids, objects) through every allowed key, and statically scans every `trackRecall` call site and every import of `posthog` and `track` in the module (a planted bad call was proved to fail the scan).
- Limit, stated plainly: access logs kept by a host or CDN in front of the API (Vercel, Supabase) record request paths, which hold card ids but no text. They are outside the API's control; do not turn on request-body logging at any layer.

**Found in W0 to W11 while closing out, and fixed.**
1. Rebalance, and "skip to tomorrow", postpone a card to exactly the first instant of the next study day, but queue planning, Today, stats and the catch-up counters treated a card due at that instant as due today (`<=`). Rebalanced cards were still counted as due (150 before and after). They now compare with `<` against the end of the day (`domain/scheduling.py` `plan_queue`, `selectors/today.py`, `selectors/stats.py`, `apps/web/src/modules/recall/lib/queue.ts`). The scheduler maths and the golden vectors are unchanged (no vector has a card due at that instant). Tests: `test_a_review_due_at_the_first_instant_of_tomorrow_is_not_due_today`, `test_rebalanced_cards_are_not_due_today_in_the_counters` and a web test in `pure.test.ts`.
2. The tests for the shipped sample seed file were stale (the sample moved out of the default load): rewritten around a temporary folder, plus a test that the shipped template is a valid file.
3. The ERD-promised Sentry scrubbing and the `django.request` id leak (above).
4. Format debt in `core/tests/test_storage.py` and `load_recall_seed.py` (ruff format only).

### Capacity note

Command: `DATABASE_URL=postgres://... python scripts/e2e/recall-r1/capacity.py [--cards 5000] [--reviewers 8] [--rounds 10] [--strict]`. Machine: the build sandbox, Linux x86-64 with 2 CPUs, Python 3.13, PostgreSQL 16 and the Django development server (one process, threaded, `DJANGO_DEBUG` off) on the same machine, so the database and the API compete for the same two cores. 8 students with 5,000 cards each (a quarter due, new, later and in learning) were seeded; students were erased afterwards. Targets are from the PRD, section 12. The ranges are three runs on 2026-10-11 (the sandbox is shared, so run to run spread is large).

| Measure (p50 / p95, ms) | Target | One student, one request at a time | 8 reviewers at once |
| --- | --- | --- | --- |
| Today | p95 under 300 | 128 to 133 / 148 to 156 (met) | p95 about 524 to 709 (missed) |
| Queue, 20 cards | p95 under 300 | 132 / 140 to 152 (met) | 274 to 424 / 560 to 655 (missed) |
| One review | p95 under 200 | 68 to 80 / 72 to 88 (met) | 141 to 201 / 261 to 319 (missed) |
| Pack of 300 cards | under 500 ms and 400 KB gzip | 158 to 167 / 181 to 187, 25 KB gzip (met) | not measured |
| Batch of 100 reviews | under 800 ms | p50 1,150 to 1,430, max 1,300 to 1,470 (**missed**) | not measured |
| Throughput | | | 1,600 reviews in 36 to 50 s, about 1,900 to 2,700 reviews per minute; 0 throttled, 0 failed |

Said plainly: **two targets are missed.** (1) The batch of 100 takes about 1.2 to 1.5 s here against an 800 ms target. A profile shows about 15 queries per event (1,515 queries for 100 events, 1,174 ms, of which 396 ms in SQL), so the cost is mostly ORM and Python work per event, not the database; fewer queries per event (bulk fetch of the cards and bulk insert of the log) is the fix, it was not done in W12 because it touches the review service, which this close-out may not change. A real device sends a batch of 100 only after a long offline stretch, so the effect is a slower catch-up sync, not a slower review. (2) Queue, Today and review p95 exceed their targets when 8 reviewers hammer the single-process dev server with no think time at all; each met its target when run alone.

What the numbers prove: the read and write paths are index-backed and do not degrade with 5,000 cards per student (a single request is fast and flat), nothing fails or is throttled at about 1,900 to 2,700 reviews per minute, the pack is small (25 KB gzip for 300 cards), and erase works at this size. What they do not prove: production latency (a different host, network, pooler, a multi-worker server and a managed database all change it, in both directions), behaviour under real student behaviour (a student reviews a card every few seconds, so 8 unthrottled reviewers are far busier than 8 students; at 50 beta students the load is a small fraction of what was measured), the web client, or scale beyond 8 concurrent writers. Treat the figures as a baseline to compare against: run the same command on your host before widening the beta and keep the output.

## 4. Environment and flags

| Name | Where | Value |
| --- | --- | --- |
| PostHog `recall_system` | PostHog | create at **0%** before the first merge. Fails closed: a missing key, an unknown flag or an outage means off, on both API (`strict=True`) and web |
| `RECALL_TICK_SECRET` | API | long random value; empty means the tick refuses everyone (sessions then close only when the student closes them) |
| `RECALL_PACK_MAX` | API | upper bound on the offline pack, default 500 (the plan row decides the real size) |
| `RECALL_DEFAULT_WEIGHTS_VERSION` | API | `fsrs-6.0` |
| Throttles | `config/settings.py` | `recall_review` 600/min, `recall_write` 120/min, `recall_export` 6/hour (shared by export and erase) |
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

Done already: approval of this file, the build, the e2e and capacity scripts, the docs. What is left is yours.

1. **Run the tests and both scripts on your own Postgres** (the sandbox run is evidence, not a substitute). From `apps/api`: `DATABASE_URL=postgresql://... DJANGO_DEBUG=true python -m pytest modules/recall core -q`, then `DATABASE_URL=... python scripts/e2e/recall-r1/run.py` and `capacity.py` (details: `docs/SETUP.md` section 9.1). The e2e script runs `migrate` and `load_syllabus_seed --publish` on that database and leaves one withdrawn `e2e-...` platform deck behind, so use a development or staging database. Keep the capacity output.
2. **Create the PostHog flag `recall_system` at 0%** (before the first deploy that contains recall; it fails closed, so nothing shows without it).
3. **Schedule the tick**: `POST /api/v1/recall/internal/tick/` every 5 minutes, beside the notes tick (header `X-Recall-Tick-Secret: $RECALL_TICK_SECRET` or `Authorization: Bearer $RECALL_TICK_SECRET`). Set `RECALL_TICK_SECRET` first (a long random value, it may equal `NOTES_TICK_SECRET`; an empty value refuses everyone). Without the tick sessions close only when the student closes them; nothing else breaks.
4. **Staff accounts**: an editor and an admin through `grant_staff_role` (W11 operations above), before the beta.
5. **Load the CMA Final Paper 13 decks**: `python manage.py load_recall_seed apps/api/modules/recall/seed/cma-final-paper13 --dry-run`, then without `--dry-run` (drafts). In the Django admin review each deck against the official syllabus, tie each deck to its CMA Final chapter, set `rights_status` on every item, then publish.
6. **Closed beta**: put the 50 beta students into a PostHog cohort and set the `recall_system` release condition to that cohort at 100% (W11 operations above). Check with one beta account (the Features card `revision` and the study menu entry appear) and one account outside it (they do not, and `GET /api/v1/recall/today/` answers 403 `feature_disabled`).
7. **Counsel review** of the copyright posture and the terms line for student-written cards: still deferred, needed before R2 sharing.
8. Optional before widening the beta: speed up the review batch (the missed 800 ms target in the capacity note).

**What changed after the first version of this runbook (so nothing below surprises you).** Seed files live in one folder per paper (`seed/cma-final-paper13/`, one file per chapter) and `load_recall_seed` accepts a file or a folder. The Features page card `revision` (`modules/catalog/features.ts`: status `live`, tool `/app/recall`, flag `recall_system`) already follows the flag: it shows for students whose flag is on and is hidden otherwise, so the earlier plan to leave it at `soon` is superseded and nothing needs flipping at launch. `useFeatureFlag` now waits for PostHog to finish loading before it subscribes (it polls for up to ten seconds), so a strict flag such as `recall_system` no longer stays off for a whole visit when the component mounts first. The flag stays strict on the API and the web.

**Which flag where.** `recall_system`: "team only" (the closed beta cohort) until your own Postgres run and the beta checks pass; only then widen the cohort. `recall_ai` and `recall_sharing` do not exist yet (R2).

## 8. R2, wave W2: living decks (flag `recall_system`, no new flag)

Built on top of R1 and R2-W1. Specs: PRD FR-F15-47 to FR-F15-50 and the ERD events section. Everything below is behind `recall_system` (fail closed). There are no new environment variables. The only new setting is the throttle scope `recall_apply_update` (30 per hour per student).

### 8.1 What it does for a student

- **Follow or pin.** A subscription follows updates by default. A new live version of the deck is applied for her by a job within one 5-minute tick cycle (see the capacity numbers). A pinned subscription is never changed by a job: it records the pending version and shows "Update available (N changes)" with "See what changed" and "Apply update". The switch is on the deck page ("Take updates automatically"). Pin to follow queues the sync as a job; follow to pin only stops future syncs. Both are safe to repeat.
- **What a sync does.** New items become new cards (at or above her minimum tier, honouring `unlock_mode` at queue time). Removed items archive their cards (progress kept). `typo` and `clarify` changes swap the content silently. `substantive` and `amendment` changes write one `content_reset` schedule event per studied card (stability capped at 3 days, due today, `reason_code` = the change kind, `ref` = `dv:<deck_version_id>`) and set `needs_recheck` with the reason `content_changed` or `amendment`, so the card shows "Updated, please re-check" and "Still correct" clears it without touching memory. During a vacation the card is held until the vacation ends. A student who skipped versions gets the worst change of the versions she missed. The fold, the golden vectors and the review-log schema are unchanged: a content reset was already a schedule event.
- **Amendment port.** F-14 is not built, so recall listens to its three events by name (`amendment_published`, `amendment_corrected` when `material` is true, `amendment_retracted`) and never imports F-14. A job (`recall.flag_amendment`, chunks of 1,000) flags platform items whose `reference_keys` share a provision key with the event (`needs_editor_check`, `check_reason = amendment`, a `RecallAmendmentFlag` row; students see "Under review after amendment" on the deck item) and puts a "Check against the amendment" chip on her **own** cards with a matching key. Her own cards get no schedule event and no change of memory. A retraction removes what that amendment set and nothing else. Without `provision_keys` the match is by chapter and only for platform items. `provision_keys[]` is a proposed extension of the F-14 events (as in the ERD); nothing breaks while it is missing.
- **Scheme switch.** `coverage.switch_scheme` now emits `enrollment_scheme_changed(user_id, old_scheme_id, new_scheme_id)` after commit (recall also listens for the name the PRD proposed, `enrollment_scheme_switched`). A job moves her own cards through the F-02 chapter map: one confirmed row moves the card at once; a split, or several confirmed rows, or no confirmed row parks it under "Needs a new chapter" (`/app/recall/chapters`, card filter `state=needs_chapter`) with the map's candidates first. Rows an editor has not confirmed (`needs_review`) are never used automatically, only offered as suggestions: a wrong automatic move of a student's own cards is harder to see than a wrong carry of coverage progress. Platform deck cards are not moved; a deck for the previous scheme shows "This deck is for the old syllabus".
- **Offline.** The pack carries `needs_recheck`, `recheck_reason`, `updated`; a review result or "Still correct" patches the stored pack by `rev`, and an older pack from R1 still parses (defaults).

### 8.2 What staff see (Django admin, Platform deck versions)

- A draft version page shows "Before you publish": the per-item diff against the live version (item reference and change kind, never card text), how many active followers will be updated and how many are pinned, and how many studied cards will come back for a re-check.
- Publishing a version with a `substantive` or `amendment` item needs a change note (`422 changelog_required`; the admin shows "Not published"). Students read the note in the update sheet.
- After a publish, the live version page has an "Updates panel": follower sync jobs queued, running, done, failed for that version. List action **Retry the failed follower updates** (needs `recall.deck.publish`, writes an audit row `deck_sync_retry`) requeues the failed jobs with their attempts reset. A failed single subscription also gets its own retry job automatically (`recall.sync_subscription`), so one bad subscription never stops a chunk.

### 8.3 Operations

| Question | Answer |
| --- | --- |
| How long until followers have it? | The publish queues `recall.sync_subscribers` (chunks of 200). The 5-minute tick runs it with a 20 s budget and chained chunks continue in the same tick while time remains. 1,000 followers took 53 s of work, so three ticks; worst case 15 minutes after the publish (PRD target: 15 minutes). Above about 1,000 followers per deck, call the tick more often or run the worker; the number scales linearly (about 53 ms per subscription) |
| A follower did not update | Look at the Updates panel. Failed jobs: run the retry action. A student can also open the deck and apply the update herself (idempotent) |
| A mistake in a published version | Publish a new version that fixes it. A version is never edited. Followers on the bad version get the fix as a normal update; cards already reset stay "to re-check" until she confirms |
| Roll the feature back | The flag `recall_system` hides everything. Code rollback is safe: the two new tables and columns are additive and ignored by older code; the sync stops, nothing is lost |
| Export and erase | Export has the new card columns (`needs_recheck`, `recheck_reason`, `recheck_ref`), subscription fields (`follow_updates`, pinned, synced and pending version, `last_sync_at`) and a `chapter_remaps` block. Erase deletes her `RecallChapterRemap` rows and the sync jobs of her subscriptions, and leaves platform content and amendment flags alone. Job payloads hold ids and provision keys only, never card text |

### 8.4 Capacity (same sandbox as the R1 note: Linux x86-64, 2 CPUs, shared with the database and the dev server)

Command: `DATABASE_URL=postgres://... python scripts/e2e/recall-r2/capacity_w2.py`.

| Measure | Target | Result |
| --- | --- | --- |
| Update preview, 500 cards, 50 changes (p95 of 20 calls) | under 300 ms | 100 ms (p50 92), met |
| Apply, 500 cards, 50 changes, over HTTP (first call) | under 2 s | 412 ms, 50 cards reset, met; a second apply 124 ms, no change; the same sync in-process 247 ms |
| Fan-out to 1,000 followers of a 30-card deck | within 15 minutes of the publish | 53 s of work in 6 chunk jobs, 0 failed, all 1,000 on the new version; three 20 s ticks, so **15 minutes in the worst case with a 5-minute tick: met with no margin** |

The two paths the sync shares with reviews (the card write and the fold) are unchanged, so the R1 and R2-W1 numbers stand.

### 8.5 Not built in W2 (on purpose)

A student-facing history of past updates, a per-card "what changed" view, daily "2 cards changed" notifications (F-13), and deck-level sharing (R2 later waves). The staff summary shows counts only.

### 8.6 Proof

Ruff and ruff format on `apps/api`; pytest `modules/coverage modules/recall modules/syllabus core` on SQLite (1,362 passed, 39 skipped that need PostgreSQL) and `modules/coverage modules/recall core` on PostgreSQL 16 (1,292 passed); `scripts/recall-seed-check.py`; recall, observability and features web unit tests (350 passed); `scripts/e2e/recall-r1/run.py` (42 checks) and `scripts/e2e/recall-r2/run.py` (R2-W1 and the W2 section) on PostgreSQL, all passed; `capacity_w2.py` above. Manual device and browser checks are not done (your standing rule).

## 9. R2, wave W3: Recall with Coverage, Tracker and Today, strength on chapter pages, paste import (flag `recall_system`, no new flag)

Built on top of R1, R2-W1 and R2-W2. Specs: PRD FR-F15-61 to FR-F15-65, FR-F15-73 and FR-F13 (P2); ERD sections 3, 4 and the events table. Everything below is behind `recall_system` (fail closed). **No new flag, no new environment variable, no new throttle scope** (the import uses the existing `recall_write` scope). The only schema change is migration `0006`: one JSON column, `recall_session.chapter_passes` (default `[]`), which is the whole memory of the 7 day rule.

### 9.1 What it does for a student

- **Chapter recall pass (FR-F15-64).** A chapter's set is her active mandatory and important cards in it. When the set has at least 5 cards and at least 80% of them were reviewed Hard or better in the last 7 days, the chapter counts as revised: coverage gets ONE `revision_done` (source `system`) for it, so the chapter's revision schedule and "Due for revision" move on. It happens after a session closes, never while she reviews, and at most once per chapter per 7 days. It only counts while her setting "Recall counts as revision" (`recall_counts_as_revision`, on by default) is on. A student who is not enrolled, whose enrolment is archived or belongs to another scheme simply gets nothing and no error; a vacation does not pause the check (she reviewed the cards, so the chapter counts).
- **Recall strength on the chapter page (FR-F15-65).** `/app/syllabus/$subject/$chapter` shows a "Recall" section: "Recall strength 82%, 6 cards due" (or "Not reviewed yet, 3 cards to learn", or "nothing due") and a "Review cards" button to `/app/recall/review?chapter=<id>`. Hidden with the flag off, while loading and for a chapter where she has no cards. It refreshes after a review has synced.
- **Revision boost and deep links (FR-F15-63).** For a chapter that is due for revision, its mandatory cards come first in her daily queue, the catch-up list, the offline pack's plan and the quick revision plan (inside each group the usual priority order stays). A "Review cards" link sits under each row of `/app/revision`. The review screen honours `?chapter=<id>` (the id alone means "review this chapter"); a chapter she has no cards in, or an id that is not hers, shows "No cards to review in this chapter" with "Make a card" and "Back to revision".
- **Tracker (FR-F15-73, opt-in).** With auto capture switched on in the time tracker settings (off by default), a finished recall session adds ONE tracker session with `source=auto` and activity "revision", under the tracker's own auto rules: no live timer running, no overlap with recorded time, the 4 hour daily cap, and at least one minute. The session carries a chapter only when one chapter holds at least half of its reviews. Closing again or replaying the event adds nothing.
- **Import (FR-F13).** `/app/recall/cards/new?mode=import` ("Import many"): paste one card per line (`front :: back`) or a CSV with the header `kind,front,back,chapter`, or choose a file. "Check rows" shows every row in a table with its problem in words; "Import N rows" creates only the valid ones, all or nothing against her plan. Kinds with at most two required fields can be imported (pointer, formula, definition, mnemonic, case law, cloze); a section card needs the form. A card she already has, or a row repeated in the paste, is a row error, never a silent duplicate. A retry of the same paste cannot make the cards twice.

### 9.2 What staff and integrations do

- **Staff:** nothing new in the Django admin. The rule constants (5 cards, 80%, 7 days) live in `modules/recall/domain/chapter_pass.py` and are pinned by `domain/tests/vectors/chapter_pass_cases.json`; changing one is a code change with a test change.
- **F-13 Today (not built):** `core/today_port.py` is the port, the same shape as `core/plans.py` and `core/recall_port.py`: `register_task_provider(key, fn)`, `NullTaskProvider`, `collect(user_id, now=)` (a provider that raises or answers nothing is left out, so one module can never blank Today). `RecallConfig.ready` registers `provide_today` through `provider.today_tasks`, which answers an empty result when the flag is off for the student. Tasks: "Recall: N cards due", "Forgotten: top 5", "Re-check after amendment" and, within 45 days of the exam, "Quick revision: N cards today"; each has `est_minutes` from her own median seconds per card (12 s until she has 30 reviews) and a `target` path under `/app/recall`. There is no Today UI.
- **F-14 and the rest** are unchanged. Coverage does not import recall: the coverage rows reach recall only through `adapters/coverage.py`, and the "Review cards" link and the recall card are composed by the routes (`app.revision`, `app.syllabus.$subject.$chapter`).

### 9.3 Decisions and deviations

| Question | Decision |
| --- | --- |
| PRD "7 days" or ERD "ISO week" for the pass | **Rolling 7 days.** Reviews count while younger than 7 x 24 hours (a review exactly 7 days old has left the window); a pass blocks another pass of the same chapter for 7 days from the announced pass (a pass exactly 7 days old no longer blocks). An ISO week would allow two passes on a Sunday and the Monday after, and no pass for 13 days, which is not what "once a week" means to a student. Tested at 4 vs 5 cards, 79 vs 80 of 100, and 6 days 23 h vs 7 days |
| Where the 7 day memory lives | In `recall_session.chapter_passes` (the pass is written on the session that earned it), so no new table and the cool-down is one indexed read of the last 8 days of her sessions. Export and erase cover it (the sessions block of the export carries it; erase deletes the sessions) |
| Not on the review path | A closed session emits `recall_session_completed` (it already did); recall queues ONE light job per session (`recall.chapter_pass`, de-duplicated on the session id) and forwards the tracker session. `services/reviews.py` and `reviews_bulk.py` are unchanged |
| Replays | The job re-emits the pass the session already carries (a crash between the commit and the emit loses nothing); coverage is called with a client id derived from user, chapter and session (`uuid5`), so a replay is a no-op there; the tracker call is idempotent on a client id derived from the session id |
| Boost without touching the scheduler | `plan_queue(..., boosted=frozenset[str])` and `QuickCard.boosted` only change the sort key (boosted first, then the usual order). The fold and the golden vectors are untouched. The boost is the mandatory cards of due chapters; with no due chapter it costs one coverage read |
| Tracker extraction | `tracking.services.add_auto_session(...)` is now the one place the auto rules live; `add_auto` (Notes and the reader's reading time) calls it with activity "reading". Recall reaches it through `adapters/tracking.py` with `forward=False`, so auto time is not sent on to coverage |
| Import row limit | The ERD states none: **200 rows a call** (the same as a bulk change), 400,000 characters of pasted text. Over the limit is `422 import_too_large` and nothing is read |
| Import atomicity | One `reserve_cards(total faces)` for the whole batch (`create_card(reserve_quota=False)` for each row), inside one transaction: a full plan creates nothing (`429 quota_exceeded`). The preview also says whether the valid rows fit (`quota.fits`) |
| Review route | `?chapter=<id>` with no `source` now means `source=chapter` (the zod schema derives it); a malformed id falls back to Today as before |
| "Review cards" under every due row | Shown when the flag is on, without asking the server per row; a chapter without cards opens the calm empty state |

### 9.4 Operations

| Question | Answer |
| --- | --- |
| A student says a chapter was not counted | Check that her "Recall counts as revision" setting is on, that the chapter has at least 5 mandatory or important cards, and that 80% of them were reviewed Hard or better in the 7 days before the session closed. The job is `recall.chapter_pass` in `core_job` (ids only); a failed one is retried by the tick. The session row shows what was announced (`chapter_passes`) |
| Tracker time did not appear | Auto capture is off by default (tracker settings). It also needs the `time_tracker` flag, no running timer, no overlapping time, under 4 hours of auto time that day and at least a minute of reviews. The outcome word is logged at info level without any student text |
| Roll back | The flag `recall_system` hides the screens and the endpoints answer 403 `feature_disabled`. The code is additive: migration `0006` is one defaulted column that older code ignores; the new job type is simply not claimed if the code is rolled back |
| Export and erase | The sessions block of the export has `chapter_passes`; erase removes the sessions and the `recall.chapter_pass` jobs of the student. Imported cards are ordinary cards (origin `import_csv`, never shareable) and are covered as before |
| Privacy | Events, jobs, logs, Sentry and PostHog carry ids and counts only. The import's analytics events are `recall_import_previewed` and `recall_import_done` (row counts); the API's preview echoes a 120 character excerpt of each row back to the same student in the response body and nothing is logged |

### 9.5 Capacity (same sandbox as the earlier notes: Linux x86-64, 2 CPUs, shared with PostgreSQL 16 and the Django development server)

Command: `DATABASE_URL=postgres://... python scripts/e2e/recall-r2/capacity.py` (8 students with 5,000 cards each, an exam in 40 days). To prove that W3 does not touch the review path, the script was run on the code before W3 and on the code after it, alternating (before, after, before, after) on the same machine and the same private PostgreSQL 16, because the sandbox is shared and a single run is noisy. p95 in ms, one student at a time unless noted:

| Measure | Target | Before W3 (run 1, run 2) | After W3 (run 1, run 2) |
| --- | --- | --- | --- |
| One review with the exam horizon (40 calls) | under 200 ms | 76, 84 | 80, 80 (**did not move**) |
| Batch of 100 reviews (max of 4 calls) | under 800 ms | 384, 379 | 386, 428 |
| Today | under 300 ms | 276, 357 | 297, 304 |
| Queue, 20 cards | under 300 ms | 184, 212 | 196, 214 |
| Quick revision plan | under 300 ms | 156, 200 | 172, 184 |
| Quick queue, 20 cards | under 300 ms | 168, 240 | 176, 188 |
| Pack of 300 | under 500 ms | 212, 250 | 254, 243 |
| 8 students at once, today (p95) | under 300 ms | 1,328, 1,236 | 1,451, 1,460 |

Reading: review and batch are within the run to run spread (the batch maximum in one "after" run, 428 ms, is one slow call of four; the target is 800 ms). The read endpoints that plan a queue (today, queue, quick plan, quick queue, the pack) gained one coverage read for the revision boost (`due_revision_chapter_ids`, and one card query only when a chapter is due); the p50 moved by roughly 5 to 20 ms (for example today 208 and 224 before, 216 and 216 after) and the p95 stays inside the spread of the "before" runs for a single student. With 8 students hitting the development server at once the three read endpoints miss the 300 ms target both before and after W3 (the two cores run the database and a single-process server); the "after" runs are about 10% slower there. Production runs more than one worker. The new read, the chapter strength, took 25 ms; the import preview of 200 rows is a handful of queries (the 200 rows are checked with a fixed number of queries, one card query per created row on the real call).

### 9.6 Not built in W3 (on purpose)

Sharing and share imports, AI suggestions and AI batches, `create_card_from_question`, a student-facing history of passes or updates, any Today screen (F-13), parameter fitting, and an import of the section card kind (it has three required fields, so it stays in the form).

### 9.7 Proof

- `ruff check` and `ruff format --check` clean over `apps/api` (773 files).
- API tests: `modules/coverage modules/recall modules/syllabus modules/tracking modules/focus core` on SQLite (1,968 passed, 39 skipped by design, 0 failed) and on PostgreSQL 16 (2,007 passed, 0 skipped, 0 failed). New and extended: pure domain tests with a vector file (4 vs 5 cards, 79 vs 80 of 100, 6 days 23 h vs 7 days, the cool-down), the chapter pass service (job, replay, cool-down, off switch; unenrolled, archived and other-scheme students never raise; a vacation does not stop it), the tracker forward (saved, timer running, overlap, daily cap, off switch, idempotent replay, a failing tracker never fails the close), the boost (`plan_queue`, quick plan, queue, pack, no boost without a due chapter), the strength read (a query-count test: the same number of queries for two cards or two hundred), the Today port and provider (flag on and off, minutes, exam, vacation), import (preview, partial validity, one atomic quota check, replay, row cap, chapters by id and key, no text in the logs), the URL-conf drift test for the contract and the flag matrix for the two new paths.
- Web (clean install in a scratch copy): `pnpm typecheck`, `pnpm lint`, `pnpm format:check`, `pnpm emails:check`, `pnpm check:contrast`, the `@artha/web` tests (3,130 passed in 319 files, including new tests for the chapter card, the revision list slot and link, the review route parameter and its empty state, the import panel with its keyboard path, and the analytics allow-list) and `pnpm build:web` all pass.
- `scripts/e2e/recall-r2/run.py` on PostgreSQL: 53 checks, all passed, including the new W3 section (strength, import preview, real call and replay, the 200 row cap, 60% is not a pass and 80% over two sessions counts one revision, a second pass in the week and a replayed job add nothing, the tracker is off by default then forwards one `auto` revision session and a replay adds none, export carries `chapter_passes`, erase leaves no rows, no card text in the server log). Writing it found one real fact worth knowing: the tracker never records more time than has really passed since the session opened, so a session that answers cards in a few real seconds is "too short" however long the cards claim to have taken.
- The capacity comparison above.
Manual device and browser checks are not done (your standing rule, an accepted risk).

## 10. R2, wave W4: history of updates, "my own words", cards from mistakes (flag `recall_system`, no new flag)

Built on top of R1 and R2-W1 to W3. Specs: PRD FR-F15-17 (card from a mistake), FR-F15-21 (selection cards are private unless she attests "in my own words") and the "student-facing history of past updates, per-card what changed" that section 8.5 left out. Everything is behind `recall_system` (fail closed). **No new flag, no new environment variable, no new throttle scope** (writes use `recall_write`). One schema change: migration `0007`, a new table `recall_subscriptionupdate` (one row per update a student received on a deck). It is the smaller of the three remaining R2 pieces on purpose; **sharing (`recall_sharing`) and AI suggestions (`recall_ai`) are not in it.**

### 10.1 What it does for a student

- **Past updates of a deck.** On a deck she has, an accordion "Past updates" lists the updates she received, newest first: the day, "Version 2 to version 5 (2 versions in between)", whether "You applied it" or "Applied for you", the editors' change log, and what it did to her cards ("1 new card, 2 cards to re-check."). Closed by default; nothing is read until she opens it. A deck that never changed says "No updates yet". Updates that happened before this wave are not listed (nothing recorded them).
- **What changed in a card.** On the card page an accordion "Versions of this card": every version of its text (at most 20, newest first) with the kind of change ("Meaning changed", "Typo fixed", "Changed after a law amendment"), the day, the first lines of that version, which version her card shows, and a notice when newer versions are waiting in a pinned deck. Under it, the times the card came back for a re-check and why ("A law this card relies on was amended"). Her own cards show her edits the same way.
- **"Are these your own words?" (FR-F15-21).** A card made from a highlight, a solution or a mistake is private. On its page a panel lets her say the words are her own ("Yes, these are my own words"); the card then becomes shareable, the time is kept, and she can take it back. Manual, imported and platform cards show no panel. Sharing itself is not built: this is the state Share will read, and it is already in the export.
- **Card from a mistake (FR-F15-17).** `QuestionCardButton` ("Make a card from this") for the question bank to put on a wrong answer. The card is a pointer: the front asks "What is the rule in Section 17(5), CGST Act?", the back quotes the bank's explanation and names the source. One card per question; a second tap says "You already have a card for this question." **F-06 does not exist yet**, so nothing mounts the button and the endpoint answers 503 `question_source_unavailable` until F-06 registers its provider (9.2 below).

### 10.2 What staff and integrations do

- **F-06 registers a provider** from its `AppConfig.ready`: `core.question_port.register_question_provider(provider)` where `provider.source_for(user_id, question_id, version_id)` answers a `QuestionSource` (explanation, reference labels and keys, chapter and topic) or None. It must answer from the bank's own data and enforce who may see the question. Recall never calls a model and never invents a source. The port is the same shape as `core.recall_port` and `core.today_port`.
- **F-06 then mounts** `QuestionCardButton` from the recall barrel on the wrong-answer screen (`questionId`, `versionId`, optional `onMade`). It renders nothing while recall is off for the student.
- No new admin screen. The staff deck summary still shows counts only.

### 10.3 Decisions and deviations

| # | Decision | Why |
| --- | --- | --- |
| W4-1 | The history of updates is a new table, written by the sync | `pinned_version` is overwritten on every apply, so the start of her history cannot be derived. One row per `(subscription, to_version)`, written in the transaction that moves her version, so a replay changes and writes nothing. Ids, numbers and counts only. Updates before W4 are not listed. |
| W4-2 | `trigger` is `manual` (she pressed Apply) or `auto` (the follow sync) | Stated in her words in the list. A pin switched to follow is queued, so its update is `auto`. |
| W4-3 | "What changed" shows text, not a diff | Versions are immutable and short; the first 300 characters of each version are enough to see what moved and are read by the owner only. A word-level diff is a later refinement. |
| W4-4 | The card from a question never takes text from the client | The ERD says never from model memory; here it is also never from the browser. The body is `{question_id, version_id}`. |
| W4-5 | One card per question and student, whatever the version | The unique source key is `(owner, questionbank, question id, question_mistake)`; the version is kept in the locator. A deleted card can be made again. |
| W4-6 | A bank chapter that is not in her scheme leaves the card Unsorted | Refusing would lose a mistake she wanted to keep. An explicit `chapter_id` that is not hers is still 422. |
| W4-7 | Attestation applies to origins `selection`, `solution`, `mistake` only | Manual cards are shareable already; imports are never shareable (W3); platform cards are not hers. The others answer 422 `attestation_not_needed`. Editing a card does not clear the statement. |
| W4-8 | No new audit action | `attest_own_words` existed in the audit enum since R1; the detail carries `own_words` true or false. |
| W4-9 | The explanation on the back is cut at 1,500 characters and flattened | The card profile refuses headings and images and allows 4,000 characters; a good explanation must never fail the save. |

### 10.4 Operations

- Apply migration `0007` (a new table, no change to existing ones; older code ignores it). Rollback: remove the three routes and the sync write; the table can stay.
- Erase deletes the table's rows with the student; export carries `subscription_updates`.
- No job, tick or scheduler change. Nothing runs on the review path.
- Logs carry counts only. A test proves no card text reaches the log for a card from a question.

### 10.5 Reads (same sandbox as the earlier notes)

| Read | Measured |
| --- | --- |
| `GET subscriptions/{id}/history/` | 52 ms over HTTP (first call, a deck with two updates) |
| `GET cards/{id}/changes/` (7 versions) | 58 ms over HTTP (first call), at most 12 queries whatever the number of versions |

The review path is untouched; the capacity script was re-run and its numbers are in 10.7.

### 10.6 Not built in W4 (on purpose)

Sharing by link and its abuse controls (`recall_sharing`), AI-suggested cards (`recall_ai`, built in W5), a word-level diff in "what changed" (built after W4, see section 11.1), daily "N cards changed" notifications (built after W4 as a Today task, see section 11.1), the Today screen, and the first mount of the question button (F-06).

### 10.7 Proof

Ruff and ruff format on `apps/api` (clean); pytest `modules/coverage modules/recall modules/syllabus modules/tracking modules/focus core` on SQLite (2,029 passed, 39 skipped that need PostgreSQL) and on PostgreSQL 16 (2,068 passed, 0 skipped, 0 failed); new API tests: 16 for the card from a question, 11 for the statement, 12 for the history and the card read (one asserts at most 12 queries for a card with seven versions), 10 for the pure card builder, 4 for the port, and the URL-conf contract drift test and the flag matrix over the four new paths; `pnpm check` (typecheck, lint, format, emails, contrast, 3,160 web tests in 322 files, production build) all green, 30 of those tests are new for W4 (and a few fixtures changed), and every new component has an axe test; `scripts/e2e/recall-r2/run.py` on PostgreSQL (W1 to W4 sections), all checks passed, including the history after a follower's update and her own, attest and take back, the 503 of the question card, the export of `subscription_updates`, the erase and the log search for card text.

Capacity (same sandbox): review p95 76 ms alone, as in W3 (nothing new runs on the review path); `capacity_w2.py` on the original code and on W4: update preview p95 88 ms and 86 ms, apply over HTTP 340 ms and 356 ms, fan-out to 1,000 followers 48.3 s in both, so the extra history row per sync is not measurable. The 8-students-at-once misses on today, quick plan and quick queue were already there before W3. Manual device and browser checks are not done (your standing rule).


## 11. R2, wave W5: AI-suggested cards (new fail-closed flag `recall_ai`), and the W4 leftovers

### 11.1 W4 leftovers

- **Word diff.** "Show what changed since version N" on the card page compares a version with the one before it, word by word (`lib/wordDiff.ts`, pure, 400 words at most, longer texts show plain). Added and removed words are `<ins>` and `<del>` with a hidden "added:" or "removed:" so the change is never colour only.
- **"N cards changed".** The Today port now carries a `cards_changed` task: the sum of the added, rechecked and silently changed cards of the student's deck updates in her study day (`selectors/today.cards_changed`). There is no Today screen yet; whoever builds it renders the task.

### 11.2 What it does for a student

At `/app/recall/suggestions` (a "Suggest with AI" link on the card creator while the flag is on) she chooses a chapter, the sources (her notes, her wrong answers when F-06 exists, or pasted text), and a number of cards. She must first read and agree to a versioned notice. The AI drafts cards in the background; each draft shows the exact quote from her material that backs it. She adds it, edits it first, or says it is not useful. **Nothing becomes a card until she accepts.** Accepted cards are private (`shareable=False`) and marked `origin=ai_suggestion`. She can withdraw her agreement at any time, which cancels running batches and deletes drafts she has not decided on.

### 11.3 The rule that keeps it honest

A draft is kept only if its `evidence_quote` appears verbatim in the text that was sent (whitespace and case ignored) and its fields pass the same validators as a hand-made card. Anything else is dropped and counted ("2 drafts were left out"). The prompt is versioned (`recall.suggest` v1).

### 11.4 Decisions and deviations

| # | Decision | Why |
| --- | --- | --- |
| W5-1 | Fail-closed flag `recall_ai`, plus env kill switch `RECALL_AI_ENABLED`, plus a shared daily budget `RECALL_AI_DAILY_BUDGET_PAISE` | It costs money and sends her text to Google |
| W5-2 | `RECALL_AI_CONSENT_APPROVED` must be `true` before anyone can use it | The notice wording in `domain/ai_consent.py` is a draft; the owner (and counsel) approve it first |
| W5-3 | Consent is stored with its version; a new version asks again | She agrees to what she read |
| W5-4 | Quota is charged by one conditional UPDATE before the call; unused suggestions and failed or cancelled batches are refunded | No double spending under concurrent taps |
| W5-5 | Free plan: 3 batches and 30 suggestions a day (India day), from `recall_quotaplan` | Staff can change it without a deploy |
| W5-6 | One active batch per chapter; the same `client_id` joins the same batch; same source, kinds and count within 7 days reuse the cached answer | Taps and retries never pay twice |
| W5-7 | Rejected drafts are remembered as a fingerprint for 90 days, never as text | The same card is not suggested again |
| W5-8 | Pasted text is stored on the batch only until the job ends; no student text in logs, job payloads or the ledger | Privacy; tests prove it |
| W5-9 | Notes registers a source through `core/suggestion_source_port.py`; `wrong_answers` answers 422 `source_unavailable` until F-06 registers one | Modules never import each other's models |
| W5-10 | `recall.suggest` is a heavy job: it runs only in the worker (`manage.py run_worker`), not in the cron tick; drafts expire after 30 days through a light daily job | Same split as PDF work |
| W5-11 | `ai/consent/withdraw/` is an open path (works with every flag off) | She can always take her agreement back |

### 11.5 Operations

- Apply migration `0008` (five new tables and three consent columns on `recall_settings`; older code ignores them).
- Set on the API **and on the worker**: `GEMINI_API_KEY`, `GEMINI_DATA_TIER=paid`, `RECALL_AI_ENABLED=true`, `RECALL_AI_CONSENT_APPROVED=true` (only after the notice is approved), `RECALL_AI_DAILY_BUDGET_PAISE`. Then open the `recall_ai` flag for the beta cohort. Rollback: switch the flag or `RECALL_AI_ENABLED` off; data can stay.
- Erase deletes batches, drafts, reject fingerprints, call ledger rows and usage rows with the student; export carries `ai_suggestions`.
- Logs carry counts only.

### 11.6 Not built in R2 (on purpose)

Sharing by link (`recall_sharing`), the `wrong_answers` source until F-06 registers a provider, the Today screen.

### 11.7 Proof

Backend tests: pure rules (evidence check, parsing, cost), the full API (consent, request, reuse, quota and refunds, accept, edit, reject, expiry, erase, export, privacy), the URL contract drift test and the flag matrix. Web tests: pure helpers, the screen flow with axe, and the analytics allow-list. Run results are in the hand-over message; manual device checks are not done (your standing rule).
