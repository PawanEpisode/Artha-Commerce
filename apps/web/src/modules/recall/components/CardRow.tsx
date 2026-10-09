import { Badge, Checkbox } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { plain } from '../lib/inline'
import type { RecallCardRow } from '../lib/schemas'
import { kindLabel } from './CardFace'

const BADGE_TEXT: Record<string, string> = {
  suspended: 'Paused',
  tricky: 'Tricky',
  recheck: 'Needs a look',
  buried: 'Back tomorrow',
}

/** One card in the browser: tick box, a short look at the front, and a link to open it. */
export function CardRow({
  card,
  selected,
  onSelect,
}: {
  card: RecallCardRow
  selected: boolean
  onSelect: (id: string, on: boolean) => void
}) {
  const text = plain(card.front_md).slice(0, 140) || 'Untitled card'
  return (
    <li className="flex items-start gap-3 rounded-xl border border-border bg-card p-3 sm:p-4">
      <Checkbox
        checked={selected}
        onCheckedChange={(v) => onSelect(card.id, v === true)}
        aria-label={`Select: ${text}`}
        className="mt-1"
      />
      <div className="min-w-0 flex-1 space-y-2">
        <Link
          to="/app/recall/cards/$cardId"
          params={{ cardId: card.id }}
          className="block text-base font-medium break-words text-foreground underline-offset-4 hover:underline focus-visible:underline"
        >
          {text}
        </Link>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">{kindLabel(card.kind)}</Badge>
          {card.chapter?.name ? <span>{card.chapter.name}</span> : null}
          {card.badges.map((b) => (
            <Badge key={b} variant="outline">
              {BADGE_TEXT[b] ?? b}
            </Badge>
          ))}
        </div>
      </div>
    </li>
  )
}
