import { cn } from '@artha/design-system'

interface Props {
  /** Rounds before the long break. */
  total: number
  /** The round now running or due next (1-based). */
  current: number
  /** True while a focus round is the thing running. */
  active: boolean
}

/** One dot per round in the cycle: finished, current, still to come. The words carry the meaning, not the colour. */
export function CycleDots({ total, current, active }: Props) {
  return (
    <div className="flex flex-col items-center gap-2">
      <ol className="flex items-center gap-2" aria-label="Rounds in this cycle">
        {Array.from({ length: total }, (_, i) => {
          const n = i + 1
          const state = n < current ? 'done' : n === current ? (active ? 'now' : 'next') : 'later'
          return (
            <li
              key={n}
              aria-label={`Round ${n}: ${state === 'done' ? 'finished' : state === 'now' ? 'in progress' : state === 'next' ? 'up next' : 'later'}`}
              className={cn(
                'size-3.5 rounded-full border-2 border-primary',
                state === 'done' && 'bg-primary',
                state === 'now' && 'bg-primary ring-4 ring-primary/25',
                state === 'next' && 'bg-card ring-4 ring-primary/25',
                state === 'later' && 'border-input bg-card',
              )}
            />
          )
        })}
      </ol>
      <p className="max-w-xs text-center text-sm text-muted-foreground">
        Round {Math.min(current, total)} of {total}. A longer break starts after round {total}.
      </p>
    </div>
  )
}
