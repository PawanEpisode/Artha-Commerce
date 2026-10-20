import { Badge } from '@artha/design-system'

import type { ChangeType } from '../lib/types'

interface Props {
  type: ChangeType
  className?: string
}

const typeConfigs: Record<
  ChangeType,
  { label: string; variant: 'default' | 'accent' | 'outline' | 'highlight'; className: string }
> = {
  addition: {
    label: 'Addition',
    variant: 'accent',
    className: 'bg-emerald-500/10 text-emerald-600 border-emerald-300 dark:text-emerald-400',
  },
  deletion: {
    label: 'Omission / Deletion',
    variant: 'outline',
    className: 'border-destructive/30 text-destructive dark:text-destructive',
  },
  modification: {
    label: 'Substitution',
    variant: 'highlight',
    className: '',
  },
  new_standard: {
    label: 'New Standard',
    variant: 'default',
    className: 'border-primary/20 bg-primary/10 text-primary',
  },
  clarification: {
    label: 'Clarification',
    variant: 'outline',
    className: 'text-muted-foreground border-border',
  },
}

export function ChangeTypeBadge({ type, className }: Props) {
  const config = typeConfigs[type] ?? {
    label: type,
    variant: 'outline' as const,
    className: '',
  }

  return (
    <Badge variant={config.variant} className={`${config.className} ${className ?? ''}`}>
      {config.label}
    </Badge>
  )
}
