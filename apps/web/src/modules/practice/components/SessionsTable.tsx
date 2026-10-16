import {
  Badge,
  Button,
  DataTable,
  Play,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { SessionRow } from '../lib/types'

const modeLabel = (mode: string) => {
  const words = mode.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

interface SessionsTableProps {
  sessions: SessionRow[]
  /** `open`: sessions to resume. `done`: submitted sessions with a score and a Review link. */
  variant: 'open' | 'done'
}

/** Practice sessions as a table. Used for "In progress" (Resume) and "Recent sessions" (score, Review). */
export function SessionsTable({ sessions, variant }: SessionsTableProps) {
  const done = variant === 'done'
  return (
    <DataTable>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Session</TableHead>
          <TableHead className="hidden sm:table-cell">Mode</TableHead>
          <TableHead className="hidden text-right sm:table-cell">Questions</TableHead>
          {done ? <TableHead className="text-right">Score</TableHead> : <TableHead>Status</TableHead>}
          {done ? <TableHead className="hidden md:table-cell">Submitted</TableHead> : null}
          <TableHead className="text-right">
            <span className="sr-only">Action</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sessions.map((s) => {
          const accuracy =
            s.score !== null && s.max_score ? Math.round((Number(s.score) / Number(s.max_score)) * 100) : null
          return (
            <TableRow key={s.id}>
              <TableCell className="max-w-56 truncate font-medium">
                {s.title || (done ? 'Completed Practice' : 'Practice Session')}
              </TableCell>
              <TableCell className="hidden text-muted-foreground sm:table-cell">{modeLabel(s.mode)}</TableCell>
              <TableCell className="hidden text-right text-muted-foreground tabular-nums sm:table-cell">
                {s.question_count}
              </TableCell>
              {done ? (
                <TableCell className="text-right whitespace-nowrap tabular-nums">
                  {s.score !== null ? (
                    <>
                      {s.score} / {s.max_score}
                      {accuracy !== null ? <span className="ml-1.5 text-muted-foreground">{accuracy}%</span> : null}
                    </>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
              ) : (
                <TableCell>
                  <Badge variant={s.status === 'paused' ? 'outline' : 'default'}>
                    {s.status === 'paused' ? 'Paused' : 'Active'}
                  </Badge>
                </TableCell>
              )}
              {done ? (
                <TableCell className="hidden text-muted-foreground tabular-nums md:table-cell">
                  {s.submitted_at ? new Date(s.submitted_at).toLocaleDateString() : '-'}
                </TableCell>
              ) : null}
              <TableCell className="text-right">
                {done ? (
                  <Button size="sm" variant="outline" asChild>
                    <Link to="/app/practice/session/$id/review" params={{ id: s.id }}>
                      Review
                    </Link>
                  </Button>
                ) : (
                  <Button size="sm" asChild>
                    <Link to="/app/practice/session/$id" params={{ id: s.id }}>
                      <Play aria-hidden className="size-3.5 fill-current" /> Resume
                    </Link>
                  </Button>
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </DataTable>
  )
}
