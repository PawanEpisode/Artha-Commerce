import { Button, EmptyState, Notebook } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { type ReactNode, useEffect, useRef } from 'react'

import { FilterBar } from '../components/FilterBar'
import { NotesList } from '../components/NotesList'
import { useNoteActions } from '../hooks/useNoteActions'
import { flattenPages, useAggregateList, useTags } from '../hooks/useNotesQueries'
import { notesAnalytics } from '../lib/analytics'
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

  return (
    <div className="space-y-4">
      <FilterBar search={search} tags={tags.data ?? []} topics={topics} onChange={onSearchChange} />
      <NotesList
        label="notes"
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
