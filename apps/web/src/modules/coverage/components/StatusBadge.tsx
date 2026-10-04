import { Badge, Check, CircleCheck, Clock, Sparkles } from '@artha/design-system'

import type { ChapterStatus } from '../lib/types'

const META: Record<
  ChapterStatus,
  { label: string; variant: 'default' | 'outline' | 'accent' | 'highlight'; icon?: typeof Check }
> = {
  not_started: { label: 'Not started', variant: 'outline' },
  reading: { label: 'Reading', variant: 'default' },
  practised: { label: 'Practised', variant: 'default', icon: Check },
  revised_once: { label: 'Revised once', variant: 'highlight', icon: Clock },
  revised_twice_plus: { label: 'Revised twice or more', variant: 'accent', icon: CircleCheck },
  exam_ready: { label: 'Exam ready', variant: 'accent', icon: Sparkles },
}

export const statusLabel = (s: ChapterStatus) => META[s].label

/** Status as text plus an icon where it adds meaning: never colour only. */
export function StatusBadge({ status }: { status: ChapterStatus }) {
  const { label, variant, icon: Icon } = META[status]
  return (
    <Badge variant={variant}>
      {Icon ? <Icon aria-hidden /> : null}
      {label}
    </Badge>
  )
}
