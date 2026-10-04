import { Badge, Card, ChevronRight, ConfidenceDot, EmptyState, ListChecks } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { DueRow } from '../lib/types'

function dueLabel(days: number) {
  if (days <= 0) return 'Due today'
  return `${days} day${days === 1 ? '' : 's'} overdue`
}

/** Chapters whose next revision date has arrived. Overdue and high-weight first (the API orders them). */
export function DueList({ rows }: { rows: DueRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<ListChecks aria-hidden />}
        title="Nothing due for revision"
        description="When you log a revision, the next one is scheduled automatically and shows up here on the day."
      />
    )
  }
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.id}>
          <Card className="focus-within:ring-[3px] focus-within:ring-ring/40 hover:shadow-(--shadow-soft)">
            <Link
              to="/app/syllabus/$subject/$chapter"
              params={{ subject: r.subject.id, chapter: r.id }}
              className="flex items-center gap-4 rounded-xl p-4 outline-none"
            >
              <span className="min-w-0 flex-1">
                <span className="block font-semibold">{r.name}</span>
                <span className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <span>{r.subject.name}</span>
                  <Badge variant={r.overdue_days > 0 ? 'highlight' : 'default'}>{dueLabel(r.overdue_days)}</Badge>
                  {r.confidence ? <ConfidenceDot value={r.confidence} showLabel /> : null}
                </span>
              </span>
              <span className="font-display text-lg font-bold tabular-nums">{r.coverage_pct}%</span>
              <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
            </Link>
          </Card>
        </li>
      ))}
    </ul>
  )
}
