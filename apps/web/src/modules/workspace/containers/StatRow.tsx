import { StatTile } from '@artha/design-system'

import { useDue, useOverview } from '~/modules/coverage'
import { useFeatureFlag } from '~/modules/observability'
import { formatDuration, isTrackerOff, useGoals } from '~/modules/tracker'

/**
 * The four numbers a student checks first: time today, streak, course progress and chapters due. Each tile appears only
 * once its data is in and its feature is on, so a slow or switched-off feature leaves a smaller row, never a hole.
 */
export function StatRow() {
  const goals = useGoals()
  const trackerOn = useFeatureFlag('time_tracker')
  const overview = useOverview()
  const due = useDue()

  const daily = trackerOn && !isTrackerOff(goals.error) ? goals.data?.progress.daily : undefined
  const streak = trackerOn && !isTrackerOff(goals.error) ? goals.data?.progress.streak : undefined
  const level = overview.featureDisabled || overview.noEnrollment ? undefined : overview.data?.level
  const dueCount = due.noEnrollment || overview.featureDisabled ? undefined : due.data?.results.length

  const tiles = [
    daily
      ? {
          key: 'today',
          label: 'Studied today',
          value: formatDuration(daily.done_seconds),
          hint: `Goal ${formatDuration(daily.target_minutes * 60)} (${daily.percent}%)`,
        }
      : null,
    streak !== undefined
      ? { key: 'streak', label: 'Streak', value: String(streak), hint: streak === 1 ? 'day' : 'days' }
      : null,
    level
      ? {
          key: 'progress',
          label: 'Course progress',
          value: `${Math.round(level.pct_simple)}%`,
          hint: `${level.chapters_done} of ${level.chapters_total} chapters done`,
        }
      : null,
    dueCount !== undefined
      ? {
          key: 'due',
          label: 'Revision due',
          value: String(dueCount),
          hint: dueCount === 1 ? 'chapter' : 'chapters',
        }
      : null,
  ].filter((tile) => tile !== null)

  if (tiles.length === 0) return null
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 [&>*]:min-w-0" data-testid="home-stats">
      {tiles.map((tile) => (
        <StatTile key={tile.key} label={tile.label} value={tile.value} hint={tile.hint} className="p-3" />
      ))}
    </div>
  )
}
