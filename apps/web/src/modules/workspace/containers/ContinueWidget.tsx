import { useRouter } from '@tanstack/react-router'

import { isCoverageOff, useContinue } from '~/modules/coverage'
import { cleanVisit, useBootstrap, useOnline, visitHref } from '~/modules/personalization'

import { ContinueView } from '../components/ContinueView'
import { WidgetCard } from '../components/WidgetCard'
import { widgetState } from '../hooks/useWidgetState'

/** The chapter studied most recently; failing that the last visited page; on day one, the syllabus map. */
export function ContinueWidget() {
  const query = useContinue()
  const { data: me } = useBootstrap()
  const online = useOnline()
  const router = useRouter()
  if (query.featureDisabled || query.noEnrollment || isCoverageOff(query.error)) return null

  const visit = me?.last_visit ? cleanVisit(me.last_visit.path, me.last_visit.search) : null
  const returnTo = visit && visit.path !== '/app' ? visitHref(visit) : null

  return (
    <WidgetCard
      id="widget-continue"
      title="Continue where you left off"
      state={widgetState(query)}
      onRetry={() => void query.refetch()}
      offline={!online}
    >
      {query.data !== undefined ? (
        <ContinueView chapter={query.data} onReturn={returnTo ? () => router.history.push(returnTo) : undefined} />
      ) : null}
    </WidgetCard>
  )
}
