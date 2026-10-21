import React from 'react'

import type { AttemptLayoutItem, AttemptSectionState } from '../lib/types'

interface SubmitReviewSheetProps {
  layout: AttemptLayoutItem[]
  sections: AttemptSectionState[]
  answers: Record<number, unknown>
  flags: Record<number, boolean>
  isSubmitting: boolean
  onConfirm: () => void
  onCancel: () => void
}

export const SubmitReviewSheet: React.FC<SubmitReviewSheetProps> = ({
  layout,
  sections,
  answers,
  flags: _flags,
  isSubmitting,
  onConfirm,
  onCancel,
}) => {
  const total = layout.length
  let answered = 0

  layout.forEach((it) => {
    const hasAns = answers[it.pos] !== undefined && answers[it.pos] !== null
    if (hasAns) answered++
  })

  const unanswered = total - answered

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-labelledby="submit-modal-title"
    >
      <div className="w-full max-w-lg space-y-6 rounded-2xl border bg-card p-6 shadow-xl">
        <div className="space-y-1">
          <h3 id="submit-modal-title" className="text-xl font-bold text-foreground">
            Submit Examination
          </h3>
          <p className="text-sm text-muted-foreground">Review your progress summary before final submission.</p>
        </div>

        {/* Counts Grid */}
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border bg-muted/40 p-3 text-center">
            <div className="text-2xl font-bold text-foreground">{total}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">Total Questions</div>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-center dark:border-emerald-800 dark:bg-emerald-950/40">
            <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">{answered}</div>
            <div className="mt-0.5 text-xs text-emerald-600 dark:text-emerald-400">Answered</div>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-center dark:border-amber-800 dark:bg-amber-950/40">
            <div className="text-2xl font-bold text-amber-700 dark:text-amber-300">{unanswered}</div>
            <div className="mt-0.5 text-xs text-amber-600 dark:text-amber-400">Unanswered</div>
          </div>
        </div>

        {/* Section Breakdown */}
        <div className="overflow-hidden rounded-xl border text-sm">
          <table className="w-full text-left">
            <thead className="border-b bg-muted/60 text-xs text-muted-foreground">
              <tr>
                <th className="p-2.5">Section</th>
                <th className="p-2.5 text-center">Questions</th>
                <th className="p-2.5 text-center">Answered</th>
                <th className="p-2.5 text-right">Max Marks</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sections.map((sec) => {
                const secItems = layout.filter((l) => l.section === sec.key)
                const secAns = secItems.filter((l) => answers[l.pos] !== undefined && answers[l.pos] !== null).length

                return (
                  <tr key={sec.key}>
                    <td className="p-2.5 font-medium text-foreground">
                      Section {sec.key}: {sec.title}
                    </td>
                    <td className="p-2.5 text-center text-muted-foreground">{secItems.length}</td>
                    <td className="p-2.5 text-center font-semibold text-emerald-600 dark:text-emerald-400">{secAns}</td>
                    <td className="p-2.5 text-right font-mono text-muted-foreground">{sec.max_score}M</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {unanswered > 0 && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-600 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-400">
            Note: You still have {unanswered} unanswered question{unanswered > 1 ? 's' : ''}. Unanswered questions will
            receive zero marks.
          </p>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            disabled={isSubmitting}
            onClick={onCancel}
            className="min-h-[44px] rounded-xl border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            Return to Exam
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={onConfirm}
            className="flex min-h-[44px] items-center gap-2 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground shadow-xs transition-colors hover:bg-primary/90"
          >
            {isSubmitting && (
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            )}
            <span>{isSubmitting ? 'Submitting...' : 'Confirm & Submit'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
