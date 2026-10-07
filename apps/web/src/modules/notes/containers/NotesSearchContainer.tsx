import { Alert, Button, EmptyState, Search, SegmentedControl, Skeleton } from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { RecentSearches, SearchBox, SearchHitList } from '../components/SearchParts'
import { flattenPages, useSearchNotes } from '../hooks/useNotesQueries'
import { notesAnalytics } from '../lib/analytics'
import type { NoteSearchParams } from '../lib/filter-schema'
import { addRecent, clearRecent, loadRecent, saveRecent } from '../lib/recent-searches'
import { normaliseQuery, queryLengthBucket, resultBucket } from '../lib/search-query'
import { NotesShell } from './NotesShell'

const SCOPES = [
  { value: 'all', label: 'Everything' },
  { value: 'notes', label: 'Notes' },
] as const

function SearchScreen({ search }: { search: NoteSearchParams }) {
  const navigate = useNavigate()
  const q = normaliseQuery(search.q ?? '')
  const scope = search.scope === 'notes' ? 'notes' : 'all'
  const [text, setText] = useState(search.q ?? '')
  const [recent, setRecent] = useState<string[]>([])
  useEffect(() => setRecent(loadRecent()), [])
  useEffect(() => setText(search.q ?? ''), [search.q])

  const results = useSearchNotes({ q, scope, subject: search.subject, chapter: search.chapter })
  const { items, offline } = flattenPages(results.data?.pages)

  const go = (next: Partial<NoteSearchParams>) =>
    void navigate({ to: '/app/notes/search', search: { ...search, ...next }, replace: false })

  const submit = (query: string) => {
    const normalised = normaliseQuery(query)
    if (!normalised) return
    const next = addRecent(loadRecent(), normalised)
    saveRecent(next)
    setRecent(next)
    go({ q: normalised })
  }

  const reported = useRef('')
  useEffect(() => {
    if (!results.data || !q) return
    const key = `${q}|${scope}`
    if (reported.current === key) return
    reported.current = key
    notesAnalytics.searchPerformed({
      scope,
      queryLength: queryLengthBucket(q),
      results: resultBucket(items.length),
    })
  }, [results.data, q, scope, items.length])

  return (
    <>
      <header className="space-y-1">
        <h1 className="font-display text-3xl font-extrabold">Search notes</h1>
        <p className="text-muted-foreground">Section numbers work too, like 17(5) or 80C.</p>
      </header>
      <SearchBox value={text} onChange={setText} onSubmit={() => submit(text)} busy={results.isFetching && !!q} />
      <SegmentedControl
        label="Where to search"
        value={scope}
        options={SCOPES}
        onValueChange={(value) => go({ scope: value })}
      />

      {!q ? (
        <RecentSearches
          items={recent}
          onPick={(query) => {
            setText(query)
            submit(query)
          }}
          onClear={() => {
            clearRecent()
            setRecent([])
          }}
        />
      ) : results.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <span role="status" className="sr-only">
            Searching…
          </span>
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : results.isError && items.length === 0 ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            <span>The search did not work. Please try again.</span>
            <Button size="sm" variant="outline" onClick={() => void results.refetch()}>
              Try again
            </Button>
          </span>
        </Alert>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Search aria-hidden />}
          title="No notes match"
          description="Try fewer or different words, or a section number such as 17(5)."
        />
      ) : (
        <div className="space-y-3">
          {offline ? (
            <Alert variant="info">
              <span>You are offline. Searching the notes kept on this device.</span>
            </Alert>
          ) : null}
          <p role="status" className="text-sm text-muted-foreground">
            {items.length}
            {results.hasNextPage ? '+' : ''} result{items.length === 1 && !results.hasNextPage ? '' : 's'} for &ldquo;
            {q}&rdquo;
          </p>
          <SearchHitList
            hits={items}
            query={q}
            onOpen={() =>
              notesAnalytics.searchResultOpened({
                scope,
                queryLength: queryLengthBucket(q),
                results: resultBucket(items.length),
              })
            }
          />
          {results.hasNextPage ? (
            <Button
              variant="outline"
              disabled={results.isFetchingNextPage}
              onClick={() => void results.fetchNextPage()}
            >
              {results.isFetchingNextPage ? 'Loading…' : 'Load more'}
            </Button>
          ) : null}
        </div>
      )}
    </>
  )
}

export function NotesSearchContainer({ search }: { search: NoteSearchParams }) {
  return (
    <NotesShell width="max-w-3xl">
      <SearchScreen search={search} />
    </NotesShell>
  )
}
