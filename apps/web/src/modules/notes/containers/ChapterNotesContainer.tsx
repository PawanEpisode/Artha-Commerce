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

import { useChapterCoverage } from '~/modules/coverage'

import { SummaryOffer } from '../components/ai/SummaryOffer'
import { useAiAvailable, useChapterSummary } from '../hooks/useAi'
import { useChapterNotesOverview, useEnrolledSubjects, useLevelId } from '../hooks/useNotesQueries'
import { isNotFound } from '../lib/errors'
import type { NoteFilterSearch } from '../lib/filter-schema'
import { AggregateSection, NewNoteLink } from './AggregateSection'
import { NotesShell } from './NotesShell'

function ChapterNotes({ subject, chapter, search }: { subject: string; chapter: string; search: NoteFilterSearch }) {
  const navigate = useNavigate()
  const levelId = useLevelId()
  const { subjects } = useEnrolledSubjects()
  const overview = useChapterNotesOverview(subject, chapter)
  const topics = useChapterCoverage(overview.data?.chapter.id ?? '')
  const ai = useAiAvailable()
  const chapterId = overview.data?.chapter.id
  const summary = useChapterSummary(chapterId, ai.available)
  const subjectName = overview.data?.chapter.subject_name ?? subjects.find((s) => s.key === subject)?.name ?? subject

  if (overview.isPending && levelId !== undefined) return <Skeleton className="h-40 w-full" />
  if (overview.isError) {
    return (
      <Alert variant="error">
        <span className="flex flex-wrap items-center gap-3">
          <span>
            {isNotFound(overview.error)
              ? 'This chapter is not in your current syllabus. Your notes are kept under "Moved or removed" on the subject page.'
              : 'We could not load this chapter.'}
          </span>
          {isNotFound(overview.error) ? (
            <Button size="sm" variant="outline" asChild>
              <Link to="/app/notes/$subject" params={{ subject }}>
                Back to {subjectName}
              </Link>
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={() => void overview.refetch()}>
              Try again
            </Button>
          )}
        </span>
      </Alert>
    )
  }
  const name = overview.data?.chapter.name ?? chapter

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
            <Link to="/app/notes/$subject" params={{ subject }} className="underline-offset-4 hover:underline">
              {subjectName}
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
        <NewNoteLink levelId={levelId} subject={subject} chapter={chapter} topic={search.topic} />
      </header>
      {ai.available && chapterId ? <SummaryOffer chapterId={chapterId} job={summary.data} /> : null}
      <AggregateSection
        levelId={levelId}
        subject={subject}
        chapter={chapter}
        search={search}
        kind="chapter"
        topics={topics.data?.topics.map((t) => ({ key: t.key, name: t.name }))}
        onSearchChange={(next) =>
          void navigate({
            to: '/app/notes/$subject/$chapter',
            params: { subject, chapter },
            search: next,
            replace: true,
          })
        }
        newNote={<NewNoteLink levelId={levelId} subject={subject} chapter={chapter} topic={search.topic} />}
      />
    </>
  )
}

export function ChapterNotesContainer({
  subject,
  chapter,
  search,
}: {
  subject: string
  chapter: string
  search: NoteFilterSearch
}) {
  return (
    <NotesShell>
      <ChapterNotes subject={subject} chapter={chapter} search={search} />
    </NotesShell>
  )
}
