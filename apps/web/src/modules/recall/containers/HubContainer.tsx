import { Alert, Button, ButtonLink, CircleCheck, EmptyState, Layers, Skeleton, WifiOff } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useMemo } from 'react'

import { CatchUpNotice } from '../components/CatchUpNotice'
import { ForgottenRow } from '../components/ForgottenRow'
import { QueueSummary } from '../components/QueueSummary'
import { LoadError, RecallShell } from '../components/RecallShell'
import { SyncStatus } from '../components/SyncStatus'
import { usePack } from '../hooks/usePack'
import { useOnlineStatus } from '../hooks/useRecallBasics'
import { useRebalance, useSetVacation } from '../hooks/useSettings'
import { useSync } from '../hooks/useSync'
import { useTodayPlan } from '../hooks/useTodayPlan'
import { nowDate } from '../lib/clock'
import { plural, shortDate } from '../lib/format'
import { hubStateOf } from '../lib/hub'
import { planFromPack } from '../lib/player'
import type { TodayPlan } from '../lib/schemas'

function StartLink({ label = 'Start reviewing', source = 'today' }: { label?: string; source?: string }) {
  return (
    <ButtonLink size="lg" asChild>
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
  const next = plan.next_due_at ? new Date(plan.next_due_at) : null

  const hero =
    state === 'vacation' ? (
      <section className="space-y-3 rounded-2xl border border-border bg-card p-5">
        <h2 className="font-display text-xl font-bold">You are on vacation</h2>
        <p className="text-sm text-muted-foreground">
          Reviews are paused until {plan.vacation_until ? shortDate(plan.vacation_until) : 'you return'}. Your streak is
          safe and nothing piles up as overdue while you are away.
        </p>
        <Button variant="outline" onClick={() => vacation.mutate(null)} disabled={vacation.isPending}>
          End vacation now
        </Button>
      </section>
    ) : state === 'empty' ? (
      <EmptyState
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
      {hero}
      {rebalance.isSuccess ? (
        <Alert variant="success">
          <span role="status">Done. Your backlog is spread over the coming days.</span>
        </Alert>
      ) : null}
      {plan.limits.new_done > 0 || plan.limits.reviews_done > 0 ? (
        <p className="text-sm text-muted-foreground">
          Today so far: {plural(plan.limits.reviews_done, 'review')} and {plural(plan.limits.new_done, 'new card')}.
        </p>
      ) : null}
      {plan.forgotten.length > 0 ? (
        <section aria-labelledby="forgotten-heading" className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="forgotten-heading" className="font-display text-lg font-bold">
              Slipping away
            </h2>
            <ButtonLink variant="outline" size="sm" asChild>
              <Link to="/app/recall/review" search={{ source: 'forgotten' }}>
                Review these
              </Link>
            </ButtonLink>
          </div>
          <ul className="space-y-3">
            {plan.forgotten.slice(0, 3).map((f) => (
              <ForgottenRow key={f.card_id} item={f} />
            ))}
          </ul>
        </section>
      ) : null}
      {plan.tiles.length > 0 ? (
        <section aria-labelledby="subjects-heading" className="space-y-3">
          <h2 id="subjects-heading" className="font-display text-lg font-bold">
            By subject
          </h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {plan.tiles.map((t) => (
              <li
                key={t.subject_key ?? 'none'}
                className="flex items-center justify-between rounded-xl border border-border bg-card px-4 py-3 text-sm"
              >
                <span className="font-medium">{t.subject_key ?? 'Other'}</span>
                <span className="text-muted-foreground">{plural(t.total, 'card')}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  )
}

/** Offline, with no plan from the server: today's size from the cards stored on this device. */
function OfflineHub() {
  const { pack, loading } = usePack()
  const planned = useMemo(() => (pack ? planFromPack(pack, nowDate()).cards.length : 0), [pack])
  if (loading) return <Skeleton className="h-40 w-full" />
  if (!pack) {
    return (
      <EmptyState
        icon={<WifiOff aria-hidden />}
        title="You are offline"
        description="Connect once to download your cards, then you can review without a connection."
      />
    )
  }
  return (
    <section className="space-y-3 rounded-2xl border border-border bg-card p-5">
      <h2 className="font-display text-xl font-bold">{plural(planned, 'card')} on this device</h2>
      <p className="text-sm text-muted-foreground">
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
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Revision</h1>
        <p className="text-muted-foreground">Short reviews, spaced so you remember for the exam.</p>
      </header>
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
        <div aria-busy="true" className="space-y-4">
          <span className="sr-only" role="status">
            Loading today's revision…
          </span>
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-24 w-full" />
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
