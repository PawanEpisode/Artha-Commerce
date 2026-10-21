import {
  AlertCircle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  HelpCircle,
  XCircle,
} from '@artha/design-system'
import React, { useEffect, useMemo, useState } from 'react'

import { PdfViewerModal } from '../components/PdfViewerModal'
import { fetchAttemptReview } from '../lib/api'
import type { AttemptReview, AttemptReviewItem } from '../lib/types'

interface AttemptReviewContainerProps {
  attemptId: string
  onBackToResult: (attemptId: string) => void
  onBackToMocks: () => void
}

type FilterKind = 'all' | 'correct' | 'incorrect' | 'skipped' | 'excluded'

export const AttemptReviewContainer: React.FC<AttemptReviewContainerProps> = ({
  attemptId,
  onBackToResult,
  onBackToMocks,
}) => {
  const [review, setReview] = useState<AttemptReview | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [activeFilter, setActiveFilter] = useState<FilterKind>('all')
  const [expandedExplanations, setExpandedExplanations] = useState<Record<string, boolean>>({})
  const [isPdfOpen, setIsPdfOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)

    fetchAttemptReview(attemptId)
      .then((data) => {
        if (!cancelled) {
          setReview(data)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err)
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [attemptId])

  const toggleExplanation = (questionId: string) => {
    setExpandedExplanations((prev) => ({
      ...prev,
      [questionId]: !prev[questionId],
    }))
  }

  const filteredItems = useMemo(() => {
    if (!review?.items) return []
    return review.items.filter((item) => {
      if (activeFilter === 'all') return true
      if (activeFilter === 'correct') return item.result === 'correct'
      if (activeFilter === 'incorrect') return item.result === 'incorrect'
      if (activeFilter === 'skipped') return item.result === 'skipped'
      if (activeFilter === 'excluded') return item.is_excluded_by_choice
      return true
    })
  }, [review, activeFilter])

  const counts = useMemo(() => {
    const res = {
      all: review?.items?.length || 0,
      correct: 0,
      incorrect: 0,
      skipped: 0,
      excluded: 0,
    }
    review?.items?.forEach((i) => {
      if (i.result === 'correct') res.correct += 1
      if (i.result === 'incorrect') res.incorrect += 1
      if (i.result === 'skipped') res.skipped += 1
      if (i.is_excluded_by_choice) res.excluded += 1
    })
    return res
  }, [review])

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl animate-pulse space-y-4 p-4 sm:p-8">
        <div className="h-20 rounded-2xl border bg-muted/40" />
        <div className="h-64 rounded-2xl border bg-muted/40" />
      </div>
    )
  }

  if (error || !review) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-8 text-center">
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Failed to load attempt review.
        </div>
        <button
          type="button"
          onClick={() => onBackToResult(attemptId)}
          className="min-h-[44px] rounded-xl border px-4 py-2 text-sm font-semibold"
        >
          Back to Result
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-8">
      {/* Top Header */}
      <div className="flex flex-col justify-between gap-4 border-b pb-6 sm:flex-row sm:items-center">
        <div>
          <button
            type="button"
            onClick={() => onBackToResult(attemptId)}
            className="mb-2 inline-flex min-h-[44px] items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Scorecard
          </button>
          <h1 className="text-2xl font-bold tracking-tight">{review.paper_title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">Detailed Question-by-Question Review</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start sm:gap-3 sm:self-auto">
          {review.solution_pdf_url && (
            <button
              type="button"
              onClick={() => setIsPdfOpen(true)}
              className="inline-flex min-h-[44px] items-center gap-1.5 rounded-xl border border-primary/30 bg-primary/5 px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/10"
            >
              <FileText className="h-4 w-4" />
              <span>Official Solution (PDF)</span>
            </button>
          )}
          <div className="rounded-2xl border bg-muted/50 p-3 text-right">
            <div className="text-xs font-medium text-muted-foreground">Final Score</div>
            <div className="text-lg font-bold text-foreground">
              {review.score ?? '—'}{' '}
              <span className="text-xs font-normal text-muted-foreground">/ {review.max_score}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onBackToMocks}
            className="min-h-[44px] rounded-xl border px-4 py-2 text-sm font-semibold hover:bg-muted/50"
          >
            Exit Review
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Question review filter">
        {(
          [
            { id: 'all', label: 'All Questions', count: counts.all },
            { id: 'correct', label: 'Correct', count: counts.correct },
            { id: 'incorrect', label: 'Incorrect', count: counts.incorrect },
            { id: 'skipped', label: 'Skipped', count: counts.skipped },
            { id: 'excluded', label: 'Choice Excluded', count: counts.excluded },
          ] as const
        ).map((tab) => {
          const isActive = activeFilter === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveFilter(tab.id)}
              className={`flex min-h-[44px] items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition-all ${
                isActive
                  ? 'border-foreground bg-foreground text-background shadow-xs'
                  : 'border-border bg-background text-foreground hover:bg-muted/50'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`rounded-md px-1.5 py-0.5 text-[10px] ${
                  isActive ? 'bg-background/20 text-background' : 'bg-muted text-muted-foreground'
                }`}
              >
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Questions List */}
      <div className="space-y-6">
        {filteredItems.length === 0 ? (
          <div className="rounded-2xl border bg-muted/10 py-12 text-center text-sm text-muted-foreground">
            No questions match this filter.
          </div>
        ) : (
          filteredItems.map((item, index) => (
            <ReviewItemCard
              key={item.question_id || index}
              item={item}
              index={item.position || index + 1}
              isExplanationOpen={Boolean(expandedExplanations[item.question_id])}
              onToggleExplanation={() => toggleExplanation(item.question_id)}
            />
          ))
        )}
      </div>

      {review.solution_pdf_url && (
        <PdfViewerModal
          isOpen={isPdfOpen}
          title={review.paper_title}
          pdfUrl={review.solution_pdf_url}
          subtitle="Official Model Answers & Rubric"
          onClose={() => setIsPdfOpen(false)}
        />
      )}
    </div>
  )
}

interface ReviewItemCardProps {
  item: AttemptReviewItem
  index: number
  isExplanationOpen: boolean
  onToggleExplanation: () => void
}

const ReviewItemCard: React.FC<ReviewItemCardProps> = ({ item, index, isExplanationOpen, onToggleExplanation }) => {
  const getResultBadge = () => {
    if (item.is_excluded_by_choice) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800">
          <Ban className="h-3.5 w-3.5" /> Excluded by Choice
        </span>
      )
    }

    switch (item.result) {
      case 'correct':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">
            <CheckCircle2 className="h-3.5 w-3.5" /> Correct (+{item.marks_awarded ?? item.marks_max})
          </span>
        )
      case 'incorrect':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-800">
            <XCircle className="h-3.5 w-3.5" /> Incorrect ({item.marks_awarded ?? 0})
          </span>
        )
      case 'skipped':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
            <HelpCircle className="h-3.5 w-3.5" /> Skipped (0)
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full border bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
            <AlertCircle className="h-3.5 w-3.5" /> {item.result || 'Ungraded'}
          </span>
        )
    }
  }

  return (
    <article className="space-y-4 rounded-2xl border bg-card p-5 shadow-xs sm:p-6">
      {/* Item Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-3">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-semibold">Q{index}</span>
          <span className="text-xs font-medium text-muted-foreground">Section: {item.section_key}</span>
          {item.display_label && <span className="text-xs text-muted-foreground">({item.display_label})</span>}
        </div>
        <div className="flex items-center gap-2">
          {getResultBadge()}
          <span className="text-xs font-medium text-muted-foreground">Max: {item.marks_max}</span>
        </div>
      </div>

      {/* Choice Rule Exclusion Notice */}
      {item.is_excluded_by_choice && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3 text-xs leading-relaxed text-amber-900">
          <strong>Best of N Rule applied:</strong> You answered more questions than required in this choice section. Per
          official ICAI exam blueprint rules, your highest scoring responses were counted towards your score, and this
          response was excluded.
        </div>
      )}

      {/* Question Stem */}
      <div
        className="prose prose-sm max-w-none leading-relaxed text-foreground"
        dangerouslySetInnerHTML={{ __html: item.stem_html }}
      />

      {/* Options List (MCQ / MRQ) */}
      {item.options && item.options.length > 0 && (
        <div className="space-y-2 pt-2">
          {item.options.map((opt) => {
            const isUserSelected = item.user_answer?.selected_option_ids?.includes(opt.id)
            const isCorrect = item.correct_option_ids?.includes(opt.id)

            let borderStyle = 'border-border bg-background'
            let statusIcon = null

            if (isCorrect && isUserSelected) {
              borderStyle = 'border-emerald-500 bg-emerald-50/40 text-emerald-950 font-medium'
              statusIcon = <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            } else if (isCorrect && !isUserSelected) {
              borderStyle = 'border-emerald-400 bg-emerald-50/20 text-emerald-900'
              statusIcon = (
                <span className="shrink-0 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">
                  Correct Answer
                </span>
              )
            } else if (!isCorrect && isUserSelected) {
              borderStyle = 'border-rose-400 bg-rose-50/30 text-rose-950'
              statusIcon = (
                <span className="shrink-0 rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold text-rose-800">
                  Your Answer
                </span>
              )
            }

            return (
              <div
                key={opt.id}
                className={`flex items-start justify-between gap-3 rounded-xl border p-3 text-sm ${borderStyle}`}
              >
                <div className="flex-1 leading-relaxed" dangerouslySetInnerHTML={{ __html: opt.content_html }} />
                {statusIcon}
              </div>
            )
          })}
        </div>
      )}

      {/* Numeric / Subjective user answer if no options */}
      {(!item.options || item.options.length === 0) && item.user_answer && (
        <div className="space-y-1 rounded-xl border bg-muted/40 p-3 text-sm">
          <div className="text-xs font-semibold text-muted-foreground">Your Recorded Response:</div>
          <div className="font-mono font-medium text-foreground">
            {item.user_answer.numeric_value ?? 'No value submitted'}
          </div>
        </div>
      )}

      {/* Explanation Accordion */}
      {item.explanation_html && (
        <div className="mt-3 overflow-hidden rounded-xl border">
          <button
            type="button"
            onClick={onToggleExplanation}
            className="flex min-h-[44px] w-full items-center justify-between bg-muted/30 px-4 py-3 text-xs font-semibold text-foreground hover:bg-muted/50"
            aria-expanded={isExplanationOpen}
          >
            <span>Solution & Detailed Explanation</span>
            {isExplanationOpen ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </button>
          {isExplanationOpen && (
            <div
              className="prose prose-sm max-w-none border-t bg-card p-4 text-xs leading-relaxed text-muted-foreground"
              dangerouslySetInnerHTML={{ __html: item.explanation_html }}
            />
          )}
        </div>
      )}
    </article>
  )
}
