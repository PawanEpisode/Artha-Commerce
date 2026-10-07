import { useTodayThought } from '~/modules/notifications'
import { useOnline } from '~/modules/personalization'

import { ThoughtView } from '../components/ThoughtView'
import { WidgetCard } from '../components/WidgetCard'
import { widgetState } from '../hooks/useWidgetState'

/**
 * A short line for the day (X-01.1 W3.3). It hides itself when there is nothing to say: notifications off, the student
 * turned motivation off, or no line fits them. Opening it is also what the nudge counts as "visited today".
 */
export function ThoughtWidget() {
  const { thought, off, query } = useTodayThought()
  const online = useOnline()
  if (off) return null
  return (
    <WidgetCard
      id="widget-thought"
      title="A thought for today"
      state={widgetState(query)}
      onRetry={() => void query.refetch()}
      offline={!online}
      skeletonHeight="h-16"
    >
      {thought ? <ThoughtView body={thought.body} attribution={thought.attribution} /> : null}
    </WidgetCard>
  )
}
