import { Container, Skeleton } from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'

import { useChapterCoverage } from '~/modules/coverage'
import { useOnline } from '~/modules/personalization'

import { useChapterNotesOverview } from '../hooks/useNotesQueries'
import { useStartNote } from '../hooks/useStartNote'
import { selectionFromOverview } from '../lib/chapter-link'
import type { NewNoteSearch } from '../lib/filter-schema'
import { NotesShell } from './NotesShell'

/**
 * `/app/notes/new` is only a doorway (old links, the marketing and chapter buttons): it makes the note on this device
 * and replaces itself with `/app/notes/n/<id>` at once. The only wait is the chapter lookup of a `?chapter=` link, and
 * only while online; offline (or when the lookup fails) the note simply starts unfiled and can be filed later.
 */
function NewNoteRedirect({ search }: { search: NewNoteSearch }) {
  const navigate = useNavigate()
  const online = useOnline()
  const start = useStartNote()
  const started = useRef(false)
  const wants = Boolean(search.subject && search.chapter) && online
  const overview = useChapterNotesOverview(search.subject ?? '', search.chapter ?? '', wants)
  const chapter = useChapterCoverage(overview.data?.chapter.id ?? '')
  const topic = search.topic ? chapter.data?.topics.find((t) => t.key === search.topic) : undefined
  const waiting =
    wants &&
    !overview.isError &&
    (overview.isPending || (Boolean(search.topic) && chapter.isPending && overview.isSuccess))
  const selection = overview.data ? selectionFromOverview(overview.data, topic) : null

  useEffect(() => {
    if (waiting || started.current) return
    started.current = true
    void start({ selection, recoverLegacyDraft: !search.chapter }).then((noteId) =>
      navigate({ to: '/app/notes/n/$noteId', params: { noteId }, search: {}, replace: true }),
    )
  }, [waiting, selection, search.chapter, start, navigate])

  return (
    <Container className="max-w-5xl py-10">
      <div aria-busy="true" className="space-y-4">
        <span role="status" className="sr-only">
          Opening a new note…
        </span>
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    </Container>
  )
}

export function NewNoteContainer({ search }: { search: NewNoteSearch }) {
  return (
    <NotesShell bare>
      <NewNoteRedirect search={search} />
    </NotesShell>
  )
}
