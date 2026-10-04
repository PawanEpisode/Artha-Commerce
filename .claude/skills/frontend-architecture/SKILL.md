---
name: frontend-architecture
description: Use when creating or editing anything under apps/web. Module-driven structure, container/presentational pattern, routing, data fetching and env rules.
---

# Frontend architecture

## Layout

```
src/
  routes/            thin TanStack file routes (head + loader + one container)
  modules/<name>/    feature modules
    components/      presentational, props in / JSX out, no data fetching, no router hooks
    containers/      own state and data, compose components
    hooks/           useX (TanStack Query, local state)
    lib/             pure functions, no React
    data/            static content
    index.ts         PUBLIC API of the module
  design-system/     tokens (styles.css), layout (Container, Section), motion (Reveal), Logo
  components/ui/     shadcn primitives (Button, Card, ...)
  lib/               env.ts, supabase.ts, api.ts, utils.ts (cross-cutting only)
```

## Rules

- **Routes are thin.** `createFileRoute(...)({ head, loader, component })`. No markup beyond rendering a container.
- **Container/presentational.** Components never call `useQuery`, `useNavigate` or read context other than theme. Containers do. This keeps components reusable and testable.
- **Barrels.** Cross-module imports use `~/modules/<name>` only. ESLint blocks deeper paths.
- **Dependency direction.** `routes -> modules -> design-system/components/ui -> lib`. Modules may use `catalog` and `auth`; avoid module-to-module cycles. Shared needs go to `lib` or `design-system`.
- **Data.** Server data via TanStack Query hooks calling `api()` from `~/lib/api`. Do not store server data in `useState`. Static public content may use route loaders for SSR.
- **State in the URL** when it should survive refresh or be shareable: filters, tabs, selected course/level (use route params or search params validated with zod).
- **Env.** Add every `VITE_*` var to `src/lib/env.ts` (zod) and `.env.example`. Never read `import.meta.env` elsewhere.
- **Client-only code** (`window`, supabase, posthog) runs in effects or behind `typeof window` checks so SSR stays safe.
- **Errors.** Route-level `errorComponent` reports to Sentry. Use `notFound()` in loaders for unknown slugs.
- **File naming.** Components `PascalCase.tsx`, hooks `useThing.ts`, everything else `kebab-case.ts`.
