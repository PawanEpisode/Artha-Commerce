import { useLiveTimer } from '~/modules/focus'
import { useFeatureFlag } from '~/modules/observability'
import { useOnline } from '~/modules/personalization'
import { formatDuration, isTrackerOff, useGoals } from '~/modules/tracker'

import { TodayView } from '../components/TodayView'
import { WidgetCard } from '../components/WidgetCard'
import { widgetState } from '../hooks/useWidgetState'
import { todayAction } from '../lib/today'

/** Time today against the daily goal, the streak and the one button that starts or resumes studying. */
export function TodayWidget() {
  const goals = useGoals()
  const focusOn = useFeatureFlag('focus_timer')
  const trackerOn = useFeatureFlag('time_tracker')
  const { live } = useLiveTimer()
  const online = useOnline()
  if (!trackerOn || isTrackerOff(goals.error)) return null

  const daily = goals.data?.progress.daily
  return (
    <WidgetCard
      id="widget-today"
      title="Today"
      state={widgetState(goals)}
      onRetry={() => void goals.refetch()}
      offline={!online}
    >
      {daily && goals.data ? (
        <TodayView
          percent={daily.percent}
          doneLabel={`${formatDuration(daily.done_seconds)} of ${formatDuration(daily.target_minutes * 60)}`}
          streak={goals.data.progress.streak}
          action={todayAction({ live, focusOn, doneSeconds: daily.done_seconds })}
          canLogTime
        />
      ) : null}
    </WidgetCard>
  )
}
