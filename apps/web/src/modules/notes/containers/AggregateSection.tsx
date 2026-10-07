import { Button, EmptyState, FileText, Notebook } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { type ReactNode, useEffect, useRef } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { FilterBar } from '../components/FilterBar'
import { DocumentCard } from '../components/library/DocumentCard'
import { HighlightRow } from '../components/library/HighlightRow'
import { NotesList } from '../components/NotesList'
import { useDocumentTitles } from '../hooks/useLibrary'
import { useNoteActions } from '../hooks/useNoteActions'
import { flattenPages, useAggregateList, useTags } from '../hooks/useNotesQueries'
import { useNotesSettings } from '../hooks/useNotesSettings'
import { notesAnalytics } from '../lib/analytics'
import type { DocumentSummary } from '../lib/document-types'
import {
  activeFilters,
  aggregateParams,
  type NoteFilterSearch,
  strongestFilter,
  tabOf,
  withoutFilter,
} from '../lib/filter-schema'

interface AggregateSectionProps {
  levelId: string | undefined
  subject: string
  chapter?: string
  search: NoteFilterSearch
  onSearchChange: (next: NoteFilterSearch) => void
  topics?: ReadonlyArray<{ key: string; name: string }>
  /** What an empty list offers: a "New note" link filed under this subject or chapter. */
  newNote: ReactNode
  kind: 'subject' | 'chapter'
}

/** The filtered list shared by the subject and chapter pages: filters in the URL, notes below, all four states. */
export function AggregateSection({
  levelId,
  subject,
  chapter,
  search,
  onSearchChange,
  topics,
  newNote,
  kind,
}: AggregateSectionProps) {
  const actions = useNoteActions()
  const tags = useTags()
  const pdfOn = useFeatureFlag('notes_pdf')
  const settings = useNotesSettings(pdfOn)
  const titles = useDocumentTitles(pdfOn)
  const tab = tabOf(search)
  const params = aggregateParams({ level: levelId ?? '', subject, chapter }, search)
  const list = useAggregateList(params, levelId !== undefined)
  const { items, offline } = flattenPages(list.data?.pages)

  const seen = useRef('')
  useEffect(() => {
    if (!list.data) return
    const signature = JSON.stringify({ ...params, cursor: undefined })
    if (seen.current === signature) return
    seen.current = signature
    const event = { tab: tabOf(search), filters: activeFilters(search).length, items: items.length }
    if (kind === 'chapter') notesAnalytics.chapterNotesSeen(event)
    else notesAnalytics.aggregateViewed(event)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list.data])

  const strongest = strongestFilter(search)
  const documents = [...titles].map(([id, title]) => ({ id, title }))
  const legend = pdfOn ? settings.data?.color_legend : undefined

  return (
    <div className="space-y-4">
      <FilterBar
        search={search}
        tags={tags.data ?? []}
        topics={topics}
        legend={legend}
        documents={documents}
        onChange={onSearchChange}
      />
      <NotesList
        label={tab === 'highlights' ? 'highlights' : tab === 'documents' ? 'documents' : 'notes'}
        items={items}
        isPending={list.isPending && levelId !== undefined}
        isError={list.isError}
        onRetry={() => void list.refetch()}
        offline={offline}
        showLocation={kind === 'subject'}
        hasMore={list.hasNextPage}
        loadingMore={list.isFetchingNextPage}
        onLoadMore={() => void list.fetchNextPage()}
        onPin={(note, on) => void actions.pin(note, on)}
        onTrash={(note) => void actions.trash(note)}
        renderOther={(row) =>
          row.type === 'highlight' ? (
            <HighlightRow
              row={row}
              colorName={row.color && legend ? legend[row.color as keyof typeof legend] : undefined}
              documentTitle={titles.get(row.document_id)}
              showLocation={kind === 'subject'}
            />
          ) : (
            <DocumentCard doc={row satisfies DocumentSummary} compact showLocation={kind === 'subject'} />
          )
        }
        empty={
          strongest ? (
            <EmptyState
              icon={<Notebook aria-hidden />}
              title="No notes match these filters"
              description="Try removing a filter to see more."
              action={
                <Button variant="outline" onClick={() => onSearchChange(withoutFilter(search, strongest))}>
                  Remove the {strongest === 'from' || strongest === 'to' ? 'date' : strongest} filter
                </Button>
              }
            />
          ) : tab === 'highlights' || tab === 'documents' ? (
            <EmptyState
              icon={<FileText aria-hidden />}
              title={tab === 'highlights' ? 'No highlights here yet' : 'No documents here yet'}
              description="Link your PDFs to chapters to see highlights here."
              action={
                <Button variant="outline" asChild>
                  <Link to="/app/notes/library">Open the library</Link>
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={<Notebook aria-hidden />}
              title={kind === 'chapter' ? 'No notes in this chapter yet' : 'No notes in this subject yet'}
              description="Write one now, or file an unfiled note here."
              action={newNote}
            />
          )
        }
      />
    </div>
  )
}

export function NewNoteLink({
  levelId,
  subject,
  chapter,
  topic,
}: {
  levelId?: string
  subject: string
  chapter?: string
  topic?: string
}) {
  return (
    <Button variant="cta" asChild>
      <Link to="/app/notes/new" search={{ level: levelId, subject, chapter, topic }}>
        New note
      </Link>
    </Button>
  )
}
