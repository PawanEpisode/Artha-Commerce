import { Alert, Badge, ButtonLink, Card, Check, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import { RichText } from '~/lib/richtext'
import { useFeatureFlag } from '~/modules/observability'
import { QuestionCardButton } from '~/modules/recall'

import { ReportErrorDialog } from '../components/ReportErrorDialog'
import { getPlayableQuestion, getReviewQuestion } from '../lib/api'
import type { ReviewQuestion } from '../lib/types'

interface QuestionDetailContainerProps {
  questionId: string
}

export function QuestionDetailContainer({ questionId }: QuestionDetailContainerProps) {
  const enabled = useFeatureFlag('question_bank', { strict: true })

  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [data, setData] = React.useState<ReviewQuestion | null>(null)

  React.useEffect(() => {
    if (!enabled) return
    let active = true
    setLoading(true)
    setError(null)

    // Try review endpoint first, then playable
    getReviewQuestion(questionId)
      .then((res) => {
        if (!active) return
        setData(res)
      })
      .catch(async () => {
        try {
          const playable = await getPlayableQuestion(questionId)
          if (!active) return
          setData({
            ...playable,
            correct_option_ids: [],
            negative_marks: 0,
          })
        } catch (err) {
          if (!active) return
          setError(err instanceof Error ? err.message : 'Could not load question details.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [questionId, enabled])

  if (!enabled) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12">
        <Alert variant="info">The Question Bank feature is currently in rollout and not available yet.</Alert>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 px-4 py-8">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 px-4 py-8">
        <Alert variant="error">
          {error ?? 'Question not found.'}
          <div className="mt-3">
            <ButtonLink asChild variant="outline" size="sm">
              <Link to="/app/questions">Back to questions</Link>
            </ButtonLink>
          </div>
        </Alert>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      {/* Navigation header */}
      <div className="flex items-center justify-between">
        <ButtonLink asChild variant="ghost" size="sm">
          <Link to="/app/questions">← Back to questions</Link>
        </ButtonLink>

        <div className="flex items-center gap-2">
          <ReportErrorDialog questionId={questionId} />
        </div>
      </div>

      {/* Main question card */}
      <Card className="space-y-6 p-6">
        {/* Meta badges */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="font-semibold tracking-wider uppercase">
              {data.kind.replace('_', ' ')}
            </Badge>
            <span className="text-muted-foreground">•</span>
            <span className="font-medium text-foreground">
              {data.marks} {data.marks === 1 ? 'mark' : 'marks'}
            </span>
            {data.negative_marks > 0 && (
              <span className="font-medium text-destructive">(-{data.negative_marks} for wrong)</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Version {data.version_no}</span>
          </div>
        </div>

        {/* Stem */}
        <div className="prose-reading text-foreground">
          <RichText markdown={data.stem_md} profile="question" />
        </div>

        {/* Options (MCQ) */}
        {data.options && data.options.length > 0 && (
          <div className="space-y-3 pt-2">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Options</p>
            <div className="space-y-2">
              {data.options.map((opt, idx) => {
                const isCorrect = data.correct_option_ids?.includes(opt.id)
                const letter = String.fromCharCode(65 + idx)
                return (
                  <div
                    key={opt.id}
                    className={`flex items-start gap-3 rounded-lg border p-3 text-sm transition-colors ${
                      isCorrect
                        ? 'border-emerald-600/60 bg-emerald-500/10 dark:bg-emerald-950/20'
                        : 'border-border bg-card'
                    }`}
                  >
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-xs font-bold text-foreground">
                      {letter}
                    </span>
                    <div className="min-w-0 flex-1 pt-0.5">
                      <RichText markdown={opt.body_md} profile="question" />
                    </div>
                    {isCorrect && (
                      <span className="flex items-center gap-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                        <Check aria-hidden className="size-4" /> Correct
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Numeric Answer key if available */}
        {data.numeric_key !== undefined && (
          <div className="rounded-lg border border-border bg-muted/30 p-4">
            <span className="text-xs font-semibold text-muted-foreground">Correct numerical value:</span>
            <div className="font-mono text-lg font-bold text-foreground">{data.numeric_key}</div>
          </div>
        )}

        {/* Explanation & References */}
        {data.explanation_md && (
          <div className="space-y-3 rounded-xl border border-primary/20 bg-primary/5 p-4 dark:bg-primary/10">
            <h3 className="text-sm font-bold text-foreground">Explanation & Solution</h3>
            <div className="prose-reading text-sm text-foreground">
              <RichText markdown={data.explanation_md} profile="question" />
            </div>

            {data.reference_labels && data.reference_labels.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-2">
                <span className="text-xs text-muted-foreground">References:</span>
                {data.reference_labels.map((ref, i) => (
                  <span
                    key={i}
                    className="rounded bg-background/80 px-2 py-0.5 font-mono text-xs text-foreground shadow-xs"
                  >
                    {ref}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Card creation bridge for Recall */}
        <div className="border-t border-border/60 pt-4">
          <QuestionCardButton questionId={data.question_id} versionId={data.version_id} />
        </div>
      </Card>
    </div>
  )
}
