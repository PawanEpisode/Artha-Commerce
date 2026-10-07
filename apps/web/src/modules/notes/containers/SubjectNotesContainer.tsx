import {
  Alert,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
  Button,
  Skeleton,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { ChapterRows } from '../components/ChapterRows'
import { useEnrolledSubjects, useLevelId, useSubjectCounts } from '../hooks/useNotesQueries'
import { useRelink } from '../hooks/useRelink'
import { linkFromSelection } from '../lib/chapter-link'
import type { NoteFilterSearch } from '../lib/filter-schema'
import type { MovedChapterRow } from '../lib/types'
import { AggregateSection, NewNoteLink } from './AggregateSection'
import { ChapterPicker } from './ChapterPicker'
import { NotesShell } from './NotesShell'

function SubjectNotes({ subject, search }: { subject: string; search: NoteFilterSearch }) {
  const navigate = useNavigate()
  const levelId = useLevelId()
  const { subjects } = useEnrolledSubjects()
  const counts = useSubjectCounts(subject)
  const relinker = useRelink()
  const [moving, setMoving] = useState<MovedChapterRow | null>(null)
  const name = subjects.find((s) => s.key === subject)?.name ?? subject

  return (
    <>
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <Link to="/app/notes" className="underline-offset-4 hover:underline">
              Notes
            </Link>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-3xl font-extrabold break-words">{name}</h1>
        <NewNoteLink levelId={levelId} subject={subject} />
      </header>

      <section aria-labelledby="chapters-h" className="space-y-3">
        <h2 id="chapters-h" className="font-display text-xl font-bold">
          Chapters
        </h2>
        {counts.isPending ? (
          <div aria-busy="true" className="space-y-2">
            <span role="status" className="sr-only">
              Loading chapters…
            </span>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : counts.isError || !counts.data ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              <span>We could not load the chapters of this subject.</span>
              <Button size="sm" variant="outline" onClick={() => void counts.refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          <ChapterRows
            subjectKey={subject}
            chapters={counts.data.chapters}
            moved={counts.data.moved_or_removed}
            onRelink={setMoving}
          />
        )}
      </section>

      <section aria-labelledby="all-notes-h" className="space-y-3">
        <h2 id="all-notes-h" className="font-display text-xl font-bold">
          All notes in {name}
        </h2>
        <AggregateSection
          levelId={levelId}
          subject={subject}
          search={search}
          kind="subject"
          onSearchChange={(next) =>
            void navigate({ to: '/app/notes/$subject', params: { subject }, search: next, replace: true })
          }
          newNote={<NewNoteLink levelId={levelId} subject={subject} />}
        />
      </section>

      {moving ? (
        <ChapterPicker
          link={linkFromSelection(null)}
          showTrigger={false}
          open
          onOpenChange={(open) => !open && setMoving(null)}
          disabled={relinker.busy}
          onSelect={async (selection) => {
            const row = moving
            setMoving(null)
            if (selection && levelId) await relinker.relink(levelId, subject, row.chapter_key, selection)
          }}
        />
      ) : null}
    </>
  )
}

export function SubjectNotesContainer({ subject, search }: { subject: string; search: NoteFilterSearch }) {
  return (
    <NotesShell>
      <SubjectNotes subject={subject} search={search} />
    </NotesShell>
  )
}
