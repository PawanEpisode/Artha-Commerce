import { Badge, buttonVariants } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { DueRow } from '~/modules/coverage'

import { dueNote } from '../lib/summaries'

/** Up to three chapters due for revision. Empty wording only for students who have revised before. */
export function DueView({ rows, total }: { rows: DueRow[]; total: number }) {
  return (
    <>
      <ul className="space-y-3">
        {rows.map((row) => (
          <li key={row.id} className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-medium">{row.name}</p>
              <p className="truncate text-sm text-muted-foreground">{row.subject.name}</p>
            </div>
            <Badge variant={row.overdue_days > 0 ? 'highlight' : 'default'}>{dueNote(row.overdue_days)}</Badge>
            <Link
              to="/app/syllabus/$subject/$chapter"
              params={{ subject: row.subject.id, chapter: row.id }}
              className={buttonVariants({ variant: 'outline', size: 'sm' })}
            >
              Open <span className="sr-only">{row.name}</span>
            </Link>
          </li>
        ))}
      </ul>
      {total > rows.length ? (
        <Link
          to="/app/revision"
          className="mt-auto text-sm font-semibold text-primary underline-offset-4 hover:underline"
        >
          See all {total} due
        </Link>
      ) : null}
    </>
  )
}
