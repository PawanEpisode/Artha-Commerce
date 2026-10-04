import { Badge, Card, ChevronRight, ConfidenceDot, ProgressBar } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { ChapterRow } from '../lib/types'
import { StatusBadge } from './StatusBadge'

/** Chapters of one subject: percent, status, confidence (beside the measured percent, FR-21). */
export function ChapterList({ subjectId, chapters }: { subjectId: string; chapters: ChapterRow[] }) {
  return (
    <ol className="space-y-3">
      {chapters.map((c, i) => (
        <li key={c.id}>
          <Card
            className={`focus-within:ring-[3px] focus-within:ring-ring/40 hover:shadow-(--shadow-soft) ${c.is_excluded ? 'opacity-70' : ''}`}
          >
            <Link
              to="/app/syllabus/$subject/$chapter"
              params={{ subject: subjectId, chapter: c.id }}
              className="flex items-center gap-4 rounded-xl p-4 outline-none"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary font-display font-bold text-primary">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1 space-y-2">
                <span className="block font-medium">{c.name}</span>
                <span className="flex flex-wrap items-center gap-2">
                  {c.is_excluded ? <Badge variant="outline">Excluded</Badge> : <StatusBadge status={c.status} />}
                  {c.confidence ? <ConfidenceDot value={c.confidence} showLabel /> : null}
                </span>
                {c.is_excluded ? null : <ProgressBar size="sm" value={c.coverage_pct} label={`${c.name} coverage`} />}
              </span>
              <span className="w-12 shrink-0 text-right font-display text-lg font-bold tabular-nums">
                {c.is_excluded ? '' : `${c.coverage_pct}%`}
              </span>
              <ChevronRight aria-hidden className="size-5 shrink-0 text-muted-foreground" />
            </Link>
          </Card>
        </li>
      ))}
    </ol>
  )
}
