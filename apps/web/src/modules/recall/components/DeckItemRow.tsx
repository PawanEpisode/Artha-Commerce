import { Badge, Button, Flag } from '@artha/design-system'

import { tierLabel } from '../lib/decks'
import type { ApiDeckItem } from '../lib/schemas'
import { kindLabel } from './CardFace'

/** One item of a deck as a preview line (the full card shows in revision), with a way to report it. */
export function DeckItemRow({ item, onReport }: { item: ApiDeckItem; onReport: (item: ApiDeckItem) => void }) {
  return (
    <li className="flex items-start justify-between gap-3 rounded-xl border border-border bg-card p-3 sm:p-4">
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{kindLabel(item.kind)}</Badge>
          <Badge variant={item.importance === 'mandatory' ? 'highlight' : 'default'}>
            {tierLabel(item.importance)}
          </Badge>
        </div>
        <p className="text-sm break-words">{item.preview}</p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        aria-label={`Report this card: ${item.preview}`}
        onClick={() => onReport(item)}
        className="shrink-0"
      >
        <Flag aria-hidden />
        Report
      </Button>
    </li>
  )
}
