# ArthaCommerce

Exam preparation workspace for CA, CS and CMA students in India. Public marketing and feature pages are indexable and
shareable (WhatsApp previews); signed-in students get a workspace that stores their plan, progress and notes.

## Stack

| Layer | Choice |
| --- | --- |
| Web | TanStack Start (React 19, SSR), TanStack Router + Query, Tailwind CSS v4, shadcn/ui (Radix), `motion` (Framer Motion) |
| API | Django 5.2 LTS + Django REST Framework, stateless, Supabase JWT auth |
| Data/Auth/Storage | Supabase (Postgres, Auth, Storage, Realtime). Django is the only writer of app data |
| AI | Google AI Studio (Gemini), called only from the API |
| Observability | Sentry (web + api), PostHog (web, proxied via `/ingest`) |
| Design system | `packages/design-system` (`@artha/design-system`): tokens, shadcn-style primitives, layout, motion |
| Quality | ESLint (flat) + Prettier + Husky + lint-staged + commitlint (Conventional Commits), Vitest, pytest, ruff, CI, Dependabot, gitleaks |
| Hosting | Vercel: two projects from one monorepo (`apps/web`, `apps/api`) |

## Repo map

- `apps/web`: frontend. `src/routes` (thin), `src/modules/*` (features), `src/styles.css` (Tailwind entry), `src/lib` (env, supabase, api)
- `packages/design-system`: the only place for tokens, UI primitives, layout helpers, motion and the logo. Imported as `@artha/design-system`
- `apps/api`: backend. `config` (settings, urls), `core` (auth, errors, health), `modules/*` (domain apps), `integrations/*` (Gemini)
- `docs`: `ARCHITECTURE.md`, `SETUP.md` (platform steps and env vars), `product/FEATURE_MAP.md` (what we are building), `templates/` (PRD and ERD templates)
- `.claude/skills`: task playbooks. Read the relevant one before starting work.

## Commands

```bash
pnpm install
pnpm dev:web                 # http://localhost:3000
pnpm check                   # typecheck + lint + format check + tests + build
pnpm lint:fix && pnpm format # auto-fix
cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
python manage.py migrate && python manage.py runserver 8000
pytest && ruff check .
```

## Non-negotiable rules

1. **Modular.** Every feature or issue is a self-contained module (`src/modules/<name>` on web, `modules/<name>` on api) with a public `index.ts` barrel. Import other modules only through their barrel.
2. **Separation of concerns.** Web: routes -> containers (state, data) -> presentational components (props only). API: views -> services (writes) -> selectors (reads) -> models. Business logic never lives in views or JSX.
3. **DRY.** Reuse before creating. Shared UI goes in `packages/design-system`; shared data (courses, features) lives once in `modules/catalog`.
4. **Design system only.** No raw hex or arbitrary colours. Use semantic tokens (`bg-primary`, `text-muted-foreground`). Compose from `@artha/design-system`. Details: `.claude/skills/design-system-usage`.
5. **URL-driven.** Every screen and meaningful state has a URL. Public pages set SEO via `buildHead()`. Private pages use `noindex`.
6. **Secrets.** Only `VITE_*` values reach the browser, and only public ones. Gemini and service keys exist only on the API. Never commit `.env*`.
7. **Types and validation at the edges.** Zod/typed env on web, DRF serializers on api.
8. **Tests.** Pure logic and every API endpoint get tests. Run typecheck, lint, build and pytest before declaring done.

## Quality gates (automatic)

- `pre-commit`: lint-staged runs ESLint `--fix`, Prettier and ruff on staged files
- `commit-msg`: commitlint enforces Conventional Commits, e.g. `feat(web): add syllabus tracker` (scopes: web, api, ds, docs, ci, deps, db, product, tooling)
- `pre-push`: typecheck and unit tests
- CI repeats everything on every PR. Never bypass hooks with `--no-verify`; fix the cause.

## Workflow for any task

Follow `.claude/skills/new-feature-module`. Keep changes small and reviewable, one concern per PR.

## Product status

First milestone shipped: foundation, design system, SEO, public pages, auth wiring, API skeleton.
The product scope is captured in `docs/product/FEATURE_MAP.md`. PRD + ERD written so far, in build order: F-02 Syllabus Structure and Coverage, F-01.1 Pomodoro Focus Timer, X-04 Ingestion Service (`docs/product/prd`, `docs/product/erd`). Next: F-01.2 Time Tracker + Analytics. The feature list in `modules/catalog/features.ts` is still provisional.
