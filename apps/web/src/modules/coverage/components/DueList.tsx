import {
  Badge,
  ConfidenceDot,
  DataTable,
  EmptyState,
  EntityBadge,
  ListChecks,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import type { DueRow } from '../lib/types'
import { ProgressCell } from './ProgressCell'

function dueLabel(days: number) {
  if (days <= 0) return 'Due today'
  return `${days} day${days === 1 ? '' : 's'} overdue`
}

/** What another module can hang under a row (its own link), composed by the route so coverage imports nothing of it. */
export type DueRowAction = (row: { chapterId: string; chapterName: string }) => ReactNode

/** Chapters whose next revision date has arrived, as a table. Overdue and high-weight first (the API orders them). */
export function DueList({ rows, renderAction }: { rows: DueRow[]; renderAction?: DueRowAction }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        className="rounded-lg py-6"
        icon={<ListChecks aria-hidden />}
        title="Nothing due for revision"
        description="When you log a revision, the next one is scheduled automatically and shows up here on the day."
      />
    )
  }
  return (
    <DataTable aria-label="Chapters due for revision">
      <TableHeader>
        <TableRow>
          <TableHead>Chapter</TableHead>
          <TableHead className="hidden md:table-cell">Paper</TableHead>
          <TableHead>Due</TableHead>
          <TableHead className="hidden sm:table-cell">Confidence</TableHead>
          <TableHead className="text-right">Coverage</TableHead>
          {renderAction ? (
            <TableHead className="w-px">
              <span className="sr-only">Actions</span>
            </TableHead>
          ) : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.id}>
            <TableCell className="min-w-44 whitespace-normal">
              <Link
                to="/app/syllabus/$subject/$chapter"
                params={{ subject: r.subject.id, chapter: r.id }}
                title={r.name}
                className="line-clamp-2 font-medium break-words underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                {r.name}
              </Link>
            </TableCell>
            <TableCell className="hidden max-w-48 md:table-cell">
              <EntityBadge kind="paper" title={r.subject.name} className="max-w-full">
                {r.subject.name}
              </EntityBadge>
            </TableCell>
            <TableCell className="whitespace-nowrap">
              <Badge variant={r.overdue_days > 0 ? 'highlight' : 'default'}>{dueLabel(r.overdue_days)}</Badge>
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              {r.confidence ? <ConfidenceDot value={r.confidence} showLabel /> : null}
            </TableCell>
            <TableCell className="text-right">
              <ProgressCell value={r.coverage_pct} label={`${r.name} coverage`} />
            </TableCell>
            {renderAction ? (
              <TableCell className="w-px text-right whitespace-nowrap">
                {renderAction({ chapterId: r.id, chapterName: r.name })}
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </DataTable>
  )
}
