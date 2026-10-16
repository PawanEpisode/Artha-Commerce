import { Flame, StatTile } from '@artha/design-system'

import { formatDuration } from '~/modules/tracker'

interface Props {
  doneSeconds: number
  targetMinutes: number
  percent: number
  streak: number
  /** Pomodoro rounds finished today. */
  rounds: number
}

/** Today at a glance as a stat row: the shared daily goal (all study time counts), rounds finished and the streak. */
export function TodayCard({ doneSeconds, targetMinutes, percent, streak, rounds }: Props) {
  return (
    <section aria-label="Today" className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <StatTile
        className="col-span-2 p-3 shadow-none sm:col-span-1"
        label="Daily goal"
        value={`${Math.round(percent)}%`}
        hint={`${formatDuration(doneSeconds)} of ${formatDuration(targetMinutes * 60)}. All study time counts.`}
      />
      <StatTile
        className="p-3 shadow-none"
        label="Rounds today"
        value={rounds}
        hint={`${rounds === 1 ? '1 round' : `${rounds} rounds`} finished today`}
      />
      <StatTile
        className="p-3 shadow-none"
        label="Streak"
        value={
          <span className="flex items-center gap-1.5">
            <Flame className="size-5 text-primary" aria-hidden />
            {streak} {streak === 1 ? 'day' : 'days'}
          </span>
        }
      />
    </section>
  )
}
