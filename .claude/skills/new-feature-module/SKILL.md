---
name: new-feature-module
description: Use for any new feature, issue or change request in ArthaCommerce. Defines the module-first workflow, layering and definition of done.
---

# New feature or issue workflow

1. **Clarify the slice.** Write one sentence: who benefits, what changes, which URL it lives at. Split anything bigger than one PR.
2. **Find reuse first.** Search `src/modules`, `src/components/ui`, `src/design-system`, `modules/` (api). Extend before creating.
3. **Name the module.** One noun, kebab-case (`syllabus-tracker`). Create `src/modules/<name>/` and, if it needs data, `apps/api/modules/<name>/`.
4. **Build API first when data is involved** (see `django-backend-layers`): model -> migration -> selector/service -> serializer -> view -> url -> tests.
5. **Build the web module** (see `frontend-architecture`):
   - `lib/` pure logic (unit-testable), `api.ts` typed calls, `hooks/` TanStack Query hooks
   - `containers/` wire hooks to components, `components/` presentational only
   - `index.ts` exports the public surface only
6. **Add the route** in `src/routes`. The route file only sets `head` (SEO), loader and renders one container.
7. **Add UI from the design system** (see `design-system-usage`). Add loading, empty, error and success states for every data view.
8. **SEO and sharing** if public (see `seo-and-sharing`). Add to `modules/seo/sitemap.ts` if it is not catalog-driven.
9. **Analytics.** Capture one PostHog event for the key action, named `noun_verb` (`plan_created`). Do not send PII.
10. **Verify.** `pnpm typecheck && pnpm lint && pnpm build:web` and `pytest && ruff check .`. Open the page at mobile and desktop widths.

## Definition of done

- [ ] Lives in one module with a barrel export; no deep imports
- [ ] No business logic in routes, views or JSX
- [ ] No duplicated component, constant or query
- [ ] Only design tokens and `components/ui` used
- [ ] Loading, empty, error states handled; keyboard and screen-reader usable
- [ ] Tests for logic and endpoints; checks green
- [ ] Docs or skill updated if a convention changed
