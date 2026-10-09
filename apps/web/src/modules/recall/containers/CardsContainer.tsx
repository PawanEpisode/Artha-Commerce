import {
  Alert,
  Button,
  ButtonLink,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  EmptyState,
  FilterChip,
  Input,
  SelectField,
  Skeleton,
  Sparkles,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'

import { CardRow } from '../components/CardRow'
import { LoadError, RecallShell } from '../components/RecallShell'
import { useCards } from '../hooks/useCards'
import { useBulkCards } from '../hooks/useCardScreens'
import { KIND_LABELS } from '../lib/cardKinds'
import { CARD_STATES, type CardsSearch, hasFilters, listParams } from '../lib/cardSearch'
import { errorText } from '../lib/errors'

const STATE_LABEL: Record<string, string> = {
  new: 'New',
  learning: 'Learning',
  review: 'In review',
  suspended: 'Paused',
  tricky: 'Tricky',
  recheck: 'Needs a look',
}
const TIER_LABEL: Record<string, string> = { bullet: 'Normal', important: 'Important', mandatory: 'Must know' }
const SORT_LABEL: Record<string, string> = {
  newest: 'Newest first',
  oldest: 'Oldest first',
  updated: 'Recently edited',
}

const ANY = ''

function Search({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  const [text, setText] = useState(value)
  useEffect(() => setText(value), [value])
  useEffect(() => {
    if (text === value) return
    const t = setTimeout(() => onCommit(text), 350)
    return () => clearTimeout(t)
  }, [text, value, onCommit])
  return (
    <div className="grid gap-1">
      <label htmlFor="card-search" className="text-sm font-medium">
        Search your cards
      </label>
      <Input id="card-search" type="search" value={text} onChange={(e) => setText(e.target.value)} />
    </div>
  )
}

function Cards({ search }: { search: CardsSearch }) {
  const navigate = useNavigate()
  const params = useMemo(() => listParams(search), [search])
  const q = useCards(params)
  const bulk = useBulkCards()
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set())
  const [confirmDelete, setConfirmDelete] = useState(false)

  const cards = useMemo(() => q.data?.pages.flatMap((p) => p.items) ?? [], [q.data])
  // A selection never outlives the cards on screen: a changed filter drops the ticks it can no longer show.
  useEffect(() => {
    setPicked((prev) => {
      const visible = new Set(cards.map((c) => c.id))
      const next = new Set([...prev].filter((id) => visible.has(id)))
      return next.size === prev.size ? prev : next
    })
  }, [cards])

  const set = (patch: Partial<CardsSearch>) =>
    void navigate({ to: '/app/recall/cards', search: { ...search, ...patch }, replace: true })

  const act = (
    action: 'suspend' | 'delete' | 'set_importance',
    args?: { importance?: 'bullet' | 'important' | 'mandatory' },
  ) =>
    bulk.mutate(
      { ids: [...picked], action, args },
      {
        onSuccess: (r) => {
          setPicked(new Set())
          setConfirmDelete(false)
          toast.success(
            action === 'delete'
              ? `Deleted ${r.count} ${r.count === 1 ? 'card' : 'cards'}`
              : action === 'suspend'
                ? `Paused ${r.count} ${r.count === 1 ? 'card' : 'cards'}`
                : `Updated ${r.count} ${r.count === 1 ? 'card' : 'cards'}`,
          )
        },
        onError: (e) => toast.error(errorText(e, 'That did not work. Nothing was changed.')),
      },
    )

  const chips: Array<{ key: keyof CardsSearch; text: string }> = [
    search.kind ? { key: 'kind', text: KIND_LABELS[search.kind].label } : null,
    search.tier ? { key: 'tier', text: TIER_LABEL[search.tier] ?? search.tier } : null,
    search.state ? { key: 'state', text: STATE_LABEL[search.state] ?? search.state } : null,
    search.chapter ? { key: 'chapter', text: 'One chapter' } : null,
    search.deck ? { key: 'deck', text: 'One deck' } : null,
  ].filter((c): c is { key: keyof CardsSearch; text: string } => c !== null)

  const filtered = hasFilters(search)

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-3xl font-extrabold">Your cards</h1>
          <p className="text-muted-foreground">Find, fix and organise the cards you review.</p>
        </div>
        <ButtonLink asChild>
          <Link to="/app/recall/cards/new" search={{}}>
            Make a card
          </Link>
        </ButtonLink>
      </header>

      <section aria-label="Filters" className="space-y-3 rounded-2xl border border-border bg-card p-4">
        <Search value={search.q ?? ''} onCommit={(v) => set({ q: v.trim() || undefined })} />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SelectField
            aria-label="Kind"
            value={search.kind ?? ANY}
            onValueChange={(v) => set({ kind: (v || undefined) as CardsSearch['kind'] })}
            options={[
              { value: ANY, label: 'Any kind' },
              ...Object.entries(KIND_LABELS).map(([value, k]) => ({ value, label: k.label })),
            ]}
          />
          <SelectField
            aria-label="Importance"
            value={search.tier ?? ANY}
            onValueChange={(v) => set({ tier: (v || undefined) as CardsSearch['tier'] })}
            options={[
              { value: ANY, label: 'Any importance' },
              ...Object.entries(TIER_LABEL).map(([value, label]) => ({ value, label })),
            ]}
          />
          <SelectField
            aria-label="Status"
            value={search.state ?? ANY}
            onValueChange={(v) => set({ state: (v || undefined) as CardsSearch['state'] })}
            options={[
              { value: ANY, label: 'Any status' },
              ...CARD_STATES.map((value) => ({ value, label: STATE_LABEL[value] ?? value })),
            ]}
          />
          <SelectField
            aria-label="Order"
            value={search.sort ?? 'newest'}
            onValueChange={(v) => set({ sort: v === 'newest' ? undefined : (v as CardsSearch['sort']) })}
            options={Object.entries(SORT_LABEL).map(([value, label]) => ({ value, label }))}
          />
        </div>
        {chips.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2">
            {chips.map((c) => (
              <FilterChip
                key={c.key}
                removeLabel={`Remove filter: ${c.text}`}
                onRemove={() => set({ [c.key]: undefined })}
              >
                {c.text}
              </FilterChip>
            ))}
          </div>
        ) : null}
      </section>

      {picked.size > 0 ? (
        <section
          aria-label="Selected cards"
          className="sticky bottom-3 z-10 flex flex-wrap items-center gap-2 rounded-2xl border border-border bg-card p-3 shadow-soft"
        >
          <p className="mr-auto text-sm font-medium" role="status">
            {picked.size} selected
          </p>
          <Button variant="outline" disabled={bulk.isPending} onClick={() => act('suspend')}>
            Pause
          </Button>
          <Button
            variant="outline"
            disabled={bulk.isPending}
            onClick={() => act('set_importance', { importance: 'mandatory' })}
          >
            Mark as must know
          </Button>
          <Button variant="danger" disabled={bulk.isPending} onClick={() => setConfirmDelete(true)}>
            Delete
          </Button>
          <Button variant="ghost" onClick={() => setPicked(new Set())}>
            Clear
          </Button>
        </section>
      ) : null}

      {q.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <span className="sr-only" role="status">
            Loading your cards…
          </span>
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : q.isError ? (
        <LoadError what="your cards" onRetry={() => void q.refetch()} />
      ) : cards.length === 0 ? (
        filtered || search.q ? (
          <EmptyState
            icon={<Sparkles aria-hidden />}
            title="No cards match"
            description="Try fewer filters or a different word."
            action={
              <Button
                variant="outline"
                onClick={() => void navigate({ to: '/app/recall/cards', search: {}, replace: true })}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={<Sparkles aria-hidden />}
            title="You have no cards yet"
            description="Make one here, or highlight a line in your notes and choose Make a card."
            action={
              <ButtonLink asChild>
                <Link to="/app/recall/cards/new" search={{}}>
                  Make your first card
                </Link>
              </ButtonLink>
            }
          />
        )
      ) : (
        <>
          <ul className="space-y-3" aria-label="Cards">
            {cards.map((c) => (
              <CardRow
                key={c.id}
                card={c}
                selected={picked.has(c.id)}
                onSelect={(id, on) =>
                  setPicked((prev) => {
                    const next = new Set(prev)
                    if (on) next.add(id)
                    else next.delete(id)
                    return next
                  })
                }
              />
            ))}
          </ul>
          {q.hasNextPage ? (
            <Button
              variant="outline"
              className="w-full"
              disabled={q.isFetchingNextPage}
              onClick={() => void q.fetchNextPage()}
            >
              {q.isFetchingNextPage ? 'Loading…' : 'Show more cards'}
            </Button>
          ) : null}
          {q.isFetchNextPageError ? <Alert variant="error">We could not load more cards. Try again.</Alert> : null}
        </>
      )}

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogTitle>
            Delete {picked.size} {picked.size === 1 ? 'card' : 'cards'}?
          </DialogTitle>
          <DialogDescription>
            They stop appearing in your reviews. Your review history is kept. This cannot be undone from here.
          </DialogDescription>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
              Keep them
            </Button>
            <Button variant="danger" disabled={bulk.isPending} onClick={() => act('delete')}>
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export function CardsContainer({ search }: { search: CardsSearch }) {
  return (
    <RecallShell>
      <Cards search={search} />
    </RecallShell>
  )
}
