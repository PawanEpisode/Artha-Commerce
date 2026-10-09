import { Badge } from '@artha/design-system'

import type { ForgottenCard } from '../lib/schemas'
import { kindLabel } from './CardFace'
import { InlineText } from './InlineText'

/** One card the student keeps missing: the question, how often, and how recently. */
export function ForgottenRow({ item }: { item: ForgottenCard }) {
  return (
    <li className="space-y-2 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{kindLabel(item.kind)}</Badge>
        {item.subject_key ? <span className="text-xs text-muted-foreground">{item.subject_key}</span> : null}
      </div>
      <div className="space-y-1 text-sm">
        <InlineText text={item.front_md} />
      </div>
      <p className="text-xs text-muted-foreground">
        Missed {item.agains === 1 ? 'once' : `${item.agains} times`} recently
        {item.lapses > 0 ? `, forgotten ${item.lapses === 1 ? 'once' : `${item.lapses} times`} after you knew it` : ''}.
      </p>
    </li>
  )
}
