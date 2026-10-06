import { useDue, useOverview } from '~/modules/coverage'
import { useOnline } from '~/modules/personalization'

import { DueView } from '../components/DueView'
import { WidgetCard } from '../components/WidgetCard'
import { widgetState } from '../hooks/useWidgetState'
import { topDue } from '../lib/summaries'

/** Up to three chapters due for revision. Hidden when none, except a short "Nothing due" for students who study. */
export function RevisionWidget() {
  const due = useDue()
  const overview = useOverview()
  const online = useOnline()
  if (due.noEnrollment || overview.featureDisabled) return null

  const rows = due.data?.results ?? []
  const hasStudied = (overview.data?.level.chapters_started ?? 0) > 0
  if (due.data && rows.length === 0 && !hasStudied) return null

  return (
    <WidgetCard
      id="widget-revision"
      title="Next revision due"
      state={widgetState(due)}
      onRetry={() => void due.refetch()}
      offline={!online}
    >
      {rows.length > 0 ? (
        <DueView rows={topDue(rows)} total={rows.length} />
      ) : (
        <p className="text-sm text-muted-foreground">Nothing due. Nice.</p>
      )}
    </WidgetCard>
  )
}
