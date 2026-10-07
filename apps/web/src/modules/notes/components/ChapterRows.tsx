import { Alert, Badge, Button, Card, ChevronRight } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { formatDate, pluralize } from '../lib/format'
import type { ChapterCountsRow, MovedChapterRow } from '../lib/types'

interface ChapterRowsProps {
  subjectKey: string
  chapters: readonly ChapterCountsRow[]
  moved: readonly MovedChapterRow[]
  /** Re-file the notes of a chapter that is no longer in the syllabus. */
  onRelink: (row: MovedChapterRow) => void
}

/** The chapters of a subject in syllabus order with their note counts, then the chapters that moved or were removed. */
export function ChapterRows({ subjectKey, chapters, moved, onRelink }: ChapterRowsProps) {
  return (
    <div className="space-y-6">
      <ul aria-label="Chapters" className="space-y-2">
        {chapters.map((c) => (
          <li key={c.chapter_id}>
            <Card className="relative flex min-h-16 items-center gap-3 px-4 py-3 focus-within:ring-[3px] focus-within:ring-ring/40 hover:bg-muted/50">
              <div className="min-w-0 flex-1">
                <h3 className="text-base leading-snug font-semibold break-words">
                  <Link
                    to="/app/notes/$subject/$chapter"
                    params={{ subject: subjectKey, chapter: c.chapter_key }}
                    className="outline-none after:absolute after:inset-0 after:content-['']"
                  >
                    {c.name}
                  </Link>
                </h3>
                <p className="text-sm text-muted-foreground">
                  {c.notes === 0 ? 'No notes yet' : pluralize(c.notes, 'note')}
                  {c.last_noted_at ? `, last on ${formatDate(c.last_noted_at)}` : ''}
                </p>
              </div>
              {c.has_summary ? <Badge variant="accent">Has summary</Badge> : null}
              <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
            </Card>
          </li>
        ))}
      </ul>
      {moved.length > 0 ? (
        <section aria-labelledby="moved-h" className="space-y-3">
          <h2 id="moved-h" className="font-display text-xl font-bold">
            Moved or removed
          </h2>
          <Alert variant="info">
            These chapters are not in your current syllabus any more. Your notes are safe: re-file them under a chapter
            that exists now.
          </Alert>
          <ul className="space-y-2">
            {moved.map((m) => (
              <li key={m.chapter_key}>
                <Card className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold break-words">{m.chapter_name}</p>
                    <p className="text-sm text-muted-foreground">{pluralize(m.notes, 'note')}</p>
                  </div>
                  <Button variant="outline" onClick={() => onRelink(m)}>
                    Re-link
                  </Button>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}
