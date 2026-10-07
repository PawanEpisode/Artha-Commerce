import { Alert, Button, EmptyState, Inbox, Notebook, Plus, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'

import { NotesList } from '../components/NotesList'
import { SubjectGrid, type SubjectTile } from '../components/SubjectGrid'
import { useNoteActions } from '../hooks/useNoteActions'
import { flattenPages, useAllSubjectCounts, useEnrolledSubjects, useNoteList } from '../hooks/useNotesQueries'
import { notesAnalytics } from '../lib/analytics'
import { pluralize } from '../lib/format'
import type { SubjectCounts } from '../lib/types'
import { NotesShell } from './NotesShell'
import { UnfiledRow } from './UnfiledRow'

const totalOf = (c: SubjectCounts) =>
  c.chapters.reduce((n, r) => n + r.notes, 0) + c.moved_or_removed.reduce((n, r) => n + r.notes, 0)

function Hub() {
  const actions = useNoteActions()
  const { subjects, isPending: subjectsPending, isError: subjectsError, noEnrollment, refetch } = useEnrolledSubjects()
  const counts = useAllSubjectCounts(subjects.map((s) => s.key))
  const pinned = useNoteList({ pinned: true, limit: 10 })
  const unfiled = useNoteList({ unfiled: true, limit: 30 })
  const recent = useNoteList({ limit: 8 })

  const pinnedList = flattenPages(pinned.data?.pages)
  const unfiledList = flattenPages(unfiled.data?.pages)
  const recentList = flattenPages(recent.data?.pages)

  const reported = useRef(false)
  useEffect(() => {
    if (reported.current || recent.isPending || unfiled.isPending) return
    reported.current = true
    notesAnalytics.hubViewed({
      unfiled: unfiledList.items.length,
      notes: recentList.items.length,
    })
  }, [recent.isPending, unfiled.isPending, unfiledList.items.length, recentList.items.length])

  const tiles: SubjectTile[] = subjects.map((s, i) => {
    const q = counts[i]
    return q?.isError
      ? { key: s.key, name: s.name, state: 'error' }
      : q?.data
        ? { key: s.key, name: s.name, notes: totalOf(q.data), state: 'ok' }
        : { key: s.key, name: s.name, state: 'loading' }
  })

  const onPin = (note: Parameters<typeof actions.pin>[0], on: boolean) => void actions.pin(note, on)
  const onTrash = (note: Parameters<typeof actions.trash>[0]) => void actions.trash(note)

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-extrabold">Notes</h1>
          <p className="text-muted-foreground">Write once, find it by subject and chapter.</p>
        </div>
        <Button variant="cta" asChild>
          <Link to="/app/notes/new">
            <Plus aria-hidden /> New note
          </Link>
        </Button>
      </header>

      {pinnedList.items.length > 0 ? (
        <section aria-labelledby="pinned-h" className="space-y-3">
          <h2 id="pinned-h" className="font-display text-xl font-bold">
            Pinned
          </h2>
          <NotesList
            label="pinned notes"
            items={pinnedList.items}
            isPending={false}
            isError={false}
            onRetry={() => void pinned.refetch()}
            empty={null}
            onPin={onPin}
            onTrash={onTrash}
          />
        </section>
      ) : null}

      <section aria-labelledby="subjects-h" className="space-y-3">
        <h2 id="subjects-h" className="font-display text-xl font-bold">
          By subject
        </h2>
        {subjectsPending ? (
          <Skeleton className="h-24 w-full" />
        ) : noEnrollment ? (
          <EmptyState
            icon={<Notebook aria-hidden />}
            title="Choose your course first"
            description="Pick your course and level so your notes can follow your syllabus."
            action={
              <Button asChild>
                <Link to="/app/onboarding">Choose my course</Link>
              </Button>
            }
          />
        ) : subjectsError ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              <span>We could not load your subjects.</span>
              <Button size="sm" variant="outline" onClick={() => void refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          <SubjectGrid subjects={tiles} />
        )}
      </section>

      {unfiledList.items.length > 0 || unfiled.isError ? (
        <section aria-labelledby="unfiled-h" className="space-y-3">
          <h2 id="unfiled-h" className="flex items-center gap-2 font-display text-xl font-bold">
            <Inbox aria-hidden className="size-5" /> Unfiled
            <span className="text-base font-medium text-muted-foreground">
              ({pluralize(unfiledList.items.length, 'note')}
              {unfiled.hasNextPage ? ' or more' : ''})
            </span>
          </h2>
          <p className="text-sm text-muted-foreground">Tap a suggestion to file a note under its chapter.</p>
          <NotesList
            label="unfiled notes"
            items={unfiledList.items}
            isPending={unfiled.isPending}
            isError={unfiled.isError}
            onRetry={() => void unfiled.refetch()}
            empty={null}
            offline={unfiledList.offline}
            hasMore={unfiled.hasNextPage}
            loadingMore={unfiled.isFetchingNextPage}
            onLoadMore={() => void unfiled.fetchNextPage()}
            onPin={onPin}
            onTrash={onTrash}
            renderExtra={(note) => <UnfiledRow note={note} />}
          />
        </section>
      ) : null}

      <section aria-labelledby="recent-h" className="space-y-3">
        <h2 id="recent-h" className="font-display text-xl font-bold">
          Recent
        </h2>
        <NotesList
          label="recent notes"
          items={recentList.items}
          isPending={recent.isPending}
          isError={recent.isError}
          onRetry={() => void recent.refetch()}
          offline={recentList.offline}
          onPin={onPin}
          onTrash={onTrash}
          empty={
            <EmptyState
              icon={<Notebook aria-hidden />}
              title="Write your first note"
              description="Capture a formula, a doubt or a summary. It saves as you type, even offline."
              action={
                <Button variant="cta" asChild>
                  <Link to="/app/notes/new">
                    <Plus aria-hidden /> New note
                  </Link>
                </Button>
              }
            />
          }
        />
      </section>
    </>
  )
}

export function NotesHubContainer() {
  return (
    <NotesShell>
      <Hub />
    </NotesShell>
  )
}
