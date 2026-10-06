import type { DueRow, SubjectRow } from '~/modules/coverage'

export const WIDGET_ROWS = 3

/** "Due today", "1 day late", "3 days late". */
export function dueNote(overdueDays: number): string {
  if (overdueDays <= 0) return 'Due today'
  return overdueDays === 1 ? '1 day late' : `${overdueDays} days late`
}

/** The server already orders the list (most overdue, then heavier chapters); the card shows the first few. */
export const topDue = (rows: readonly DueRow[], limit = WIDGET_ROWS): DueRow[] => rows.slice(0, limit)

/** The papers furthest behind: lowest average progress first, ignoring papers with nothing left to study. */
export function weakestSubjects(subjects: readonly SubjectRow[], limit = WIDGET_ROWS): SubjectRow[] {
  return [...subjects]
    .filter((s) => s.chapters_total > 0)
    .sort((a, b) => a.pct_simple - b.pct_simple || a.name.localeCompare(b.name))
    .slice(0, limit)
}
