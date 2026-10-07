import { Alert, Button, EmptyState, Search, SegmentedControl, Skeleton } from '@artha/design-system'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { MarkResults, PdfResultGroups, PdfSearchNotices } from '../components/library/PdfSearchResults'
import { RecentSearches, SearchBox, SearchHitList } from '../components/SearchParts'
import { useDocumentDialogState } from '../hooks/useDocumentDialogState'
import { useDocumentTitles } from '../hooks/useLibrary'
import { flattenPages, useSearchNotes } from '../hooks/useNotesQueries'
import { useNotesSettings } from '../hooks/useNotesSettings'
import { notesAnalytics } from '../lib/analytics'
import { getDocument } from '../lib/documents-api'
import type { NoteSearchParams } from '../lib/filter-schema'
import { notesKeys } from '../lib/keys'
import { addRecent, clearRecent, loadRecent, saveRecent } from '../lib/recent-searches'
import { groupPdfHits, indexingText, isMarkHit, isPdfHit, notSearchable } from '../lib/search-groups'
import { normaliseQuery, queryLengthBucket, resultBucket } from '../lib/search-query'
import type { SearchHit } from '../lib/types'
import { DocumentDialogs } from './DocumentDialogs'
import { NotesShell } from './NotesShell'

const NOTE_SCOPES = [
  { value: 'all', label: 'Everything' },
  { value: 'notes', label: 'Notes' },
] as const
const PDF_SCOPES = [...NOTE_SCOPES, { value: 'pdf', label: 'PDFs' }] as const

function SearchScreen({ search }: { search: NoteSearchParams }) {
  const navigate = useNavigate()
  const q = normaliseQuery(search.q ?? '')
  const pdfOn = useFeatureFlag('notes_pdf')
  const scope = search.scope === 'notes' ? 'notes' : search.scope === 'pdf' && pdfOn ? 'pdf' : 'all'
  const queryClient = useQueryClient()
  const dialogs = useDocumentDialogState()
  const [busyId, setBusyId] = useState<string | null>(null)
  const settings = useNotesSettings(pdfOn)
  const titles = useDocumentTitles(pdfOn)
  const [text, setText] = useState(search.q ?? '')
  const [recent, setRecent] = useState<string[]>([])
  useEffect(() => setRecent(loadRecent()), [])
  useEffect(() => setText(search.q ?? ''), [search.q])

  const results = useSearchNotes({ q, scope, subject: search.subject, chapter: search.chapter })
  const { items, offline } = flattenPages(results.data?.pages)
  const meta = results.data?.pages.at(-1)?.meta ?? results.data?.pages[0]?.meta
  const noteHits = items.filter((hit): hit is SearchHit => hit.type === 'note')
  const markHits = items.filter(isMarkHit)
  const pdfGroups = groupPdfHits(items.filter(isPdfHit))
  const unsearchable = notSearchable(meta)
  const makeSearchable = async (documentId: string) => {
    setBusyId(documentId)
    try {
      const doc = await queryClient.fetchQuery({
        queryKey: notesKeys.document(documentId),
        queryFn: () => getDocument(documentId),
        staleTime: 60_000,
      })
      dialogs.openOcr(doc)
    } finally {
      setBusyId(null)
    }
  }

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

  const opened = () =>
    notesAnalytics.searchResultOpened({
      scope,
      queryLength: queryLengthBucket(q),
      results: resultBucket(items.length),
    })

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
        options={pdfOn ? PDF_SCOPES : NOTE_SCOPES}
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
      ) : scope === 'pdf' && offline ? (
        <Alert variant="info">
          <span role="status">You are offline. PDF text is searched online only, so connect to search your PDFs.</span>
        </Alert>
      ) : items.length === 0 ? (
        <div className="space-y-3">
          <EmptyState
            icon={<Search aria-hidden />}
            title={scope === 'pdf' ? 'No PDF pages match' : 'No notes match'}
            description="Try fewer or different words, or a section number such as 17(5)."
          />
          {pdfOn ? (
            <PdfSearchNotices
              indexing={indexingText(meta)}
              notSearchable={unsearchable}
              titles={titles}
              documents={meta?.not_searchable ?? []}
              onMakeSearchable={(id) => void makeSearchable(id)}
              busyId={busyId}
            />
          ) : null}
        </div>
      ) : (
        <div className="space-y-3">
          {offline ? (
            <Alert variant="info">
              <span>You are offline. Searching the notes kept on this device. PDFs need a connection.</span>
            </Alert>
          ) : null}
          <p role="status" className="text-sm text-muted-foreground">
            {items.length}
            {results.hasNextPage ? '+' : ''} result{items.length === 1 && !results.hasNextPage ? '' : 's'} for &ldquo;
            {q}&rdquo;
          </p>
          {pdfOn ? (
            <PdfSearchNotices
              indexing={indexingText(meta)}
              notSearchable={unsearchable}
              titles={titles}
              documents={meta?.not_searchable ?? []}
              onMakeSearchable={(id) => void makeSearchable(id)}
              busyId={busyId}
            />
          ) : null}
          {noteHits.length > 0 ? <SearchHitList hits={noteHits} query={q} onOpen={opened} /> : null}
          {markHits.length > 0 ? (
            <MarkResults hits={markHits} query={q} legend={settings.data?.color_legend} onOpen={opened} />
          ) : null}
          {pdfGroups.length > 0 ? <PdfResultGroups groups={pdfGroups} query={q} onOpen={opened} /> : null}
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
      <DocumentDialogs controller={dialogs} showLibraryLink />
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
