# F-16 Personalization, Onboarding and Profile: rollout

What ships: the `profiles` API module (profile, avatar, onboarding state machine, last visit, account export and delete), study targets and daily minutes in `coverage` (migration 0004), and the web modules `personalization` (onboarding, profile, targets, data) and `workspace` (the `/app` home). Course-scoped `/courses` and `/features` live in `courses` and `features`. Read this with `docs/F-02-ROLLOUT.md`.

## A. What you must configure

1. **PostHog flags.** Create `personalization` (gates the new onboarding, the `/app` gate, last-visit restore and the landing redirect), `profile_avatar` (avatar upload), `study_targets` (targets step and settings). All fail open: with no flag, a feature is on. Turning `personalization` off restores the original two-step coverage setup and an ungated `/app`.
2. **Supabase service role key.** `SUPABASE_SERVICE_ROLE_KEY` on the API project only (avatar writes and account deletion). Never a `VITE_*` variable. See `docs/SETUP.md` 2.6.
3. **Avatar bucket.** Public bucket `avatars`, 1 MB, `image/webp` (`supabase config push` or by hand).
4. **Migrations (once per environment, from your computer).** `cd apps/api`, export `DJANGO_SECRET_KEY` and `DIRECT_DATABASE_URL`, then `python manage.py migrate`. It applies `profiles.0003_profile_personalization`, `profiles.0004_backfill_onboarding` (marks every existing student as onboarded at the current version, so nobody is pushed through the flow) and `coverage.0004_study_targets_and_daily_minutes`. Row Level Security is switched on after the migrate as in earlier features.
5. **Throttles** (`config/settings.py`): `profile_write` 30/min, `avatar_write` 10/hour, `lastvisit_write` 20/min, `onboarding_write` 60/min, `account_export` 3/hour, `account_delete` 3/day.
6. **Sentry.** Nothing to set. The last-visit beacon is scrubbed in `before_send` (its body carries a token).
7. **Cron (optional).** `python manage.py sweep_avatars` removes avatar files no profile points to. Run it weekly.

## B. Things to know

- Onboarding status comes from the server (facts over flags). A student on the new flow who has not finished is sent to `/app/onboarding?next=<where they were going>`; if the API is down a student known to be finished is let through.
- The last-visit beacon is `POST /me/last-visit/` with the token in a `text/plain` body (1 KB cap), so it works from `pagehide`. Only paths on the allow-list are stored (`profiles/domain/restorable.py`, mirrored in `personalization/lib/restorable.ts`, both tested against `tests/fixtures/restorable_cases.json`).
- The landing page and `/courses` carry one tiny inline script each. They read the Supabase session key (`^sb-.+-auth-token$`) to send a signed-in student straight to the home. Crawlers and guests get the public HTML unchanged.
- `/` is the signed-in course home. `/courses?all=1` ("Explore other courses") is never redirected.
- Account deletion runs the registry in `core`: each module registers an exporter and a deleter, so a later feature adds one registration, not a change here.
- The vestigial columns left by the old coverage onboarding are kept for two releases. Drop them in a later migration.

## C. Check as a signed-in student

1. New email account: sign up, confirm. You land on `/app/onboarding`, one step per screen, the step in the URL, Back works, reload resumes. Skip an optional step, finish, see the celebration, land on `/app`.
2. Deep link: open `/app/tracker` signed out, sign in. You finish onboarding and arrive on `/app/tracker`.
3. `/app` home: Today, Continue, Revision, Progress, Setup. Switch `time_tracker` off: Today disappears and nothing else changes. Go offline: cards show the Offline badge.
4. Visit a chapter, close the tab, open the landing page: you are taken back to that chapter. Sign out and in on another device: same.
5. Profile: change name, upload a photo (crop, zoom), choose a preset, remove. Try a PNG over 1 MB and a tiny image: clear messages.
6. Targets: pick a preset, lower one below what you logged (allowed, nothing is deleted), log past the cap (blocked with the reason), set 0 (activity hidden).
7. Account: export (JSON downloads), delete (type to confirm, you are signed out, the account and avatar are gone).
8. `/courses` while signed in goes to `/`; `/courses?all=1` stays and links back; `/features` names your course and lists unused tools first.
9. All four themes, keyboard only, 320 px wide.

## D. Support and operations

- To pull a student back through onboarding, bump `ONBOARDING_VERSION` in `profiles/domain/onboarding.py`; only new mandatory steps are asked.
- Events (PostHog): `onboarding_started`, `onboarding_step_viewed`, `onboarding_step_completed`, `onboarding_step_skipped`, `onboarding_completed`, `onboarding_gate_redirected`, `avatar_*`, `study_targets_changed`, `activity_log_blocked`, `confidence_blocked`, `profile_name_changed`, `last_visit_restored`, `landing_redirected`, `toast_shown`, `workspace_viewed`, `workspace_widget_clicked`, `courses_scope_toggled`, `account_exported`, `account_deleted`, `coverage_prompt_opened`, `study_home_viewed`, `feature_opened`. No names, emails or free text are sent.
- `last_visit_restored`, `landing_redirected`, `profile_name_changed`, `confidence_blocked` and `toast_shown` are emitted too. Notes: `confidence_blocked` fires when the locked picker appears (disabled buttons take no clicks); `toast_shown` sends the toast id and variant only, errors and warnings always and the rest sampled at 10%, and toasts without a stable id are skipped; `landing_redirected` fires on the `/app?from=landing` path only, because the inline scripts on `/` and `/courses` run before PostHog loads.

## E. Known limits

- `workspace_viewed` reads which widgets are on screen two seconds after load.
- Last-visit restore never overrides an explicit deep link.
