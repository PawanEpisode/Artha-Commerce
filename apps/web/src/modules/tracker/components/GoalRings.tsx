import { Flame, ProgressBar, ProgressRing, Target } from '@artha/design-system'

import { formatDuration } from '../lib/duration'
import type { GoalProgressEntry, GoalsPayload } from '../lib/types'

const PACE_TEXT = {
  ahead: 'Ahead of pace',
  on_track: 'On track',
  behind: 'Behind pace',
} as const

function paceNote(entry: GoalProgressEntry): string | null {
  if (!entry.pace) return null
  const gap = formatDuration(Math.abs(entry.pace.delta_seconds))
  if (entry.pace.state === 'on_track') return PACE_TEXT.on_track
  return `${PACE_TEXT[entry.pace.state]} by ${gap}`
}

/** Today's goal as a ring, the weekly goal and subject goals as bars, and the streak. Text carries every number. */
export function GoalRings({ progress }: { progress: GoalsPayload['progress'] }) {
  const { daily, weekly, subjects, streak } = progress
  return (
    <section aria-labelledby="goals-heading" className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="goals-heading" className="flex items-center gap-2 text-sm font-semibold">
          <Target className="size-4 text-primary" aria-hidden /> Goals
        </h2>
        <p className="flex items-center gap-1.5 text-[13px] font-medium">
          <Flame className="size-3.5 text-primary" aria-hidden />
          {streak === 1 ? '1 day streak' : `${streak} day streak`}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <ProgressRing value={daily.percent} label="Today's goal" size={80} strokeWidth={8}>
          <span className="text-center">
            <span className="block text-base font-semibold">{daily.percent}%</span>
            <span className="block text-[10px] text-muted-foreground">today</span>
          </span>
        </ProgressRing>
        <div className="space-y-0.5 text-[13px]">
          <p className="font-semibold">
            {formatDuration(daily.done_seconds)} of {formatDuration(daily.target_minutes * 60)}
          </p>
          <p className="text-muted-foreground">
            {daily.is_default ? 'Starting goal. Set your own on the goals page.' : 'Daily goal'}
          </p>
        </div>
      </div>
      {weekly ? (
        <div className="space-y-1.5">
          <p className="flex flex-wrap justify-between gap-2 text-[13px] font-semibold">
            <span>This week</span>
            <span className="tabular-nums">
              {formatDuration(weekly.done_seconds)} of {formatDuration(weekly.target_minutes * 60)}
            </span>
          </p>
          <ProgressBar value={weekly.percent} label="Weekly goal" />
          {paceNote(weekly) ? <p className="text-xs text-muted-foreground">{paceNote(weekly)}</p> : null}
        </div>
      ) : null}
      {subjects.length > 0 ? (
        <ul className="space-y-2.5">
          {subjects.map((g) => (
            <li key={g.subject_key} className="space-y-1.5">
              <p className="flex flex-wrap justify-between gap-2 text-[13px] font-semibold">
                <span>{g.subject_name || g.subject_key}</span>
                <span className="tabular-nums">
                  {formatDuration(g.done_seconds)} of {formatDuration(g.target_minutes * 60)}
                </span>
              </p>
              <ProgressBar value={g.percent} label={`${g.subject_name} weekly goal`} size="sm" />
              {paceNote(g) ? <p className="text-xs text-muted-foreground">{paceNote(g)}</p> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
