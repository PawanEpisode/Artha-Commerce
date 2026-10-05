import { Badge, BookOpen, ChevronRight, ConfidenceDot, EmptyState, EntityBadge, ListChecks } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { EntityIndex, EntityListRow, EntityTitle, ROW_LINK_CLASS } from '~/modules/syllabus'

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
          <EntityListRow kind="chapter">
            <Link
              to="/app/syllabus/$subject/$chapter"
              params={{ subject: r.subject.id, chapter: r.id }}
              className={ROW_LINK_CLASS}
            >
              <EntityIndex kind="chapter">
                <BookOpen className="size-5" />
              </EntityIndex>
              <span className="min-w-0 space-y-2">
                <EntityTitle>{r.name}</EntityTitle>
                <span className="flex flex-wrap items-center gap-2">
                  <EntityBadge kind="paper" title={r.subject.name} className="max-w-[12rem]">
                    {r.subject.name}
                  </EntityBadge>
                  <Badge variant={r.overdue_days > 0 ? 'highlight' : 'default'}>{dueLabel(r.overdue_days)}</Badge>
                  {r.confidence ? <ConfidenceDot value={r.confidence} showLabel /> : null}
                </span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-12 text-right font-display text-lg font-bold tabular-nums">{r.coverage_pct}%</span>
                <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
              </span>
            </Link>
          </EntityListRow>
        </li>
      ))}
    </ul>
  )
}
