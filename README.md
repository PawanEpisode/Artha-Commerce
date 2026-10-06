# ArthaCommerce

Exam preparation workspace for CA, CS and CMA students in India.

- **Web**: TanStack Start, Tailwind v4, shadcn/ui, Motion: `apps/web`
- **API**: Django + DRF on Supabase Postgres: `apps/api`
- **Design system**: `packages/design-system` (live style guide at `/design-system` when the app runs)
- **Product**: [Feature map](docs/product/FEATURE_MAP.md) · [PRD/ERD templates](docs/templates) · PRD/ERD: [Syllabus + Coverage](docs/product/prd/F-02-syllabus-structure-and-coverage.md) ([ERD](docs/product/erd/F-02-syllabus-structure-and-coverage.md)) · [Pomodoro](docs/product/prd/F-01.1-pomodoro-focus-timer.md) ([ERD](docs/product/erd/F-01.1-pomodoro-focus-timer.md)) · [Personalization + Onboarding](docs/product/prd/F-16-personalization-onboarding-profile.md) ([ERD](docs/product/erd/F-16-personalization-onboarding-profile.md), [rollout](docs/F-16-ROLLOUT.md)) · [Ingestion](docs/product/prd/X-04-ingestion-scraping-service.md) ([ERD](docs/product/erd/X-04-ingestion-scraping-service.md))
- **Docs**: [Setup per platform and env vars](docs/SETUP.md) · [Architecture](docs/ARCHITECTURE.md) · [Engineering rules](CLAUDE.md)
- **Skills/playbooks**: `.claude/skills/*`

Quick start:

```bash
corepack enable && pnpm install
cp apps/web/.env.example apps/web/.env.local
pnpm dev:web
```

Commit rules and hooks: see [CONTRIBUTING.md](CONTRIBUTING.md).

The site works without any keys (auth, analytics and error reporting switch on when env vars are present).
