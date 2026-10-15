import { Badge } from '@artha/design-system'

import { groupMilestones, milestoneTitle, movedNote, statusNote } from '../lib/planner'
import type { Milestone } from '../lib/planner-types'
import { formatDay } from '../lib/time'

function Row({ m }: { m: Milestone }) {
  const moved = movedNote(m)
  const note = statusNote(m)
  const finished = m.status === 'done' || m.status === 'dropped'
  return (
    <li
      className={`flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-xl border border-border p-3 ${finished ? 'bg-card/50 text-muted-foreground' : 'bg-card'}`}
    >
      <span className="min-w-0 flex-1 font-medium">{milestoneTitle(m)}</span>
      <span className="text-sm">{formatDay(m.target_date)}</span>
      <span className="flex flex-wrap gap-1">
        {note ? (
          <Badge variant={m.overdue_days > 0 || m.status === 'at_risk' ? 'highlight' : 'outline'}>{note}</Badge>
        ) : null}
        {moved ? <Badge variant="outline">{moved}</Badge> : null}
      </span>
    </li>
  )
}

/** The plan's dates in order. Long lists scroll inside their own box so the page does not grow (PRD 7.x, 320 px). */
export function MilestoneList({ milestones }: { milestones: Milestone[] }) {
  const { open, finished } = groupMilestones(milestones)
  return (
    <section aria-labelledby="milestones-heading" className="space-y-3">
      <h2 id="milestones-heading" className="font-display text-lg font-bold">
        Milestones
      </h2>
      <ul className="max-h-[28rem] space-y-2 overflow-y-auto pr-1">
        {open.map((m) => (
          <Row key={m.id} m={m} />
        ))}
      </ul>
      {finished.length ? (
        <details className="space-y-2">
          <summary className="cursor-pointer text-sm text-muted-foreground">Done ({finished.length})</summary>
          <ul className="mt-2 space-y-2">
            {finished.map((m) => (
              <Row key={m.id} m={m} />
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  )
}
