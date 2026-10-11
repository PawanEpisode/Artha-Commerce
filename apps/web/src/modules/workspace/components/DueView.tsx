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
          <li key={row.id} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <div className="min-w-0 basis-full sm:flex-1 sm:basis-0">
              <p className="truncate font-medium">{row.name}</p>
              <p className="truncate text-sm text-muted-foreground">{row.subject.name}</p>
            </div>
            <div className="flex w-full items-center justify-between gap-3 sm:w-auto sm:justify-end">
              <Badge variant={row.overdue_days > 0 ? 'highlight' : 'default'}>{dueNote(row.overdue_days)}</Badge>
              <Link
                to="/app/syllabus/$subject/$chapter"
                params={{ subject: row.subject.id, chapter: row.id }}
                className={buttonVariants({ variant: 'outline', size: 'sm' })}
              >
                Open <span className="sr-only">{row.name}</span>
              </Link>
            </div>
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
