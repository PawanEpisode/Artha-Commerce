import {
  Alert,
  Button,
  ButtonLink,
  CircleCheck,
  DataTable,
  EmptyState,
  Layers,
  PageHeader,
  Skeleton,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  WifiOff,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useMemo } from 'react'

import { CatchUpNotice } from '../components/CatchUpNotice'
import { ExamStrip } from '../components/ExamStrip'
import { ForgottenTable } from '../components/ForgottenRow'
import { QueueSummary } from '../components/QueueSummary'
import { LoadError, RecallShell } from '../components/RecallShell'
import { SyncStatus } from '../components/SyncStatus'
import { usePack } from '../hooks/usePack'
import { useOnlineStatus } from '../hooks/useRecallBasics'
import { useRebalance, useSetVacation } from '../hooks/useSettings'
import { useSync } from '../hooks/useSync'
import { useTodayPlan } from '../hooks/useTodayPlan'
import { trackRecall } from '../lib/analytics'
import { nowDate } from '../lib/clock'
import { plural, shortDate } from '../lib/format'
import { hubStateOf } from '../lib/hub'
import { planFromPack } from '../lib/player'
import type { TodayPlan } from '../lib/schemas'

function StartLink({ label = 'Start reviewing', source = 'today' }: { label?: string; source?: string }) {
  return (
    <ButtonLink asChild>
      <Link to="/app/recall/review" search={{ source: source as 'today' }}>
        {label}
      </Link>
    </ButtonLink>
  )
}

function HubBody({ plan }: { plan: TodayPlan }) {
  const state = hubStateOf(plan)
  const rebalance = useRebalance()
  const vacation = useSetVacation()
  const pacing = plan.exam?.pacing ?? null
  const daysLeft = plan.exam?.days_to_exam
  useEffect(() => {
    if (pacing && pacing.unseen > 0 && daysLeft !== undefined) {
      trackRecall('recall_pacing_viewed', {
        feasible: pacing.feasible,
        needed_per_day: pacing.needed_per_day,
        days_to_exam: Math.floor(daysLeft),
      })
    }
  }, [pacing, daysLeft])
  const next = plan.next_due_at ? new Date(plan.next_due_at) : null

  const hero =
    state === 'vacation' ? (
      <section className="space-y-3 rounded-lg border border-border bg-card p-4">
        <h2 className="text-base font-semibold">You are on vacation</h2>
        <p className="text-[13px] text-muted-foreground">
          Reviews are paused until {plan.vacation_until ? shortDate(plan.vacation_until) : 'you return'}. Your streak is
          safe and nothing piles up as overdue while you are away.
        </p>
        <Button variant="outline" size="sm" onClick={() => vacation.mutate(null)} disabled={vacation.isPending}>
          End vacation now
        </Button>
      </section>
    ) : state === 'empty' ? (
      <EmptyState
        className="rounded-lg py-6"
        icon={<Layers aria-hidden />}
        title="No revision cards yet"
        description="Select a line in your notes and choose Make a card. Cards you make appear here on the right day."
        action={
          <ButtonLink asChild>
            <Link to="/app/notes">Go to my notes</Link>
          </ButtonLink>
        }
      />
    ) : state === 'catchup' ? (
      <CatchUpNotice
        plan={plan}
        action={<StartLink label="Start catch-up" />}
        onRebalance={() => rebalance.mutate(7)}
        rebalancing={rebalance.isPending}
      />
    ) : state === 'caught_up' ? (
      <EmptyState
        className="rounded-lg py-6"
        icon={<CircleCheck aria-hidden />}
        title="All caught up"
        description={
          next
            ? `Your next card is due ${next.toLocaleString('en-IN', { weekday: 'short', hour: 'numeric', minute: '2-digit' })}.`
            : 'Nothing is due. Come back tomorrow.'
        }
        action={
          <ButtonLink variant="outline" asChild>
            <Link to="/app/recall/review" search={{ source: 'today', ahead: true }}>
              Review ahead 10 cards
            </Link>
          </ButtonLink>
        }
      />
    ) : (
      <QueueSummary plan={plan} action={<StartLink />} />
    )

  return (
    <>
      {plan.needs_chapter.count > 0 ? (
        <Alert variant="info">
          <span className="flex flex-wrap items-center gap-3">
            {plural(plan.needs_chapter.count, 'card needs', 'cards need')} a chapter of your new syllabus.
            <ButtonLink variant="outline" size="sm" asChild>
              <Link to="/app/recall/chapters">Choose chapters</Link>
            </ButtonLink>
          </span>
        </Alert>
      ) : null}
      {plan.recheck.count > 0 ? (
        <Alert variant="info">
          <span className="flex flex-wrap items-center gap-3">
            {plural(plan.recheck.count, 'card was', 'cards were')} updated and{' '}
            {plan.recheck.count === 1 ? 'needs' : 'need'} a quick re-check.
            <ButtonLink variant="outline" size="sm" asChild>
              <Link to="/app/recall/cards" search={{ state: 'recheck' }}>
                See them
              </Link>
            </ButtonLink>
          </span>
        </Alert>
      ) : null}
      {rebalance.isSuccess ? (
        <Alert variant="success">
          <span role="status">Done. Your backlog is spread over the coming days.</span>
        </Alert>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-4">
          {hero}
          {plan.limits.new_done > 0 || plan.limits.reviews_done > 0 ? (
            <p className="text-[13px] text-muted-foreground">
              Today so far: {plural(plan.limits.reviews_done, 'review')} and {plural(plan.limits.new_done, 'new card')}.
            </p>
          ) : null}
          {plan.forgotten.length > 0 ? (
            <section aria-labelledby="forgotten-heading" className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 id="forgotten-heading" className="text-sm font-semibold">
                  Slipping away
                </h2>
                <ButtonLink variant="outline" size="sm" asChild>
                  <Link to="/app/recall/review" search={{ source: 'forgotten' }}>
                    Review these
                  </Link>
                </ButtonLink>
              </div>
              <ForgottenTable items={plan.forgotten.slice(0, 5)} label="Cards slipping away" />
            </section>
          ) : null}
        </div>
        <div className="min-w-0 space-y-4">
          {plan.exam ? <ExamStrip exam={plan.exam} /> : null}
          {plan.tiles.length > 0 ? (
            <section aria-labelledby="subjects-heading" className="space-y-2">
              <h2 id="subjects-heading" className="text-sm font-semibold">
                By subject
              </h2>
              <DataTable aria-labelledby="subjects-heading">
                <TableHeader>
                  <TableRow>
                    <TableHead>Subject</TableHead>
                    <TableHead className="text-right">Cards</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {plan.tiles.map((t) => (
                    <TableRow key={t.subject_key ?? 'none'}>
                      <TableCell className="font-medium">{t.subject_key ?? 'Other'}</TableCell>
                      <TableCell className="text-right text-muted-foreground tabular-nums">
                        {plural(t.total, 'card')}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </DataTable>
            </section>
          ) : null}
        </div>
      </div>
    </>
  )
}

/** Offline, with no plan from the server: today's size from the cards stored on this device. */
function OfflineHub() {
  const { pack, loading } = usePack()
  const planned = useMemo(() => (pack ? planFromPack(pack, nowDate()).cards.length : 0), [pack])
  if (loading) return <Skeleton className="h-28 w-full" />
  if (!pack) {
    return (
      <EmptyState
        className="rounded-lg py-6"
        icon={<WifiOff aria-hidden />}
        title="You are offline"
        description="Connect once to download your cards, then you can review without a connection."
      />
    )
  }
  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-4">
      <h2 className="text-base font-semibold">{plural(planned, 'card')} on this device</h2>
      <p className="text-[13px] text-muted-foreground">
        You are offline. Reviews are saved here and sync when you are back.
      </p>
      {planned > 0 ? <StartLink /> : null}
    </section>
  )
}

function Hub() {
  const plan = useTodayPlan()
  const online = useOnlineStatus()
  const sync = useSync()
  return (
    <>
      <PageHeader title="Revision" description="Short reviews, spaced so you remember for the exam." />
      {sync.pending > 0 || !online ? (
        <SyncStatus
          pending={sync.pending}
          syncing={sync.syncing}
          online={online}
          last={sync.last}
          onRetry={() => void sync.syncNow()}
        />
      ) : null}
      {plan.isPending && online ? (
        <div aria-busy="true" className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <span className="sr-only" role="status">
            Loading today's revision…
          </span>
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-36 w-full" />
        </div>
      ) : plan.data ? (
        <HubBody plan={plan.data} />
      ) : !online ? (
        <OfflineHub />
      ) : (
        <LoadError what="today's revision" onRetry={() => void plan.refetch()} />
      )}
    </>
  )
}

export function HubContainer() {
  return (
    <RecallShell>
      <Hub />
    </RecallShell>
  )
}
