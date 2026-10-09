import { Button, EmptyState, Layers, SelectField, Skeleton } from '@artha/design-system'
import { useState } from 'react'

import { DeckCard } from '../components/DeckCard'
import { LoadError, RecallShell } from '../components/RecallShell'
import { useDeckLibrary, useMyDecks } from '../hooks/useDecks'
import { isTier, TIER_FILTER_OPTIONS } from '../lib/decks'

function Loading() {
  return (
    <div aria-busy="true" className="space-y-3">
      <span className="sr-only" role="status">
        Loading decks…
      </span>
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  )
}

function Mine() {
  const q = useMyDecks()
  const active = (q.data ?? []).filter((d) => d.subscription?.status === 'active')
  if (q.isPending || q.isError || active.length === 0) return null
  return (
    <section aria-labelledby="my-decks-heading" className="space-y-3">
      <h2 id="my-decks-heading" className="font-display text-xl font-bold">
        Your decks
      </h2>
      <ul aria-label="Your decks" className="space-y-3">
        {active.map((d) => (
          <DeckCard key={d.id} deck={d} />
        ))}
      </ul>
    </section>
  )
}

function Library() {
  const [tier, setTier] = useState('')
  const q = useDeckLibrary(isTier(tier) ? tier : undefined)
  const decks = q.data?.pages.flatMap((p) => p.items) ?? []
  return (
    <section aria-labelledby="library-heading" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="library-heading" className="font-display text-xl font-bold">
          Library
        </h2>
        <div className="grid w-full gap-1 sm:w-64">
          <label htmlFor="deck-tier" className="text-sm font-medium">
            Show
          </label>
          <SelectField id="deck-tier" value={tier} onValueChange={setTier} options={TIER_FILTER_OPTIONS} />
        </div>
      </div>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <LoadError what="the decks" onRetry={() => void q.refetch()} />
      ) : decks.length === 0 ? (
        <EmptyState
          icon={<Layers aria-hidden />}
          title="No decks yet"
          description="Ready-made decks from our editors will appear here as they are published."
        />
      ) : (
        <>
          <ul aria-label="Deck library" className="space-y-3">
            {decks.map((d) => (
              <DeckCard key={d.id} deck={d} />
            ))}
          </ul>
          {q.hasNextPage ? (
            <Button variant="outline" loading={q.isFetchingNextPage} onClick={() => void q.fetchNextPage()}>
              Show more decks
            </Button>
          ) : null}
        </>
      )}
    </section>
  )
}

function Decks() {
  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Decks</h1>
        <p className="text-muted-foreground">
          Ready-made cards written by our editors. Add a deck and its cards join your daily revision.
        </p>
      </header>
      <Mine />
      <Library />
    </>
  )
}

export function DecksContainer() {
  return (
    <RecallShell>
      <Decks />
    </RecallShell>
  )
}
