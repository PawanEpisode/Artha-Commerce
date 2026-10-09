import { Alert, Badge, Button, Skeleton, toast } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { ApiError } from '~/lib/api'

import { DeckItemRow } from '../components/DeckItemRow'
import { LoadError, RecallShell } from '../components/RecallShell'
import { ReportDialog } from '../components/ReportDialog'
import { useDeck, useReportItem, useResubscribe, useSubscribe, useUnsubscribe } from '../hooks/useDecks'
import type { Tier } from '../lib/api'
import { cardsText, newerText, subscribeMessage, subscriptionState, tiersText, tooLargeText } from '../lib/decks'
import { errorText } from '../lib/errors'
import type { ApiDeck, ApiDeckItem } from '../lib/schemas'

function SubscribeBar({ deck }: { deck: ApiDeck }) {
  const state = subscriptionState(deck)
  const subscribe = useSubscribe(deck.id)
  const unsubscribe = useUnsubscribe()
  const resubscribe = useResubscribe()
  const [tier, setTier] = useState<Tier | undefined>(undefined)
  const sub = deck.subscription
  const failure = subscribe.isError
    ? (tooLargeText(subscribe.error instanceof ApiError ? subscribe.error.body : undefined) ??
      errorText(subscribe.error, 'Could not add this deck. Please try again.'))
    : resubscribe.isError
      ? errorText(resubscribe.error, 'Could not bring this deck back. Please try again.')
      : unsubscribe.isError
        ? errorText(unsubscribe.error, 'Could not remove this deck. Please try again.')
        : null
  const newer = sub ? newerText(sub.newer_versions) : ''
  return (
    <div className="space-y-3 rounded-2xl border border-border bg-card p-4 sm:p-5">
      {state === 'none' ? (
        <>
          <p className="text-sm text-muted-foreground">
            Adding this deck puts {cardsText(deck)} into your revision. Your progress stays with you if you remove it
            later.
          </p>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Which cards to add">
            {(
              [
                [undefined, 'All cards'],
                ['important', 'Important and must know'],
                ['mandatory', 'Must know only'],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={label}
                size="sm"
                variant={tier === value ? 'default' : 'outline'}
                aria-pressed={tier === value}
                onClick={() => setTier(value)}
              >
                {label}
              </Button>
            ))}
          </div>
          <Button
            loading={subscribe.isPending}
            onClick={() => subscribe.mutate(tier, { onSuccess: (r) => toast.success(subscribeMessage(r)) })}
          >
            Add this deck to my revision
          </Button>
        </>
      ) : null}
      {state === 'active' ? (
        <>
          <p className="text-sm">
            <Badge variant="accent">Subscribed</Badge> <span className="ml-1">Version {sub?.version_no}</span>
          </p>
          {newer ? (
            <p className="text-xs text-muted-foreground">{newer}. Your cards stay as they are for now.</p>
          ) : null}
          <Button
            variant="outline"
            loading={unsubscribe.isPending}
            onClick={() =>
              sub && unsubscribe.mutate(sub.id, { onSuccess: () => toast.success('Removed. Your progress is kept.') })
            }
          >
            Remove from my revision
          </Button>
        </>
      ) : null}
      {state === 'archived' ? (
        <>
          <p className="text-sm text-muted-foreground">
            You removed this deck. Bring it back and your cards return with the progress you had.
          </p>
          <Button
            loading={resubscribe.isPending}
            onClick={() => sub && resubscribe.mutate(sub.id, { onSuccess: (r) => toast.success(subscribeMessage(r)) })}
          >
            Bring it back
          </Button>
        </>
      ) : null}
      {failure ? <Alert variant="error">{failure}</Alert> : null}
    </div>
  )
}

function Detail({ deckId }: { deckId: string }) {
  const q = useDeck(deckId)
  const report = useReportItem()
  const [reporting, setReporting] = useState<ApiDeckItem | null>(null)
  if (q.isPending) {
    return (
      <div aria-busy="true" className="space-y-3">
        <span className="sr-only" role="status">
          Loading the deck…
        </span>
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }
  if (q.isError || !q.data) {
    const gone = q.error instanceof ApiError && q.error.status === 404
    return gone ? (
      <Alert variant="error">
        <span className="flex flex-wrap items-center gap-3">
          This deck is not available.
          <Button variant="outline" asChild>
            <Link to="/app/recall/decks">Back to decks</Link>
          </Button>
        </span>
      </Alert>
    ) : (
      <LoadError what="this deck" onRetry={() => void q.refetch()} />
    )
  }
  const { deck, items } = q.data
  return (
    <>
      <nav aria-label="Breadcrumb">
        <Link to="/app/recall/decks" className="text-sm text-muted-foreground hover:underline">
          ← All decks
        </Link>
      </nav>
      <header className="space-y-2">
        <h1 className="text-3xl font-extrabold break-words">{deck.title}</h1>
        {deck.description ? <p className="text-muted-foreground">{deck.description}</p> : null}
        <p className="text-sm">
          {cardsText(deck)}
          {tiersText(deck.tiers) ? <span className="text-muted-foreground"> ({tiersText(deck.tiers)})</span> : null}
        </p>
        {deck.changelog_md ? (
          <p className="text-xs text-muted-foreground">
            Version {deck.version_no}: {deck.changelog_md}
          </p>
        ) : null}
      </header>
      <SubscribeBar deck={deck} />
      <section aria-labelledby="deck-items-heading" className="space-y-3">
        <h2 id="deck-items-heading" className="font-display text-xl font-bold">
          What is inside
        </h2>
        <ul aria-label="Cards in this deck" className="space-y-3">
          {items.map((item) => (
            <DeckItemRow
              key={item.item_id}
              item={item}
              onReport={(i) => {
                report.reset()
                setReporting(i)
              }}
            />
          ))}
        </ul>
      </section>
      <ReportDialog
        key={reporting?.item_id ?? 'none'}
        open={reporting !== null}
        onOpenChange={(open) => (open ? undefined : setReporting(null))}
        preview={reporting?.preview ?? ''}
        pending={report.isPending}
        error={report.isError ? errorText(report.error, 'Could not send your report. Please try again.') : null}
        onSubmit={(reason, note) =>
          reporting &&
          report.mutate(
            { itemId: reporting.item_id, reason, note },
            {
              onSuccess: () => {
                setReporting(null)
                toast.success('Thank you. Our editors will look at it.')
              },
            },
          )
        }
      />
    </>
  )
}

export function DeckDetailContainer({ deckId }: { deckId: string }) {
  return (
    <RecallShell>
      <Detail deckId={deckId} />
    </RecallShell>
  )
}
