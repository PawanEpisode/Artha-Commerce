import React, { useState } from 'react'

import { usePaperDetail } from '../hooks/usePaperDetail'
import { startAttempt } from '../lib/api'

interface PaperDetailContainerProps {
  paperId: string
  onStartAttempt: (attemptId: string) => void
  onViewResult?: (attemptId: string) => void
  onBack: () => void
}

export const PaperDetailContainer: React.FC<PaperDetailContainerProps> = ({
  paperId,
  onStartAttempt,
  onViewResult,
  onBack,
}) => {
  const { paper, isLoading, error } = usePaperDetail(paperId)
  const [isStarting, setIsStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-6 p-8">
        <div className="h-8 w-48 rounded-xl bg-muted" />
        <div className="h-64 rounded-3xl border bg-muted/40" />
      </div>
    )
  }

  if (error || !paper) {
    return (
      <div className="mx-auto max-w-xl space-y-4 p-8 text-center">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Failed to load paper details.
        </div>
        <button
          type="button"
          onClick={onBack}
          className="min-h-[44px] rounded-xl border px-4 py-2 text-sm font-semibold"
        >
          Back to Mock Tests
        </button>
      </div>
    )
  }

  const durationMins = Math.round(paper.duration_seconds / 60)
  const readingMins = Math.round(paper.reading_seconds / 60)

  const handleStart = async (runMode: 'exam' | 'practice') => {
    setIsStarting(true)
    setStartError(null)
    try {
      const attempt = await startAttempt(paper.id, runMode)
      onStartAttempt(attempt.id)
    } catch (err: unknown) {
      setIsStarting(false)
      const errObj = err as { body?: { error?: { message?: string } }; message?: string }
      const msg = errObj.body?.error?.message ?? errObj.message ?? 'Could not start exam attempt.'
      setStartError(msg)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-4 sm:p-8">
      {/* Back button */}
      <button
        type="button"
        onClick={onBack}
        className="inline-flex min-h-[44px] items-center gap-2 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
        <span>Back to Tests</span>
      </button>

      {/* Main Card */}
      <div className="space-y-6 rounded-3xl border bg-card p-6 shadow-sm sm:p-8">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary uppercase">
              {paper.kind.toUpperCase()}
            </span>
            <span className="rounded-full bg-muted px-3 py-1 text-xs font-semibold text-muted-foreground capitalize">
              {paper.source_tag}
            </span>
          </div>

          <h1 className="text-2xl font-black tracking-tight text-foreground sm:text-3xl">{paper.title}</h1>

          <p className="text-sm text-muted-foreground">
            Subject: <span className="font-semibold text-foreground uppercase">{paper.subject_key}</span>
          </p>
        </div>

        {/* Blueprint Specs Grid */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-2xl border bg-muted/30 p-4 text-center">
            <div className="text-xs text-muted-foreground">Duration</div>
            <div className="mt-1 text-xl font-black text-foreground">{durationMins}m</div>
          </div>
          <div className="rounded-2xl border bg-muted/30 p-4 text-center">
            <div className="text-xs text-muted-foreground">Reading Time</div>
            <div className="mt-1 text-xl font-black text-foreground">{readingMins}m</div>
          </div>
          <div className="rounded-2xl border bg-muted/30 p-4 text-center">
            <div className="text-xs text-muted-foreground">Total Marks</div>
            <div className="mt-1 text-xl font-black text-foreground">{paper.total_marks}M</div>
          </div>
          <div className="rounded-2xl border bg-muted/30 p-4 text-center">
            <div className="text-xs text-muted-foreground">Timing Mode</div>
            <div className="mt-1 text-sm font-bold text-foreground capitalize">
              {paper.section_timing.replace('_', ' ')}
            </div>
          </div>
        </div>

        {/* Section Structure */}
        <div className="space-y-3 pt-2">
          <h3 className="text-base font-bold text-foreground">Blueprint Structure</h3>
          <div className="overflow-hidden rounded-2xl border text-sm">
            <table className="w-full text-left">
              <thead className="border-b bg-muted/60 text-xs text-muted-foreground">
                <tr>
                  <th className="p-3">Section</th>
                  <th className="p-3">Type</th>
                  <th className="p-3 text-right">Marks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paper.sections.map((sec) => (
                  <tr key={sec.key}>
                    <td className="p-3 font-semibold text-foreground">
                      Section {sec.key}: {sec.title}
                    </td>
                    <td className="p-3 text-muted-foreground capitalize">{sec.kind}</td>
                    <td className="p-3 text-right font-mono font-bold text-foreground">{sec.marks_total}M</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Start error message */}
        {startError && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{startError}</div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap items-center justify-end gap-4 border-t border-border pt-4">
          {paper.my_attempt && onViewResult && (
            <button
              type="button"
              onClick={() => {
                if (paper.my_attempt) onViewResult(paper.my_attempt.id)
              }}
              className="min-h-[44px] rounded-xl border px-5 py-2.5 text-sm font-semibold transition-colors hover:bg-muted"
            >
              View Last Result
            </button>
          )}

          <button
            type="button"
            disabled={isStarting}
            onClick={() => handleStart('practice')}
            className="min-h-[44px] rounded-xl border px-5 py-2.5 text-sm font-semibold transition-colors hover:bg-muted"
          >
            Practice Untimed
          </button>

          <button
            type="button"
            disabled={isStarting}
            onClick={() => handleStart('exam')}
            className="flex min-h-[44px] items-center gap-2 rounded-xl bg-primary px-6 py-2.5 text-sm font-bold text-primary-foreground shadow-xs transition-colors hover:bg-primary/90"
          >
            {isStarting && (
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            )}
            <span>Start Strict Exam Mode</span>
          </button>
        </div>
      </div>
    </div>
  )
}
