import { Alert, Button, Card, Notebook, Plus, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { formatDate, pluralize } from '../lib/format'
import type { ChapterOverview } from '../lib/types'

interface ChapterNotesCardProps {
  state: 'loading' | 'error' | 'ready'
  overview?: ChapterOverview
  subjectKey: string
  chapterKey: string
  levelId?: string
  onRetry: () => void
}

/**
 * The notes section of a chapter page: how many notes the chapter has, the exam summary status, the latest notes, and
 * the two actions (open them all, write a new one already filed under this chapter).
 */
export function ChapterNotesCard({ state, overview, subjectKey, chapterKey, levelId, onRetry }: ChapterNotesCardProps) {
  return (
    <section aria-labelledby="chapter-notes-h" className="space-y-3">
      <h2 id="chapter-notes-h" className="flex items-center gap-2.5 font-display text-xl font-bold">
        <Notebook aria-hidden className="size-5" /> Notes
      </h2>
      {state === 'loading' ? (
        <Skeleton className="h-28 w-full" />
      ) : state === 'error' || !overview ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            <span>We could not load your notes for this chapter.</span>
            <Button size="sm" variant="outline" onClick={onRetry}>
              Try again
            </Button>
          </span>
        </Alert>
      ) : (
        <Card className="space-y-4 p-6">
          <p className="text-base">
            {overview.counts.notes === 0
              ? 'You have no notes in this chapter yet.'
              : `${pluralize(overview.counts.notes, 'note')} in this chapter${
                  overview.last_noted_at ? `, the latest on ${formatDate(overview.last_noted_at)}` : ''
                }.`}
          </p>
          <p className="text-sm text-muted-foreground">
            {overview.has_summary ? 'Exam summary: ready.' : 'Exam summary: not written yet.'}
          </p>
          {overview.recent.length > 0 ? (
            <ul aria-label="Latest notes" className="space-y-1">
              {overview.recent.slice(0, 3).map((n) => (
                <li key={n.id}>
                  <Link
                    to="/app/notes/n/$noteId"
                    params={{ noteId: n.id }}
                    className="inline-flex min-h-11 items-center font-medium underline-offset-4 hover:underline"
                  >
                    {n.title.trim() || 'Untitled note'}
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" asChild>
              <Link to="/app/notes/$subject/$chapter" params={{ subject: subjectKey, chapter: chapterKey }}>
                Open notes
              </Link>
            </Button>
            <Button asChild>
              <Link to="/app/notes/new" search={{ level: levelId, subject: subjectKey, chapter: chapterKey }}>
                <Plus aria-hidden /> New note
              </Link>
            </Button>
          </div>
        </Card>
      )}
    </section>
  )
}
