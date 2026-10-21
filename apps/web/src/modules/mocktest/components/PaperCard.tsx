import React from 'react'

import type { MockPaperCard } from '../lib/types'

interface PaperCardProps {
  paper: MockPaperCard
  onSelect: (paperId: string) => void
  className?: string
}

export const PaperCard: React.FC<PaperCardProps> = ({ paper, onSelect, className = '' }) => {
  const durationMins = Math.round(paper.duration_seconds / 60)

  return (
    <div
      className={`flex flex-col justify-between rounded-2xl border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md ${className}`}
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary uppercase">
              {paper.kind.toUpperCase()}
            </span>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground capitalize">
              {paper.source_tag}
            </span>
            {paper.answer_key_status === 'released' && (
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                Key Released
              </span>
            )}
          </div>
          <span className="text-xs text-muted-foreground">{paper.attempt_count} attempts</span>
        </div>

        <h3 className="line-clamp-2 text-base leading-snug font-bold text-foreground">{paper.title}</h3>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-border pt-4">
        <div className="flex items-center gap-4 text-xs font-medium text-muted-foreground">
          <div className="flex items-center gap-1">
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>{durationMins} mins</span>
          </div>
          <div className="flex items-center gap-1 font-mono">
            <span>{paper.total_marks} Marks</span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => onSelect(paper.id)}
          className="min-h-[44px] rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-xs transition-colors hover:bg-primary/90"
        >
          View Paper
        </button>
      </div>
    </div>
  )
}
