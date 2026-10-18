import type { ReasonPayload } from '../types'

export interface ReasonListProps {
  reasons: ReasonPayload[]
  className?: string
  maxItems?: number
}

export function ReasonList({ reasons, className, maxItems = 3 }: ReasonListProps) {
  if (!reasons || reasons.length === 0) return null

  const displayReasons = reasons.slice(0, maxItems)

  return (
    <ul className={`space-y-1 text-xs text-muted-foreground ${className || ''}`}>
      {displayReasons.map((r, idx) => (
        <li key={`${r.code}-${idx}`} className="flex items-start gap-1.5">
          <span className="mt-1 leading-none font-bold text-primary/70 select-none">•</span>
          <span className="leading-snug">{r.sentence}</span>
        </li>
      ))}
    </ul>
  )
}
