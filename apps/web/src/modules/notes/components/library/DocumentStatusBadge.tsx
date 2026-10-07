import {
  Badge,
  CircleCheck,
  CircleX,
  Clock,
  CloudOff,
  Hourglass,
  LoaderCircle,
  Lock,
  ScanText,
  TriangleAlert,
} from '@artha/design-system'

import type { BadgeKind, BadgeTone, DocBadge } from '../../lib/document-badges'

const TONE: Record<BadgeTone, string> = {
  success: 'border-success-border bg-success-bg text-success-fg',
  info: 'border-info-border bg-info-bg text-info-fg',
  warning: 'border-warning-border bg-warning-bg text-warning-fg',
  error: 'border-error-border bg-error-bg text-error-fg',
  neutral: 'border-border bg-card text-muted-foreground',
}

const ICON: Record<BadgeKind, typeof Lock> = {
  ready: CircleCheck,
  preparing: LoaderCircle,
  waiting: Hourglass,
  scanned: ScanText,
  ocr: LoaderCircle,
  searchable: CircleCheck,
  ocr_failed: TriangleAlert,
  locked: Lock,
  rejected: CircleX,
  failed: TriangleAlert,
  expired: Clock,
  offline: CloudOff,
}

/** One status of a document: an icon and words, so the meaning never rests on colour (WCAG 1.4.1). */
export function DocumentStatusBadge({ badge }: { badge: DocBadge }) {
  const Icon = ICON[badge.kind]
  const spins = badge.kind === 'preparing' || badge.kind === 'ocr'
  return (
    <Badge variant="outline" className={TONE[badge.tone]} title={badge.detail} data-kind={badge.kind}>
      <Icon aria-hidden className={spins ? 'animate-spin motion-reduce:animate-none' : undefined} />
      {badge.label}
    </Badge>
  )
}
