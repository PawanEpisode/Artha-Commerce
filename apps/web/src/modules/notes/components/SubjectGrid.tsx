import { Card, ChevronRight, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { pluralize } from '../lib/format'

export interface SubjectTile {
  key: string
  name: string
  /** Notes in the subject; undefined while loading or when the count could not be read. */
  notes?: number
  state: 'loading' | 'error' | 'ok'
}

/** The subjects of the student's course, each a link to its notes with a count. A failed count says so, never "0". */
export function SubjectGrid({ subjects }: { subjects: readonly SubjectTile[] }) {
  return (
    <ul aria-label="Subjects" className="grid gap-3 sm:grid-cols-2">
      {subjects.map((s) => (
        <li key={s.key}>
          <Card className="relative flex min-h-20 items-center gap-3 p-4 transition-colors focus-within:ring-[3px] focus-within:ring-ring/40 hover:bg-muted/50">
            <div className="min-w-0 flex-1">
              <h3 className="font-display text-base leading-snug font-bold break-words">
                <Link
                  to="/app/notes/$subject"
                  params={{ subject: s.key }}
                  className="outline-none after:absolute after:inset-0 after:content-['']"
                >
                  {s.name}
                </Link>
              </h3>
              {s.state === 'loading' ? (
                <Skeleton className="mt-1 h-4 w-20" />
              ) : s.state === 'error' ? (
                <p className="text-sm text-muted-foreground">Count not available</p>
              ) : (
                <p className="text-sm text-muted-foreground">{pluralize(s.notes ?? 0, 'note')}</p>
              )}
            </div>
            <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
          </Card>
        </li>
      ))}
    </ul>
  )
}
