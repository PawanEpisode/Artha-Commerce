import { Badge, DataTable, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@artha/design-system'

import { groupMilestones, milestoneTitle, movedNote, statusNote } from '../lib/planner'
import type { Milestone } from '../lib/planner-types'
import { formatDay } from '../lib/time'

function Row({ m }: { m: Milestone }) {
  const moved = movedNote(m)
  const note = statusNote(m)
  const finished = m.status === 'done' || m.status === 'dropped'
  return (
    <TableRow className={finished ? 'text-muted-foreground' : undefined}>
      <TableCell className="max-w-0 min-w-40 font-medium break-words whitespace-normal">{milestoneTitle(m)}</TableCell>
      <TableCell className="whitespace-nowrap tabular-nums">{formatDay(m.target_date)}</TableCell>
      <TableCell>
        <span className="flex flex-wrap gap-1">
          {note ? (
            <Badge variant={m.overdue_days > 0 || m.status === 'at_risk' ? 'highlight' : 'outline'}>{note}</Badge>
          ) : null}
          {moved ? <Badge variant="outline">{moved}</Badge> : null}
        </span>
      </TableCell>
    </TableRow>
  )
}

function MilestoneTable({ rows, label, className }: { rows: Milestone[]; label: string; className?: string }) {
  return (
    <DataTable aria-label={label} containerClassName={className}>
      <TableHeader>
        <TableRow>
          <TableHead>Milestone</TableHead>
          <TableHead>Date</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((m) => (
          <Row key={m.id} m={m} />
        ))}
      </TableBody>
    </DataTable>
  )
}

/** The plan's dates in order. Long lists scroll inside their own box so the page does not grow (PRD 7.x, 320 px). */
export function MilestoneList({ milestones }: { milestones: Milestone[] }) {
  const { open, finished } = groupMilestones(milestones)
  return (
    <section aria-labelledby="milestones-heading" className="space-y-2">
      <h2 id="milestones-heading" className="text-sm font-semibold">
        Milestones
      </h2>
      <MilestoneTable rows={open} label="Open milestones" className="max-h-[32rem] overflow-y-auto" />
      {finished.length ? (
        <details className="space-y-2">
          <summary className="cursor-pointer text-[13px] text-muted-foreground">Done ({finished.length})</summary>
          <div className="mt-2">
            <MilestoneTable rows={finished} label="Finished milestones" />
          </div>
        </details>
      ) : null}
    </section>
  )
}
