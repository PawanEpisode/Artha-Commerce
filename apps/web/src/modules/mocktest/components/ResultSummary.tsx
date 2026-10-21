import { FileText } from '@artha/design-system'
import React, { useState } from 'react'

import type { AttemptResult } from '../lib/types'
import { PdfViewerModal } from './PdfViewerModal'

interface ResultSummaryProps {
  result: AttemptResult
  onReview: () => void
  onBackToMocks: () => void
  className?: string
}

export const ResultSummary: React.FC<ResultSummaryProps> = ({ result, onReview, onBackToMocks, className = '' }) => {
  const [isPdfOpen, setIsPdfOpen] = useState(false)
  const timeMins = Math.round(result.time_used_seconds / 60)
  const isPassed = (result.percent ?? 0) >= 40

  let integrityBadge = (
    <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
      Verified Clean Session
    </span>
  )
  if (result.integrity_class === 'suspect') {
    integrityBadge = (
      <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-300">
        Review Flagged
      </span>
    )
  } else if (result.integrity_class === 'unverified') {
    integrityBadge = (
      <span className="rounded-full bg-muted px-3 py-1 text-xs font-semibold text-muted-foreground">
        Practice Session
      </span>
    )
  }

  return (
    <div className={`mx-auto max-w-3xl space-y-8 rounded-3xl border bg-card p-6 shadow-sm ${className}`}>
      {/* Header */}
      <div className="space-y-3 border-b border-border pb-6 text-center">
        <div className="flex items-center justify-center gap-2">
          {integrityBadge}
          <span className="text-xs text-muted-foreground">Attempt #{result.attempt_no}</span>
        </div>
        <h1 className="text-2xl font-black tracking-tight text-foreground sm:text-3xl">{result.paper_title}</h1>
        <p className="text-sm text-muted-foreground">Completed in {timeMins} minutes · Submitted successfully</p>
      </div>

      {/* Main Score Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {/* Score & Percent */}
        <div className="space-y-1 rounded-2xl border border-primary/20 bg-primary/5 p-5 text-center">
          <div className="text-xs font-semibold tracking-wider text-primary uppercase">Score</div>
          <div className="text-3xl font-black text-foreground sm:text-4xl">
            {result.score ?? 0}
            <span className="text-base font-normal text-muted-foreground"> / {result.max_score}</span>
          </div>
          <div className={`text-sm font-bold ${isPassed ? 'text-emerald-600' : 'text-rose-600'}`}>
            {result.percent}% ({isPassed ? 'Qualified' : 'Needs Practice'})
          </div>
        </div>

        {/* Percentile or Quartile */}
        <div className="space-y-1 rounded-2xl border bg-muted/30 p-5 text-center">
          <div className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Standing</div>
          <div className="text-2xl font-black text-foreground sm:text-3xl">
            {result.percentile_data?.percentile !== undefined
              ? `${result.percentile_data.percentile}th`
              : (result.percentile_data?.band ?? 'Eligible')}
          </div>
          <div className="text-xs text-muted-foreground">
            {result.percentile_eligible ? 'Cohort Percentile' : 'Practice Mode'}
          </div>
        </div>

        {/* Time Used */}
        <div className="space-y-1 rounded-2xl border bg-muted/30 p-5 text-center">
          <div className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Time Spent</div>
          <div className="font-mono text-2xl font-black text-foreground sm:text-3xl">{timeMins}m</div>
          <div className="text-xs text-muted-foreground">Duration</div>
        </div>
      </div>

      {/* Section Breakdown */}
      <div className="space-y-3">
        <h3 className="text-base font-bold text-foreground">Section Scores & Accuracy</h3>
        <div className="overflow-hidden rounded-2xl border text-sm">
          <table className="w-full text-left">
            <thead className="border-b bg-muted/60 text-xs text-muted-foreground">
              <tr>
                <th className="p-3">Section</th>
                <th className="p-3 text-center">Correct</th>
                <th className="p-3 text-center">Incorrect</th>
                <th className="p-3 text-center">Skipped</th>
                <th className="p-3 text-right">Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {result.sections.map((sec) => (
                <tr key={sec.key}>
                  <td className="p-3 font-medium text-foreground">
                    Section {sec.key} {sec.title ? `· ${sec.title}` : ''}
                  </td>
                  <td className="p-3 text-center font-semibold text-emerald-600">{sec.correct}</td>
                  <td className="p-3 text-center font-semibold text-rose-600">{sec.incorrect}</td>
                  <td className="p-3 text-center text-muted-foreground">{sec.skipped}</td>
                  <td className="p-3 text-right font-mono font-bold text-foreground">
                    {sec.score} / {sec.max_score}M
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
        {result.solution_pdf_url && (
          <button
            type="button"
            onClick={() => setIsPdfOpen(true)}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-5 py-2.5 text-sm font-semibold text-primary transition-colors hover:bg-primary/10"
          >
            <FileText className="h-4 w-4" />
            <span>Official Solution Sheet (PDF)</span>
          </button>
        )}
        <button
          type="button"
          onClick={onBackToMocks}
          className="min-h-[44px] rounded-xl border px-5 py-2.5 text-sm font-semibold transition-colors hover:bg-muted"
        >
          All Mock Tests
        </button>
        <button
          type="button"
          onClick={onReview}
          className="min-h-[44px] rounded-xl bg-primary px-6 py-2.5 text-sm font-bold text-primary-foreground shadow-xs transition-colors hover:bg-primary/90"
        >
          Review Questions & Key
        </button>
      </div>

      {result.solution_pdf_url && (
        <PdfViewerModal
          isOpen={isPdfOpen}
          title={result.paper_title}
          pdfUrl={result.solution_pdf_url}
          subtitle="Official Model Answers & Rubric"
          onClose={() => setIsPdfOpen(false)}
        />
      )}
    </div>
  )
}
