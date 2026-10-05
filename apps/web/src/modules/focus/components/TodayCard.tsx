import { Card, CardContent, Flame, ProgressRing } from '@artha/design-system'

import { formatDuration } from '~/modules/tracker'

interface Props {
  doneSeconds: number
  targetMinutes: number
  percent: number
  streak: number
  /** Pomodoro rounds finished today. */
  rounds: number
}

/** Today at a glance: the shared daily goal (all study time counts), the streak and rounds finished. */
export function TodayCard({ doneSeconds, targetMinutes, percent, streak, rounds }: Props) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-6 p-6">
        <ProgressRing value={percent} size={96} strokeWidth={9} label="Daily goal">
          <span className="text-lg font-bold">{Math.round(percent)}%</span>
        </ProgressRing>
        <div className="min-w-0 flex-1 space-y-1">
          <h2 className="text-lg font-bold">Today</h2>
          <p className="text-sm text-muted-foreground">
            {formatDuration(doneSeconds)} of {formatDuration(targetMinutes * 60)}. Stopwatch, manual and Pomodoro time
            all count.
          </p>
          <p className="text-sm text-muted-foreground">
            {rounds === 1 ? '1 round' : `${rounds} rounds`} finished today
          </p>
        </div>
        <p className="flex items-center gap-1.5 text-sm font-semibold" aria-label={`Streak: ${streak} days`}>
          <Flame className="size-5 text-primary" aria-hidden />
          {streak} {streak === 1 ? 'day' : 'days'}
        </p>
      </CardContent>
    </Card>
  )
}
