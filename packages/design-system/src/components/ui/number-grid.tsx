import { Check, Flag, X } from '../../icons'
import { cn } from '../../lib/utils'

export type QuestionGridState =
  'unseen' | 'seen' | 'answered' | 'marked' | 'answered_marked' | 'correct' | 'incorrect' | 'skipped' | 'removed'

export interface NumberGridItem {
  id: string | number
  number: number | string
  state: QuestionGridState
  label?: string
  disabled?: boolean
}

export interface NumberGridProps {
  items: NumberGridItem[]
  currentIndex?: number
  onSelect?: (index: number) => void
  columns?: number
  className?: string
  'aria-label'?: string
}

const stateLabels: Record<QuestionGridState, string> = {
  unseen: 'Unseen',
  seen: 'Not answered',
  answered: 'Answered',
  marked: 'Marked for review',
  answered_marked: 'Answered and marked for review',
  correct: 'Correct',
  incorrect: 'Incorrect',
  skipped: 'Skipped',
  removed: 'Removed',
}

export function NumberGrid({
  items,
  currentIndex,
  onSelect,
  columns = 5,
  className,
  'aria-label': ariaLabel = 'Question palette',
}: NumberGridProps) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn('grid gap-1.5', className)}
      style={{
        gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
      }}
    >
      {items.map((item, index) => {
        const isCurrent = currentIndex === index
        const stateDesc = stateLabels[item.state] || item.state
        const fullAriaLabel = `Question ${item.number}: ${stateDesc}${isCurrent ? ' (Current question)' : ''}`

        return (
          <button
            key={item.id}
            type="button"
            disabled={item.disabled || item.state === 'removed'}
            onClick={() => onSelect?.(index)}
            aria-label={fullAriaLabel}
            aria-current={isCurrent ? 'true' : undefined}
            className={cn(
              'relative flex h-8 w-full min-w-8 items-center justify-center rounded-md border text-xs font-medium transition-colors outline-none pointer-coarse:h-10 pointer-coarse:min-w-10',
              // Base states
              item.state === 'unseen' && 'border-border/60 bg-muted/30 text-muted-foreground hover:bg-muted/60',
              item.state === 'seen' && 'border-border bg-card text-foreground hover:border-primary/50',
              item.state === 'answered' && 'border-primary bg-primary text-primary-foreground hover:opacity-90',
              item.state === 'marked' && 'border-warning-border bg-warning-bg text-warning-fg hover:brightness-95',
              item.state === 'answered_marked' && 'border-primary bg-primary text-primary-foreground hover:opacity-90',
              item.state === 'correct' && 'border-success-border bg-success-bg text-success-fg hover:brightness-95',
              item.state === 'incorrect' &&
                'text-destructive-foreground border-destructive bg-destructive hover:opacity-90',
              item.state === 'skipped' && 'border-dashed border-muted-foreground/40 bg-muted/20 text-muted-foreground',
              item.state === 'removed' && 'cursor-not-allowed border-dashed line-through opacity-40',
              // Current item highlight
              isCurrent && 'font-semibold shadow-soft ring-2 ring-ring ring-offset-1 ring-offset-background',
            )}
          >
            <span>{item.number}</span>
            {/* Corner status icons so state is never colour only */}
            {(item.state === 'marked' || item.state === 'answered_marked') && (
              <span className="absolute -top-1 -right-1 flex size-3.5 items-center justify-center rounded-full bg-warning text-[8px] text-background shadow-xs">
                <Flag aria-hidden className="size-2 fill-background stroke-background" />
              </span>
            )}
            {item.state === 'correct' && (
              <span className="absolute -top-1 -right-1 flex size-3.5 items-center justify-center rounded-full bg-card text-success-fg shadow-xs">
                <Check aria-hidden className="size-2.5 stroke-[3]" />
              </span>
            )}
            {item.state === 'incorrect' && (
              <span className="absolute -top-1 -right-1 flex size-3.5 items-center justify-center rounded-full bg-card text-destructive shadow-xs">
                <X aria-hidden className="size-2.5 stroke-[3]" />
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
