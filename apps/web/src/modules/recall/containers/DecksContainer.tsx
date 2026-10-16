import { Button, EmptyState, Layers, PageHeader, SelectField, Skeleton, TableToolbar } from '@artha/design-system'
import { useState } from 'react'

import { DeckTable } from '../components/DeckCard'
import { LoadError, RecallShell } from '../components/RecallShell'
import { useDeckLibrary, useMyDecks } from '../hooks/useDecks'
import { isTier, TIER_FILTER_OPTIONS } from '../lib/decks'
import type { DecksSearch } from '../lib/search'

function Loading() {
  return (
    <div aria-busy="true" className="space-y-1">
      <span className="sr-only" role="status">
        Loading decks…
      </span>
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
    </div>
  )
}

function Mine() {
  const q = useMyDecks()
  const active = (q.data ?? []).filter((d) => d.subscription?.status === 'active')
  if (q.isPending || q.isError || active.length === 0) return null
  return (
    <section aria-labelledby="my-decks-heading" className="space-y-2">
      <h2 id="my-decks-heading" className="text-sm font-semibold">
        Your decks
      </h2>
      <DeckTable label="Your decks" decks={active} />
    </section>
  )
}

function Library({ tier, onTier }: { tier: string; onTier: (tier: string) => void }) {
  const q = useDeckLibrary(isTier(tier) ? tier : undefined)
  const decks = q.data?.pages.flatMap((p) => p.items) ?? []
  return (
    <section aria-labelledby="library-heading" className="space-y-2">
      <h2 id="library-heading" className="text-sm font-semibold">
        Library
      </h2>
      <TableToolbar>
        <SelectField
          aria-label="Show"
          className="w-full sm:w-64"
          value={tier}
          onValueChange={onTier}
          options={TIER_FILTER_OPTIONS}
        />
      </TableToolbar>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <LoadError what="the decks" onRetry={() => void q.refetch()} />
      ) : decks.length === 0 ? (
        <EmptyState
          className="rounded-lg py-6"
          icon={<Layers aria-hidden />}
          title="No decks yet"
          description="Ready-made decks from our editors will appear here as they are published."
        />
      ) : (
        <>
          <DeckTable label="Deck library" decks={decks} />
          {q.hasNextPage ? (
            <Button variant="outline" size="sm" loading={q.isFetchingNextPage} onClick={() => void q.fetchNextPage()}>
              Show more decks
            </Button>
          ) : null}
        </>
      )}
    </section>
  )
}

/** `search` and `onSearch` carry the tier filter in the URL; without them (tests, embeds) it is local state. */
function Decks({ search, onSearch }: { search?: DecksSearch; onSearch?: (next: DecksSearch) => void }) {
  const [local, setLocal] = useState('')
  const tier = search ? (search.tier ?? '') : local
  const setTier = (next: string) => (onSearch ? onSearch({ tier: isTier(next) ? next : undefined }) : setLocal(next))
  return (
    <>
      <PageHeader
        title="Decks"
        description="Ready-made cards written by our editors. Add a deck and its cards join your daily revision."
      />
      <Mine />
      <Library tier={tier} onTier={setTier} />
    </>
  )
}

export function DecksContainer({ search, onSearch }: { search?: DecksSearch; onSearch?: (next: DecksSearch) => void }) {
  return (
    <RecallShell>
      <Decks search={search} onSearch={onSearch} />
    </RecallShell>
  )
}
