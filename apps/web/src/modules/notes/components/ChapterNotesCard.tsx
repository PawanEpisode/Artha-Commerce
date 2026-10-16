import { Alert, Button, Card, FileText, Notebook, Plus, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { formatDate, pluralize } from '../lib/format'
import { markOpenedFrom } from '../lib/opened-from'
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
    <section aria-labelledby="chapter-notes-h" className="space-y-2">
      <h2 id="chapter-notes-h" className="flex items-center gap-2 text-sm font-semibold">
        <Notebook aria-hidden className="size-4" /> Notes
      </h2>
      {state === 'loading' ? (
        <Skeleton className="h-24 w-full" />
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
        <Card className="space-y-2 p-4">
          <p>
            {overview.counts.notes === 0
              ? 'You have no notes in this chapter yet.'
              : `${pluralize(overview.counts.notes, 'note')} in this chapter${
                  overview.last_noted_at ? `, the latest on ${formatDate(overview.last_noted_at)}` : ''
                }.`}
          </p>
          <p className="text-xs text-muted-foreground">
            {overview.has_summary ? 'Exam summary: ready.' : 'Exam summary: not written yet.'}
          </p>
          {overview.recent.length > 0 ? (
            <ul aria-label="Latest notes" className="space-y-1">
              {overview.recent.slice(0, 3).map((n) => (
                <li key={n.id}>
                  <Link
                    to="/app/notes/n/$noteId"
                    params={{ noteId: n.id }}
                    className="inline-flex min-h-7 items-center font-medium underline-offset-4 hover:underline"
                  >
                    {n.title.trim() || 'Untitled note'}
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
          {overview.documents.length > 0 ? (
            <div className="space-y-1">
              <h3 className="flex items-center gap-2 text-[13px] font-semibold">
                <FileText aria-hidden className="size-3.5" /> {pluralize(overview.counts.documents, 'PDF')} linked here
              </h3>
              <ul aria-label="Linked PDFs" className="space-y-1">
                {overview.documents.slice(0, 3).map((d) => (
                  <li key={d.id}>
                    <Link
                      to="/app/notes/pdf/$docId"
                      params={{ docId: d.id }}
                      onClick={() => markOpenedFrom('chapter')}
                      className="inline-flex min-h-7 items-center font-medium break-words underline-offset-4 hover:underline"
                    >
                      {d.title.trim() || 'Untitled PDF'}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to="/app/notes/$subject/$chapter" params={{ subject: subjectKey, chapter: chapterKey }}>
                Open notes
              </Link>
            </Button>
            <Button size="sm" asChild>
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
