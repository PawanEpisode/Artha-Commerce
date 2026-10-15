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
      className={cn('grid gap-2', className)}
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
              'relative flex h-10 w-full min-w-10 items-center justify-center rounded-lg border text-xs font-semibold transition-all outline-none',
              // Base states
              item.state === 'unseen' && 'border-border/60 bg-muted/30 text-muted-foreground hover:bg-muted/60',
              item.state === 'seen' && 'border-border bg-card text-foreground hover:border-primary/50',
              item.state === 'answered' && 'border-primary bg-primary text-primary-foreground hover:opacity-90',
              item.state === 'marked' &&
                'border-amber-500 bg-amber-500/15 text-amber-900 hover:bg-amber-500/25 dark:text-amber-200',
              item.state === 'answered_marked' && 'border-primary bg-primary text-primary-foreground hover:opacity-90',
              item.state === 'correct' && 'border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700',
              item.state === 'incorrect' &&
                'text-destructive-foreground border-destructive bg-destructive hover:opacity-90',
              item.state === 'skipped' && 'border-dashed border-muted-foreground/40 bg-muted/20 text-muted-foreground',
              item.state === 'removed' && 'cursor-not-allowed border-dashed line-through opacity-40',
              // Current item highlight
              isCurrent && 'font-bold shadow-sm ring-2 ring-ring ring-offset-2 ring-offset-background',
            )}
          >
            <span>{item.number}</span>
            {/* Corner status icons so state is never colour only */}
            {(item.state === 'marked' || item.state === 'answered_marked') && (
              <span className="absolute -top-1 -right-1 flex size-3.5 items-center justify-center rounded-full bg-amber-500 text-[8px] text-white shadow-xs">
                <Flag aria-hidden className="size-2 fill-white stroke-white" />
              </span>
            )}
            {item.state === 'correct' && (
              <span className="absolute -top-1 -right-1 flex size-3.5 items-center justify-center rounded-full bg-white text-emerald-700 shadow-xs">
                <Check aria-hidden className="size-2.5 stroke-[3]" />
              </span>
            )}
            {item.state === 'incorrect' && (
              <span className="absolute -top-1 -right-1 flex size-3.5 items-center justify-center rounded-full bg-white text-destructive shadow-xs">
                <X aria-hidden className="size-2.5 stroke-[3]" />
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
