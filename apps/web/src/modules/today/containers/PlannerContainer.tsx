import {
  Alert,
  Button,
  CalendarClock,
  Container,
  EmptyState,
  Skeleton,
  Sparkles,
  TextField,
  toast,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { MilestoneList } from '../components/MilestoneList'
import { PlannerHealthCard } from '../components/PlannerHealthCard'
import { ReplanOptions } from '../components/ReplanOptions'
import { hasNoStudyPlan, useChooseOption, useCreateStudyPlan, useReplan, useStudyPlan } from '../hooks/usePlanner'
import { usePlannerFlag } from '../hooks/usePlannerFlag'
import { errorCode, errorDetails, errorMessage, isFeatureDisabled } from '../lib/api'
import { gotWorse, replanSummary } from '../lib/planner'
import type { OptionChoice } from '../lib/planner-types'

const Shell = ({ children }: { children: React.ReactNode }) => (
  <Container className="max-w-3xl min-w-0 space-y-5 py-6 sm:space-y-6 sm:py-10">{children}</Container>
)

function Heading() {
  return (
    <header className="space-y-1">
      <h1 className="font-display text-2xl font-extrabold">Study plan</h1>
      <p className="text-sm text-muted-foreground">
        Dates for reading, revision and mocks, worked out from your exam date.
      </p>
    </header>
  )
}

function Unavailable() {
  return (
    <Shell>
      <EmptyState
        icon={<Sparkles aria-hidden />}
        title="The study plan is not available yet"
        description="We are rolling it out gradually. Please check back soon."
        action={
          <Button asChild variant="outline">
            <Link to="/app/today">Back to Today</Link>
          </Button>
        }
      />
    </Shell>
  )
}

function Loading() {
  return (
    <Shell>
      <div role="status" aria-label="Loading your study plan" className="space-y-4">
        <Skeleton className="h-40 w-full rounded-2xl" />
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-16 w-full rounded-xl" />
      </div>
    </Shell>
  )
}

/** First time: make the plan from the course. If the course lacks something, say what and where to set it. */
function FirstPlan() {
  const create = useCreateStudyPlan()
  const [minutes, setMinutes] = useState('')
  const reason = create.isError ? (errorDetails(create.error).reason as string | undefined) : undefined
  const asksForMinutes = reason === 'no_daily_minutes'
  const parsed = Number(minutes)
  const bad = asksForMinutes && !(Number.isInteger(parsed) && parsed >= 30 && parsed <= 720)

  const make = () => {
    if (bad) return
    create.mutate(asksForMinutes ? parsed : undefined, {
      onSuccess: () => toast.success('Your study plan is ready'),
    })
  }

  return (
    <Shell>
      <Heading />
      <EmptyState
        icon={<CalendarClock aria-hidden />}
        title="Make your study plan"
        description="We use your exam date and your chapters to date when to finish reading, start revising and sit mocks. You can re-plan any time."
        action={
          <div className="space-y-3 text-left">
            {asksForMinutes ? (
              <TextField
                label="Minutes you can study each day"
                type="number"
                inputMode="numeric"
                min={30}
                max={720}
                value={minutes}
                onChange={(e) => setMinutes(e.target.value)}
                error={minutes && bad ? 'Use a number from 30 to 720.' : undefined}
              />
            ) : null}
            <Button onClick={make} disabled={create.isPending || (asksForMinutes && bad)}>
              {create.isPending ? 'Making your plan' : 'Make my plan'}
            </Button>
          </div>
        }
      />
      {create.isError && errorCode(create.error) === 'planner_not_ready' ? (
        <Alert variant="info">
          <p>{errorMessage(create.error)}</p>
          {reason === 'not_enrolled' ? (
            <Button asChild className="mt-3" variant="outline" size="sm">
              <Link to="/app/onboarding">Set up your course</Link>
            </Button>
          ) : null}
          {reason === 'no_exam_date' || reason === 'post_exam' ? (
            <Button asChild className="mt-3" variant="outline" size="sm">
              <Link to="/app/account">Update your exam date</Link>
            </Button>
          ) : null}
        </Alert>
      ) : create.isError ? (
        <Alert variant="error">{errorMessage(create.error)}</Alert>
      ) : null}
    </Shell>
  )
}

/** /app/planner (FR-F13-51): health card, the options when the reading does not fit, the milestones, and "Re-plan". */
export function PlannerContainer() {
  const enabled = usePlannerFlag()
  const plan = useStudyPlan(enabled)
  const replan = useReplan()
  const choose = useChooseOption()

  if (!enabled || isFeatureDisabled(plan.error)) return <Unavailable />
  if (plan.isPending) return <Loading />
  if (hasNoStudyPlan(plan.error)) return <FirstPlan />
  if (plan.isError || !plan.data)
    return (
      <Shell>
        <Alert variant="error">
          <p>We could not load your study plan.</p>
          <Button className="mt-3" variant="outline" size="sm" onClick={() => void plan.refetch()}>
            Try again
          </Button>
        </Alert>
      </Shell>
    )

  const data = plan.data
  const onReplan = () =>
    replan.mutate(undefined, {
      onSuccess: (res) => {
        if (res.replan && !res.pending) toast.success(replanSummary(res.replan))
      },
      onError: (error) => toast.error(errorMessage(error)),
    })
  const onChoose = (option: OptionChoice) => {
    if (!data.pending) return
    choose.mutate(
      { eventId: data.pending.id, option },
      {
        onSuccess: () => toast.success(option === 'none' ? 'Your plan stays as it is' : 'Your plan is updated'),
        onError: (error) => toast.error(errorMessage(error)),
      },
    )
  }
  const worse = data.latest_replan ? gotWorse(data.latest_replan.health_before, data.latest_replan.health_after) : false

  return (
    <Shell>
      <Heading />
      <PlannerHealthCard plan={data} replanning={replan.isPending} onReplan={onReplan} />
      {data.pending ? <ReplanOptions event={data.pending} busy={choose.isPending} onChoose={onChoose} /> : null}
      {!data.pending && worse ? (
        <Alert variant="info">Your plan slipped since the last check. Re-plan to see what you can do about it.</Alert>
      ) : null}
      <MilestoneList milestones={data.milestones} />
    </Shell>
  )
}
