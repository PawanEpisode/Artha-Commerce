import { DataTable, Skeleton, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { pluralize } from '../lib/format'

export interface SubjectTile {
  key: string
  name: string
  /** Notes in the subject; undefined while loading or when the count could not be read. */
  notes?: number
  state: 'loading' | 'error' | 'ok'
}

/** The subjects of the student's course as a small table: name links to its notes, count on the right. A failed count says so, never "0". */
export function SubjectGrid({ subjects }: { subjects: readonly SubjectTile[] }) {
  return (
    <DataTable aria-label="Subjects">
      <TableHeader>
        <TableRow>
          <TableHead>Subject</TableHead>
          <TableHead className="text-right">Notes</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {subjects.map((s) => (
          <TableRow key={s.key}>
            <TableCell className="min-w-0 whitespace-normal">
              <Link
                to="/app/notes/$subject"
                params={{ subject: s.key }}
                className="font-medium break-words underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                {s.name}
              </Link>
            </TableCell>
            <TableCell className="text-right whitespace-nowrap text-muted-foreground tabular-nums">
              {s.state === 'loading' ? (
                <Skeleton className="ml-auto h-4 w-14" />
              ) : s.state === 'error' ? (
                <span className="text-xs">Count not available</span>
              ) : (
                pluralize(s.notes ?? 0, 'note')
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </DataTable>
  )
}
