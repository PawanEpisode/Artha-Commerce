import { useOverview } from '~/modules/coverage'
import { useOnline } from '~/modules/personalization'

import { ProgressView } from '../components/ProgressView'
import { WidgetCard } from '../components/WidgetCard'
import { widgetState } from '../hooks/useWidgetState'
import { weakestSubjects } from '../lib/summaries'

/** Average progress across chapters, in numbers and words, and the three papers furthest behind. */
export function ProgressWidget() {
  const overview = useOverview()
  const online = useOnline()
  if (overview.featureDisabled || overview.noEnrollment) return null
  const data = overview.data
  return (
    <WidgetCard
      id="widget-progress"
      title="Course progress"
      state={widgetState(overview)}
      onRetry={() => void overview.refetch()}
      offline={!online}
      skeletonHeight="h-52"
    >
      {data ? (
        <ProgressView
          percent={Math.round(data.level.pct_simple)}
          counts={{
            chaptersDone: data.level.chapters_done,
            chaptersStarted: data.level.chapters_started,
            chaptersTotal: data.level.chapters_total,
          }}
          weakest={weakestSubjects(data.subjects)}
        />
      ) : null}
    </WidgetCard>
  )
}
