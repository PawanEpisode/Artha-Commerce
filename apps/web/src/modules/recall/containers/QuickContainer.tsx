import { Alert, ButtonLink, CalendarDays, EmptyState, PageHeader, Skeleton, WifiOff } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect } from 'react'

import { ApiError } from '~/lib/api'

import { QuickPlanView } from '../components/QuickPlanView'
import { LoadError, RecallShell } from '../components/RecallShell'
import { useQuickPlan } from '../hooks/useQuickPlan'
import { useOnlineStatus } from '../hooks/useRecallBasics'
import { trackRecall } from '../lib/analytics'
import type { QuickSearch } from '../lib/search'

function Quick({ search }: { search: QuickSearch }) {
  const online = useOnlineStatus()
  const q = useQuickPlan({ minutes: search.minutes }, online)
  const plan = q.data
  useEffect(() => {
    if (plan) {
      trackRecall('recall_quick_planned', {
        days_to_exam: plan.days_to_exam,
        set_size: plan.selected,
        cut_off: plan.cut_off,
        minutes_per_day: plan.budget_minutes_per_day,
      })
    }
  }, [plan])
  const code = q.error instanceof ApiError ? q.error.code : undefined

  return (
    <>
      <PageHeader
        title="Quick revision"
        description="The cards most likely to fade before your exam, fitted to the minutes you have."
      />
      {!online ? (
        <EmptyState
          className="rounded-lg py-6"
          icon={<WifiOff aria-hidden />}
          title="You are offline"
          description="The plan needs a connection. Your normal reviews still work."
        />
      ) : q.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <span className="sr-only" role="status">
            Planning…
          </span>
          <Skeleton className="h-40 w-full" />
        </div>
      ) : code === 'no_exam_date' ? (
        <EmptyState
          className="rounded-lg py-6"
          icon={<CalendarDays aria-hidden />}
          title="Add your exam date"
          description="Quick revision counts back from your exam. Set the date in your coverage settings."
          action={
            <ButtonLink asChild>
              <Link to="/app/settings/coverage">Set exam date</Link>
            </ButtonLink>
          }
        />
      ) : code === 'exam_passed' ? (
        <Alert variant="info">Your exam date has passed. Update it in your coverage settings to plan again.</Alert>
      ) : q.isError ? (
        <LoadError what="the plan" onRetry={() => void q.refetch()} />
      ) : (
        <QuickPlanView plan={q.data} minutes={search.minutes ?? q.data.budget_minutes_per_day} />
      )}
    </>
  )
}

export function QuickContainer({ search }: { search: QuickSearch }) {
  return (
    <RecallShell>
      <Quick search={search} />
    </RecallShell>
  )
}
