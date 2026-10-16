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
  components/ui/*.tsx   shadcn-style primitives: Button, Card, Badge, Input, TextField, PasswordField, Label, RadioGroup, DropdownMenu, Alert, Tabs, Accordion, Separator,
                        plus: Button (variants default/cta/accent/secondary/outline/ghost/danger/link, sizes xs 24 / sm 28 / default 32 / icon 32 / icon-sm 28 with a mouse and 36 to 44 px under `pointer-coarse:`; `lg` 40 and `xl` 48 are for public pages only; `loading`, `arrow`, `fullWidth`), ButtonLink
                        (anchor or `asChild` router Link styled as a Button), SectionTabs (sticky scrollable sub-nav, `nav` or `tablist`; set
                        `--site-header-height` for the sticky offset), DurationField (hours + minutes <-> whole minutes), EntityBadge/LabelBadge/EntityRow/
                        EntityDot (chapter green, topic amber, paper pink), ReadToggle, Toaster + `toast.success/error/warning/info/custom/promise/dismiss`
                        + `toastApiError(error, fallback)` (mount `<Toaster />` once in the app root)
  lib/duration.ts       splitMinutes, joinMinutes, formatDuration (short/long), clampMinutes: use for every typed duration
  layout.tsx            Container, Section (public pages), Page, PageHeader (app pages), useAppFrame
  components/ui/        also: Sidebar* (app rail), CommandPalette (Cmd/Ctrl+K), DataTable + TableHeader/Body/Row/Head/Cell/Toolbar, SectionTabs (compact), StatTile, FilterChip, EmptyState (compact)
  motion.tsx            Reveal, fadeUp, stagger, ease
  Logo.tsx              LogoMark, Logo
  icons.ts              curated Lucide icons (the only icon source); StudyTimeIcon = tracker clock, Flame = streaks
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
2. Semantic colour classes only: `bg-background`, `bg-card`, `bg-primary`, `text-muted-foreground`, `border-border`, `bg-accent`, `bg-highlight`, status `bg-success-bg text-success-fg border-success-border` (also warning, info, error) and entity `tag-chapter|topic|paper` (-bg/-fg/-border, accent for rails). No `#hex`, `rgb()`, or `bg-indigo-500`.
3. Change the look globally by editing tokens in `styles.css`, never component by component.
4. **Adding a primitive**: create `src/components/ui/<name>.tsx` (cva variants, `cn()`, `data-slot`), use **relative imports inside the package** (no `~` alias: the web app also uses `~`), export it from `src/index.ts`, add it to `DesignShowcase`, then use it in the app. Components copied from shadcn need their imports rewritten to relative paths.
5. Variants over one-offs: if a long `className` repeats in three places, add a variant or a new primitive.
6. App-specific components (they know about courses, features, routes) stay in `apps/web/src/modules`, not in the package. The package has no knowledge of the product domain.
7. Type is Inter only (`font-sans`; `font-display` is now the same family). App body is 13px (`[data-app-frame]`), public pages 16px. Radius: `rounded-md` controls, `rounded-lg` cards and menus, `rounded-xl` dialogs; no `rounded-2xl/3xl`. Shadows: `shadow-soft` is a 1px hairline, `shadow-lift` only for floating layers (menus, toasts, popovers). Headings are `font-semibold`, never bold or extrabold.
8. Themes come from tokens via `data-theme` on `<html>`: `reading` (default), `light`, `dark`, and `system` (light 06:00 to 18:00, dark otherwise). Check all four on every screen and run `pnpm check:contrast`.
9. Icons: Lucide, imported only from `@artha/design-system`. Add new ones to `src/icons.ts`. Direct `lucide-react` imports are blocked by ESLint.
10. Accessibility: visible `focus-visible:ring-2 ring-ring/50`, labelled controls, `aria-live` for changing results. Targets are compact with a mouse (controls 28 to 32px) and 44px under `pointer-coarse:` (Button, Input, Select, Checkbox hit areas and so on already do this; copy the pattern, never hard-code 44px for everyone). Inputs use 16px text on touch so iOS does not zoom.
11. Motion explains change (entrances, progress, state). 150 to 600 ms. `Reveal` already honours reduced motion.

## Page recipes (app screens)

Full contract: `docs/UI-REDESIGN.md`. In short:

```tsx
<Page>                                   {/* or <Page width="form"> for settings */}
  <PageHeader title="Questions" description="..." actions={<Button>New</Button>} />
  <TableToolbar>
    <Input aria-label="Search" placeholder="Search" />
    <SelectField aria-label="Paper" ... />
    {active && <FilterChip removeLabel="Remove filter X" onRemove={clear}>X</FilterChip>}
  </TableToolbar>
  <DataTable>
    <TableHeader><TableRow><TableHead>Title</TableHead><TableHead className="text-right">Marks</TableHead></TableRow></TableHeader>
    <TableBody>{rows.map(r => <TableRow key={r.id}><TableCell>...</TableCell><TableCell className="text-right tabular-nums">...</TableCell></TableRow>)}</TableBody>
  </DataTable>
</Page>
```

- A list of like things is a `DataTable` (36px rows, first cell the link, status as `Badge`), not a stack of cards. Hide minor columns with `hidden md:table-cell`.
- One `PageHeader` per page, one primary default-size `Button` in it. Row and toolbar actions are `size="sm"` or `icon-sm` ghost. No `lg`/`xl` buttons in the app.
- Empty state: `EmptyState` (compact). Loading: skeleton rows. Dashboard: `grid gap-3` of `Card`s with a `StatTile` row.
- Public pages keep `Section`/`Container` (centred, editorial): hero h1 `text-4xl sm:text-5xl`, section h2 `text-2xl sm:text-3xl`, section padding `py-12 sm:py-20`.

## Checklist before merging UI

- [ ] Only design-system imports and tokens used
- [ ] New or changed primitive appears in `/design-system` showcase
- [ ] Looks right in Reading, Light, Dark and System at 320, 390, 768 and 1280 px, no horizontal scroll
- [ ] Completed `.claude/skills/ui-quality-checklist`
- [ ] Keyboard path works, focus visible
