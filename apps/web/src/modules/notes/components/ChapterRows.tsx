import {
  Alert,
  Badge,
  Button,
  DataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { formatDate, pluralize } from '../lib/format'
import type { ChapterCountsRow, MovedChapterRow } from '../lib/types'

/** "3 notes, 12 highlights, 1 PDF": only what exists; marks that are not highlights (sticky notes, drawings) count as marks. */
function countsText(c: { notes: number; highlights: number; marks: number; documents: number }) {
  const parts = [
    c.notes > 0 ? pluralize(c.notes, 'note') : '',
    c.highlights > 0 ? pluralize(c.highlights, 'highlight') : '',
    c.marks > 0 ? pluralize(c.marks, 'mark') : '',
    c.documents > 0 ? pluralize(c.documents, 'PDF') : '',
  ].filter(Boolean)
  return parts.length > 0 ? parts.join(', ') : null
}

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
    <div className="space-y-4">
      <DataTable aria-label="Chapters">
        <TableHeader>
          <TableRow>
            <TableHead>Chapter</TableHead>
            <TableHead>Filed here</TableHead>
            <TableHead className="text-right">Last note</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {chapters.map((c) => (
            <TableRow key={c.chapter_id}>
              <TableCell className="min-w-48 whitespace-normal">
                <Link
                  to="/app/notes/$subject/$chapter"
                  params={{ subject: subjectKey, chapter: c.chapter_key }}
                  className="font-medium break-words underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  {c.name}
                </Link>
                {c.has_summary ? (
                  <Badge variant="accent" className="ml-2 align-middle">
                    Has summary
                  </Badge>
                ) : null}
              </TableCell>
              <TableCell className="text-muted-foreground">{countsText(c) ?? 'No notes yet'}</TableCell>
              <TableCell className="text-right whitespace-nowrap text-muted-foreground tabular-nums">
                {c.last_noted_at ? formatDate(c.last_noted_at) : ''}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </DataTable>
      {moved.length > 0 ? (
        <section aria-labelledby="moved-h" className="space-y-2">
          <h2 id="moved-h" className="text-sm font-semibold">
            Moved or removed chapters
          </h2>
          <Alert variant="info">
            These chapters are not in your current syllabus any more. Your notes, highlights and PDFs are safe: re-file
            them under a chapter that exists now.
          </Alert>
          <DataTable aria-label="Moved or removed chapters">
            <TableBody>
              {moved.map((m) => (
                <TableRow key={m.chapter_key}>
                  <TableCell className="min-w-48 whitespace-normal">
                    <p className="font-medium break-words">{m.chapter_name}</p>
                    <p className="text-xs text-muted-foreground">{countsText(m) ?? 'Nothing filed here'}</p>
                  </TableCell>
                  <TableCell className="w-px text-right">
                    <Button variant="outline" size="sm" onClick={() => onRelink(m)}>
                      Re-link
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </DataTable>
        </section>
      ) : null}
    </div>
  )
}
