---
name: design-system-usage
description: Use for any UI work. How to use and extend the @artha/design-system package (tokens, primitives, layout, motion), and the rules for building screens from it.
---

# Design system usage

The design system is a workspace package: `packages/design-system`, imported as `@artha/design-system`. Screens are assembled from it, never hand-styled.

## What is inside

```
packages/design-system/src/
  styles.css            tokens for 3 palettes (reading default, light, dark), @theme mapping, prose-reading. OKLCH colours
  components/ui/*.tsx   shadcn-style primitives: Button, Card, Badge, Input, TextField, PasswordField, Label, RadioGroup, DropdownMenu, Alert, Tabs, Accordion, Separator
  layout.tsx            Container, Section
  motion.tsx            Reveal, fadeUp, stagger, ease
  Logo.tsx              LogoMark, Logo
  icons.ts              curated Lucide icons (the only icon source)
  theme/                ThemeProvider, useTheme, ThemeSwitcher, buildThemeInitScript
  lib/utils.ts          cn()
  index.ts              the public barrel
```

The app wires it in `apps/web/src/styles.css`:

```css
@import 'tailwindcss';
@import '@artha/design-system/styles.css';
@source '../../../packages/design-system/src';
```

See it live at `/design-system` (run `pnpm dev:web`). Every primitive and variant must appear there.

## Rules

1. Import from `'@artha/design-system'` only. Never from `@artha/design-system/src/...` or a local `components/ui` path (ESLint blocks both).
2. Semantic colour classes only: `bg-background`, `bg-card`, `bg-primary`, `text-muted-foreground`, `border-border`, `bg-accent`, `bg-highlight`. No `#hex`, `rgb()`, or `bg-indigo-500`.
3. Change the look globally by editing tokens in `styles.css`, never component by component.
4. **Adding a primitive**: create `src/components/ui/<name>.tsx` (cva variants, `cn()`, `data-slot`), use **relative imports inside the package** (no `~` alias: the web app also uses `~`), export it from `src/index.ts`, add it to `DesignShowcase`, then use it in the app. Components copied from shadcn need their imports rewritten to relative paths.
5. Variants over one-offs: if a long `className` repeats in three places, add a variant or a new primitive.
6. App-specific components (they know about courses, features, routes) stay in `apps/web/src/modules`, not in the package. The package has no knowledge of the product domain.
7. Display type is `font-display` (headings get it automatically), body is `font-sans`. Radius via `rounded-lg/xl/2xl`. Shadows `shadow-soft`, `shadow-lift`.
8. Themes come from tokens via `data-theme` on `<html>`: `reading` (default), `light`, `dark`, and `system` (light 06:00 to 18:00, dark otherwise). Check all four on every screen and run `pnpm check:contrast`.
9. Icons: Lucide, imported only from `@artha/design-system`. Add new ones to `src/icons.ts`. Direct `lucide-react` imports are blocked by ESLint.
10. Accessibility: visible `focus-visible` ring, 44px touch targets on mobile, labelled controls, `aria-live` for changing results.
11. Motion explains change (entrances, progress, state). 150 to 600 ms. `Reveal` already honours reduced motion.

## Checklist before merging UI

- [ ] Only design-system imports and tokens used
- [ ] New or changed primitive appears in `/design-system` showcase
- [ ] Looks right in Reading, Light, Dark and System at 320, 390, 768 and 1280 px, no horizontal scroll
- [ ] Completed `.claude/skills/ui-quality-checklist`
- [ ] Keyboard path works, focus visible
