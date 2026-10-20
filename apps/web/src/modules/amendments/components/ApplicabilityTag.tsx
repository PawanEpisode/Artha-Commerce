import { Badge, Tooltip } from '@artha/design-system'

import type { Applicability, ApplicabilityStatus } from '../lib/types'

interface Props {
  applicability: Applicability
  targetTerm?: string | null
  className?: string
}

const statusConfig: Record<
  ApplicabilityStatus,
  { label: string; variant: 'default' | 'accent' | 'outline' | 'highlight'; className: string }
> = {
  applies: {
    label: 'Applies to your attempt',
    variant: 'accent',
    className: 'bg-emerald-500/10 text-emerald-600 border-emerald-300 dark:text-emerald-400',
  },
  not_applicable: {
    label: 'Not applicable to your attempt',
    variant: 'outline',
    className: 'text-muted-foreground border-border',
  },
  unknown: {
    label: 'Applicability unknown',
    variant: 'outline',
    className: 'text-amber-600 border-amber-300 dark:text-amber-400',
  },
}

export function ApplicabilityTag({ applicability, targetTerm, className }: Props) {
  const config = statusConfig[applicability.state] ?? statusConfig.unknown
  const label = targetTerm && applicability.state === 'applies' ? `Applies to ${targetTerm}` : config.label
  const tooltipText = applicability.reason || label

  return (
    <Tooltip content={tooltipText}>
      <Badge variant={config.variant} className={`${config.className} ${className ?? ''}`}>
        {label}
      </Badge>
    </Tooltip>
  )
}
