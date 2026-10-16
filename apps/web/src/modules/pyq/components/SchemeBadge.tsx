import { Badge } from '@artha/design-system'

import { SCHEME_BADGES } from '../lib/labels'
import type { SchemeRelation } from '../lib/types'

/** How a past-paper question relates to the current syllabus. Text label, tinted by token. */
export function SchemeBadge({ relation, short = false }: { relation: SchemeRelation; short?: boolean }) {
  const badge = SCHEME_BADGES[relation] ?? SCHEME_BADGES.current
  return (
    <Badge variant="outline" className={badge.className}>
      {short && relation === 'changed' ? 'Changed' : badge.label}
    </Badge>
  )
}
