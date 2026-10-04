import { Check, CircleAlert, Info } from '../../icons'
import { cn } from '../../lib/utils'

export type Confidence = 'red' | 'amber' | 'green'

const META: Record<Confidence, { label: string; cls: string; Icon: typeof Check }> = {
  red: { label: 'Needs work', cls: 'bg-destructive text-primary-foreground', Icon: CircleAlert },
  amber: { label: 'Getting there', cls: 'bg-highlight text-highlight-foreground', Icon: Info },
  green: { label: 'Confident', cls: 'bg-accent text-accent-foreground', Icon: Check },
}

export const confidenceLabel = (c: Confidence) => META[c].label

/** Red/amber/green marker that also carries an icon and (optionally) a text label, so it is never colour only. */
export function ConfidenceDot({
  value,
  showLabel = false,
  className,
}: {
  value: Confidence
  showLabel?: boolean
  className?: string
}) {
  const { label, cls, Icon } = META[value]
  return (
    <span
      data-slot="confidence-dot"
      className={cn('inline-flex items-center gap-1.5 text-xs font-semibold', className)}
    >
      <span aria-hidden className={cn('grid size-5 place-items-center rounded-full', cls)}>
        <Icon className="size-3" strokeWidth={3} />
      </span>
      {showLabel ? <span>{label}</span> : <span className="sr-only">{label}</span>}
    </span>
  )
}
