import { Badge, Button, ConfidenceBadge, TermStrip } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { ScoredChapter } from '../types'
import { ReasonList } from './ReasonList'

export interface PriorityRowProps {
  chapter: ScoredChapter
  subjectKey: string
  showActions?: boolean
}

interface SittingData {
  term_code: string
  effective_marks?: number
  marks?: number
  is_carried?: boolean
}

export function PriorityRow({ chapter, subjectKey, showActions = true }: PriorityRowProps) {
  const rawSittings = (chapter.history?.sittings as SittingData[] | undefined) || []
  const sittings = rawSittings.map((s) => ({
    termCode: s.term_code,
    marks: Number(s.effective_marks ?? s.marks ?? 0),
    isAsked: (s.effective_marks ?? s.marks ?? 0) > 0,
    isCarried: Boolean(s.is_carried),
  }))

  const tierBadgeConfig = {
    core: { label: 'Core', variant: 'default' as const },
    next: { label: 'Next', variant: 'accent' as const },
    rest: { label: 'Lower expected weight', variant: 'outline' as const },
  }

  const tierMeta = tierBadgeConfig[chapter.tier] || tierBadgeConfig.rest

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-xs transition-colors hover:border-primary/40">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-6 items-center justify-center rounded-full bg-muted font-mono text-xs font-semibold text-muted-foreground">
            {chapter.rank}
          </span>
          <Link
            to="/app/analysis/$subjectKey/$chapterKey"
            params={{ subjectKey, chapterKey: chapter.chapter_key }}
            className="text-sm font-semibold text-foreground transition-colors hover:text-primary hover:underline"
          >
            {chapter.name}
          </Link>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Badge variant={tierMeta.variant}>{tierMeta.label}</Badge>
          <ConfidenceBadge level={chapter.confidence} />
        </div>
      </div>

      {/* Marks Summary */}
      <div className="flex items-center justify-between rounded-md bg-muted/20 px-3 py-1.5 text-xs text-muted-foreground">
        <span>
          Expected from history:{' '}
          <strong className="font-mono font-semibold text-foreground">{chapter.expected_marks.toFixed(1)} marks</strong>{' '}
          <span className="text-[11px] text-muted-foreground/80">(estimate, not a forecast)</span>
        </span>
        {chapter.student?.coverage_pct !== undefined && (
          <span className="text-[11px]">
            Your coverage: <strong>{chapter.student.coverage_pct}%</strong>
          </span>
        )}
      </div>

      {/* Sittings Strip */}
      {sittings.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="shrink-0 text-xs text-muted-foreground">Recent sittings:</span>
          <TermStrip sittings={sittings} compact />
        </div>
      )}

      {/* Reasons list */}
      <ReasonList reasons={chapter.reasons} maxItems={2} />

      {/* Actions */}
      {showActions && (
        <div className="flex items-center justify-end gap-2 border-t border-muted/60 pt-1">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/app/analysis/$subjectKey/$chapterKey" params={{ subjectKey, chapterKey: chapter.chapter_key }}>
              Historical Analysis
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to="/app/practice" search={{ chapter_id: chapter.chapter_id }}>
              Practise
            </Link>
          </Button>
        </div>
      )}
    </div>
  )
}
