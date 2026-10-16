import { Check } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { formatDay } from '../lib/time'
import type { WeekDay } from '../lib/types'

const OUTCOME_TEXT: Record<string, string> = {
  all: 'all done',
  some: 'some done',
  none: 'nothing done',
  no_plan: 'no plan',
}

const weekdayLetter = (day: string) => {
  const [y, m, d] = day.split('-').map(Number)
  return new Intl.DateTimeFormat('en-GB', { weekday: 'short', timeZone: 'UTC' })
    .format(new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1)))
    .slice(0, 2)
}

/** The last seven days as dots: all done, some, none, no plan. Each links to that day; today is outlined. Text carries the meaning. */
export function WeekStrip({ days, today }: { days: WeekDay[]; today: string }) {
  if (!days.length) return null
  return (
    <nav aria-label="This week" className="rounded-lg border border-border bg-card p-2">
      <ul className="flex items-center justify-between gap-1">
        {days.map((d) => {
          const isToday = d.date === today
          const text = OUTCOME_TEXT[d.outcome] ?? d.outcome
          return (
            <li key={d.date}>
              <Link
                to={(isToday ? '/app/today' : '/app/today/$date') as never}
                params={isToday ? undefined : ({ date: d.date } as never)}
                aria-label={`${formatDay(d.date)}: ${text}${d.planned_count ? `, ${d.done_count} of ${d.planned_count}` : ''}${isToday ? ', today' : ''}`}
                aria-current={isToday ? 'date' : undefined}
                className="flex min-h-11 min-w-9 flex-col items-center justify-center gap-1 rounded-lg px-1 text-xs text-muted-foreground outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40"
              >
                <span>{weekdayLetter(d.date)}</span>
                <span
                  aria-hidden
                  className={`grid size-5 place-items-center rounded-full border-2 ${
                    d.outcome === 'all'
                      ? 'border-primary bg-primary text-primary-foreground'
                      : d.outcome === 'some'
                        ? 'border-primary bg-secondary'
                        : d.outcome === 'none'
                          ? 'border-dashed border-input'
                          : 'border-transparent bg-muted'
                  } ${isToday ? 'ring-2 ring-foreground/60 ring-offset-2 ring-offset-card' : ''}`}
                >
                  {d.outcome === 'all' ? <Check className="size-3" strokeWidth={3} /> : null}
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
