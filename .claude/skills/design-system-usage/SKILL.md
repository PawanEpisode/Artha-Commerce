---
name: design-system-usage
description: Use for any UI work in apps/web. How to use tokens, shadcn primitives, layout and motion; how to add or change design-system pieces.
---

# Design system usage

The design system is the product's visual contract. Pages are assembled, not hand-styled.

## Source of truth

- Tokens: `src/design-system/styles.css` (`:root` and `.dark`, mapped in `@theme inline`). Colours are OKLCH.
- Primitives: `src/components/ui/*` (shadcn style: Button, Card, Badge, Input, Tabs, Accordion, Separator).
- Layout: `Container`, `Section` in `~/design-system`. Use `Section` for every page block so spacing and headings stay consistent.
- Motion: `Reveal`, `fadeUp`, `stagger`, `ease` in `~/design-system/motion`. Always respect reduced motion (built in to `Reveal`).
- Icons: `lucide-react` only. Feature icons go through `components/feature-icon.tsx`.

## Rules

1. Use semantic colour classes only: `bg-background`, `bg-card`, `bg-primary`, `text-muted-foreground`, `border-border`, `bg-accent`, `bg-highlight`. Never `#hex`, `rgb()`, or `bg-indigo-500`.
2. Change the look globally by editing tokens, not components.
3. Need a new primitive? Add it to `components/ui` following the shadcn pattern (`cva` variants, `cn()`, `data-slot`). If the shadcn CLI is reachable: `pnpm dlx shadcn@latest add <name>` (config in `components.json`), then reconcile with our tokens.
4. Variants over one-offs. Add a `variant` or `size` to the primitive instead of passing a long `className` in several places. Three similar uses means extract.
5. Display type uses `font-display` (applied to headings automatically). Body uses `font-sans`.
6. Radius comes from `rounded-lg/xl/2xl` (token driven). Shadows: `shadow-soft`, `shadow-lift`.
7. Dark mode is automatic through tokens. Check both themes for every screen.
8. Accessibility: visible focus ring (`focus-visible:ring-*`), 44px touch targets on mobile, labelled controls, `aria-live` for results that change.
9. Animate meaning, not decoration: entrances, progress, state change. Keep durations 150-600ms.

## Checklist before merging UI

- [ ] No raw colours or arbitrary pixel values where a token exists
- [ ] Looks right at 390px, 768px, 1280px, light and dark
- [ ] Keyboard path works, focus visible
- [ ] Reused an existing primitive or added a variant
