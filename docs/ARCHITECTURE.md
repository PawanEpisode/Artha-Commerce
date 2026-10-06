# Architecture

## System overview

```
Browser (TanStack Start SSR + SPA)
   |  public pages: server-rendered HTML with SEO/OG tags (Vercel, apps/web)
   |  auth: supabase-js  ----------------------->  Supabase Auth (Google, email OTP)
   |  analytics: /ingest proxy ----------------->  PostHog
   |  errors ---------------------------------->  Sentry
   |
   |  Authorization: Bearer <Supabase JWT>
   v
Django REST API (Vercel serverless, apps/api)
   |  verifies JWT via JWKS, no sessions
   |  services/selectors -> Postgres via pooler  ->  Supabase Postgres (Mumbai)
   |  integrations/gemini.py ------------------->  Google AI Studio (Gemini)
   '  errors ---------------------------------->  Sentry
```

Key decision: **Supabase for identity and storage of record; Django as the single gateway for application data.** The browser uses supabase-js only for sign-in. This keeps business rules in one place, lets us enforce rules the database cannot, and keeps the Supabase Data API closed.

Later, Supabase **Storage** (notes attachments, PDFs) and **Realtime** (live study rooms) can be used from the browser with signed URLs/RLS policies added deliberately per feature.

## Frontend: module-driven architecture

```
routes -> modules -> @artha/design-system (package) ; modules -> lib
```

- **Routes** are file-based, URL = screen. They only declare `head` (SEO), `loader`, and render one container.
- **Modules** own a feature end to end: `components` (presentational), `containers` (state/data), `hooks`, `lib` (pure logic), `data`, `index.ts` (public API).
- **Container/presentational** keeps UI reusable and testable: components receive props, containers connect data.
- **Design system** is its own workspace package, `packages/design-system` (`@artha/design-system`): tokens, shadcn-style primitives, layout and motion helpers. It is the only source of visual decisions and has no product knowledge, so it can later power other apps (admin, mobile web).
- **Catalog** (`modules/catalog`) is the shared source of truth for courses and features. It drives landing, detail pages, footer, sitemap.
- **Server data** will flow through TanStack Query hooks calling `lib/api.ts` (adds the Supabase token). Static public content uses route loaders so it is server-rendered for SEO.

### Theming and responsiveness

- **Four theme choices**: Reading (default, warm paper tone), Light, Dark and **System**. System is stored as the value `system` and behaves as Light from 6 am to 6 pm and Dark from 6 pm to 6 am on the device clock, switching by itself while the page is open.
- **How it works**: `data-theme` on `<html>` selects the token set in `packages/design-system/src/styles.css` (`reading` lives on `:root`, so it also works without JavaScript). Dark also sets the `.dark` class. An inline script in `<head>` paints the right theme before first paint (no flash); `ThemeProvider` keeps it in sync afterwards. The pure logic is in `src/theme/theme.ts` and unit tested, including the 6 am and 6 pm switch.
- **Accessibility is enforced**: `pnpm check:contrast` verifies WCAG contrast for every text, button, focus-ring and form-border pair in all three palettes (body text AAA, UI text AA, focus and borders 3:1). It runs in CI.
- **Icons**: Lucide, imported only from `@artha/design-system` (ESLint blocks direct `lucide-react` imports).
- **Responsive**: mobile first. Every screen must work from 320 px to desktop with no horizontal page scroll and 44 px touch targets. See `.claude/skills/ui-quality-checklist`.

### Auth flows

Supabase Auth is the identity provider; the web app talks to it through `modules/auth` (`lib/auth-api.ts`). Flows: Google, email code or magic link, password sign-in, sign-up with confirmation, forgot and reset password, invite, change email and reauthentication (code by email before a sensitive change). Email links go to `/auth/confirm?token_hash=...&type=...` and are verified in the browser, so mail scanners cannot use up one-time tokens. Branded email HTML is generated from `packages/email-templates` into `supabase/templates/`, and `supabase/config.toml` applies templates and settings with the Supabase CLI. Setup steps: `docs/SETUP.md` sections 2.3 and 2.3.1.

### Public vs private

| Area | Rendering | Indexed |
| --- | --- | --- |
| `/`, `/features/*`, `/courses/*` | SSR, full metadata | yes |
| `/login`, `/signup`, `/auth/*` | SSR shell | no |
| `/app/*` | client-guarded workspace | no |

### Planned workspace routes (all URL based)

`/app` dashboard, `/app/account`, `/app/planner`, `/app/tracker/$subject`, `/app/tests/$id`, `/app/notes/$id`, `/app/revision`, `/app/ask`, `/app/settings`. Filters, tabs and selected entities live in the URL (search params validated with zod).

## Backend: layered Django

```
views (HTTP) -> services (writes, rules) / selectors (reads) -> models -> Postgres
integrations/ (Gemini)  core/ (auth, errors, pagination, health)
```

- **Stateless** instances behind Vercel's autoscaling: no sessions, no local state, JWT verified per request (JWKS cached).
- **Connection management**: runtime through Supabase's transaction pooler (pgbouncer), prepared statements and server-side cursors disabled, `conn_max_age=0`. Migrations use the direct connection.
- **Availability**: Vercel multi-instance serverless + Supabase Pro managed Postgres (backups, PITR add-on). `/health/` (liveness) and `/health/ready/` (readiness) for monitors.
- **Security**: Supabase Data API disabled, RLS on every public table after migrate, DRF throttling, CORS allow-list, HSTS in production, per-user scoping.
- **Request retries (web)**: one policy for every read, `apps/web/src/lib/retry.ts`. A failing request is tried at most 5 times in total (the first call included), with back-off and the server's `Retry-After` honoured; a 4xx answer other than 408, 425 and 429 is final and never repeated. Writes are not retried automatically; queued offline writes follow the same cap. Change `MAX_API_CALLS` there, nowhere else.
- **Durability**: all state in Postgres. Long or retryable work is designed as idempotent jobs (Supabase `pg_cron` / Vercel Cron) rather than inside requests.
- **Consistent contract**: errors are `{"error": {code, message, details}}`, lists are paginated.

### Domain model roadmap (not yet built)

`profiles` (done) -> `catalog` (course, level, subject, chapter: managed in DB, seeded from official syllabi) -> `planner` (plan, plan_task) -> `tracker` (chapter_progress) -> `tests` (question, attempt, answer) -> `notes` -> `revision` (card, review) -> `ai` (conversation, message) -> `notifications` (amendments).

## Observability

- **Sentry**: browser errors + traces (10%), api exceptions; source maps uploaded on web build.
- **PostHog**: `$pageview` on route change (SPA aware), `identify` on login. Name product events `noun_verb`; no PII beyond user id and email on identify.

## Scaling path

1. Today: two Vercel projects + Supabase Pro covers early growth comfortably.
2. Cache public reads (CDN headers, materialised views) before adding infrastructure.
3. Add a worker (queue + cron) only when AI generation or imports exceed request time limits.
4. Read replicas / compute upgrades in Supabase when query load demands it.
