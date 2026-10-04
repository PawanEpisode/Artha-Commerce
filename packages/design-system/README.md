# @artha/design-system

Tokens, primitives, layout and motion for ArthaCommerce. Source-only TypeScript package, consumed by `apps/web`.

```ts
import { Button, Card, Section, Reveal, cn } from '@artha/design-system'
```

Consumer CSS (`apps/web/src/styles.css`):

```css
@import 'tailwindcss';
@import '@artha/design-system/styles.css';
@source '../../../packages/design-system/src';
```

Rules and how to add a primitive: `.claude/skills/design-system-usage/SKILL.md`. Live guide: run the web app and open `/design-system`.
