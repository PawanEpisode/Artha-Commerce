import { buttonVariants, Flame, ProgressRing } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { TodayAction } from '../lib/today'

interface Props {
  percent: number
  /** "1 h 10 m of 2 h" */
  doneLabel: string
  streak: number
  action: TodayAction
  canLogTime: boolean
}

/** Goal ring, streak, and the one primary action. Text carries every number the ring shows. */
export function TodayView({ percent, doneLabel, streak, action, canLogTime }: Props) {
  return (
    <>
      <div className="flex items-center gap-5">
        <ProgressRing value={percent} label="Today's goal" size={96}>
          <span className="text-lg font-bold">{percent}%</span>
        </ProgressRing>
        <div className="min-w-0 space-y-1">
          <p className="font-semibold">{doneLabel}</p>
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Flame className="size-4 text-primary" aria-hidden />
            {streak === 1 ? '1 day streak' : `${streak} day streak`}
          </p>
        </div>
      </div>
      <div className="mt-auto flex flex-wrap gap-2">
        {action.kind !== 'none' ? (
          <Link to={action.to} className={buttonVariants({ variant: 'cta', size: 'default' })}>
            {action.label}
          </Link>
        ) : null}
        {canLogTime ? (
          <Link to="/app/tracker/log" className={buttonVariants({ variant: 'outline' })}>
            Log time
          </Link>
        ) : null}
      </div>
    </>
  )
}
