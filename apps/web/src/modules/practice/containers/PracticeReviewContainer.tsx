import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  CircleAlert,
  CircleCheck,
  CircleX,
  EmptyState,
  SegmentedBar,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  StatTile,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { RichText } from '~/lib/richtext'
import { useFeatureFlag } from '~/modules/observability'
import { ReportErrorDialog } from '~/modules/questionbank'
import { QuestionCardButton } from '~/modules/recall'

import { getSession, retakeSession, setMistakeReason } from '../lib/api'
import type { MistakeReason, SessionView } from '../lib/types'

interface PracticeReviewProps {
  sessionId: string
}

const MISTAKE_REASONS: Array<{ value: MistakeReason; label: string }> = [
  { value: 'concept', label: 'Conceptual gap / Misunderstood topic' },
  { value: 'silly', label: 'Silly mistake / Misread question' },
  { value: 'calculation', label: 'Calculation error' },
  { value: 'time', label: 'Ran out of time / Rushed' },
  { value: 'not_read', label: 'Did not read all options' },
  { value: 'forgot', label: 'Forgot provision / rule' },
  { value: 'guess', label: 'Guessed answer' },
  { value: 'other', label: 'Other mistake' },
]

export function PracticeReviewContainer({ sessionId }: PracticeReviewProps) {
  const enabled = useFeatureFlag('question_bank', { strict: true })
  const navigate = useNavigate()

  const [session, setSession] = React.useState<SessionView | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [filter, setFilter] = React.useState<'all' | 'wrong' | 'skipped' | 'flagged' | 'correct'>('all')
  const [mistakeTags, setMistakeTags] = React.useState<Record<string, MistakeReason>>({})
  const [isRetaking, setIsRetaking] = React.useState(false)

  React.useEffect(() => {
    if (!enabled) return
    getSession(sessionId)
      .then((data) => setSession(data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load session.'))
      .finally(() => setLoading(false))
  }, [sessionId, enabled])

  const handleSetMistake = async (itemId: string, reason: MistakeReason) => {
    setMistakeTags((prev) => ({ ...prev, [itemId]: reason }))
    try {
      await setMistakeReason(sessionId, itemId, reason)
      toast.success('Mistake tag saved!')
    } catch {
      toast.error('Could not save mistake tag.')
    }
  }

  const handleRetake = async (scope: 'all' | 'wrong') => {
    setIsRetaking(true)
    try {
      const newSession = await retakeSession(sessionId, scope)
      toast.success('Retake session created!')
      navigate({ to: '/app/practice/session/$id', params: { id: newSession.id } })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not retake session.')
    } finally {
      setIsRetaking(false)
    }
  }

  if (!enabled) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <Alert variant="info">The Question Bank feature is currently in rollout.</Alert>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-8">
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    )
  }

  if (error || !session) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-12">
        <Alert variant="error">{error ?? 'Session not found.'}</Alert>
        <ButtonLink asChild variant="outline">
          <Link to="/app/practice">Back to Hub</Link>
        </ButtonLink>
      </div>
    )
  }

  // Calculate review stats
  const totalItems = session.items.length
  const correctCount = session.items.filter((i) => i.result === 'correct').length
  const incorrectCount = session.items.filter((i) => i.result === 'incorrect').length
  const skippedCount = session.items.filter((i) => i.result === 'skipped' || !i.result).length

  const accuracy = session.max_score ? Math.round((Number(session.score || 0) / Number(session.max_score)) * 100) : 0

  // Filter items
  const filteredItems = session.items.filter((item) => {
    if (filter === 'wrong') return item.result === 'incorrect' || item.result === 'partial'
    if (filter === 'skipped') return item.result === 'skipped' || !item.result
    if (filter === 'flagged') return item.marked_for_review
    if (filter === 'correct') return item.result === 'correct'
    return true
  })

  const segmentData = [
    { key: 'correct', value: correctCount, label: 'Correct', variant: 'success' as const },
    { key: 'incorrect', value: incorrectCount, label: 'Incorrect', variant: 'destructive' as const },
    { key: 'skipped', value: skippedCount, label: 'Skipped', variant: 'warning' as const },
  ]

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      {/* Top navigation */}
      <div className="flex items-center justify-between">
        <ButtonLink asChild variant="ghost" size="sm">
          <Link to="/app/practice">← Back to Practice Hub</Link>
        </ButtonLink>

        <div className="flex items-center gap-2">
          {incorrectCount > 0 && (
            <Button
              variant="default"
              size="sm"
              loading={isRetaking}
              disabled={isRetaking}
              onClick={() => handleRetake('wrong')}
            >
              Retry Wrong ({incorrectCount})
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            loading={isRetaking}
            disabled={isRetaking}
            onClick={() => handleRetake('all')}
          >
            Retake All
          </Button>
        </div>
      </div>

      {/* Summary Score Card */}
      <Card className="space-y-6 p-6">
        <div>
          <span className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Test Results</span>
          <h1 className="font-display text-2xl font-bold text-foreground sm:text-3xl">
            {session.title || 'Session Review'}
          </h1>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Score" value={`${session.score || 0} / ${session.max_score || 0}`} />
          <StatTile label="Accuracy" value={`${accuracy}%`} />
          <StatTile label="Correct" value={correctCount} />
          <StatTile label="Incorrect" value={incorrectCount} />
        </div>

        {/* Multi-segment distribution */}
        <div className="space-y-1.5 border-t border-border/60 pt-2">
          <span className="text-xs font-medium text-muted-foreground">Score breakdown</span>
          <SegmentedBar label="Result breakdown" segments={segmentData} total={totalItems} showLegend showValues />
        </div>
      </Card>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            { id: 'all', label: `All (${totalItems})` },
            { id: 'wrong', label: `Wrong (${incorrectCount})` },
            { id: 'skipped', label: `Skipped (${skippedCount})` },
            { id: 'correct', label: `Correct (${correctCount})` },
            { id: 'flagged', label: 'Flagged' },
          ] as const
        ).map((t) => (
          <Button
            key={t.id}
            variant={filter === t.id ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(t.id)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {/* Question Review List */}
      {filteredItems.length === 0 ? (
        <EmptyState
          title="No questions in this filter"
          description="Select another filter above to view your questions."
        />
      ) : (
        <div className="space-y-4">
          {filteredItems.map((item) => {
            const isCorrect = item.result === 'correct'
            const isWrong = item.result === 'incorrect' || item.result === 'partial'
            const isSkipped = item.result === 'skipped' || !item.result

            return (
              <Card key={item.question_id} className="space-y-4 p-5">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-foreground">Question {item.position}</span>
                    <span className="text-muted-foreground">•</span>
                    <Badge variant="outline">{item.kind.replace('_', ' ')}</Badge>
                    <span className="text-muted-foreground">•</span>
                    <span>
                      {item.marks_awarded ?? 0} / {item.marks_max} marks
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {isCorrect && (
                      <span className="flex items-center gap-1 font-semibold text-emerald-600 dark:text-emerald-400">
                        <CircleCheck className="size-4" /> Correct
                      </span>
                    )}
                    {isWrong && (
                      <span className="flex items-center gap-1 font-semibold text-destructive">
                        <CircleX className="size-4" /> Incorrect
                      </span>
                    )}
                    {isSkipped && (
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <CircleAlert className="size-4" /> Skipped
                      </span>
                    )}
                    <ReportErrorDialog questionId={item.question_id} />
                  </div>
                </div>

                {/* Stem */}
                <div className="prose-reading text-sm text-foreground">
                  <RichText markdown={item.stem_md} profile="question" />
                </div>

                {/* Options Review */}
                {item.options && item.options.length > 0 && (
                  <div className="space-y-2 pt-2">
                    {item.options.map((opt, idx) => {
                      const wasSelected = item.selected_option_ids?.includes(opt.id)
                      const letter = String.fromCharCode(65 + idx)

                      return (
                        <div
                          key={opt.id}
                          className={`flex items-start gap-3 rounded-lg border p-3 text-xs sm:text-sm ${
                            wasSelected
                              ? isCorrect
                                ? 'border-emerald-600 bg-emerald-500/10'
                                : 'border-destructive bg-destructive/10'
                              : 'border-border bg-card'
                          }`}
                        >
                          <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-xs font-bold text-foreground">
                            {letter}
                          </span>
                          <div className="min-w-0 flex-1">
                            <RichText markdown={opt.body_md} profile="question" />
                          </div>
                          {wasSelected && (
                            <span className="text-xs font-semibold">
                              {isCorrect ? 'Your answer (✓)' : 'Your answer (✗)'}
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}

                {/* Numeric answer review */}
                {item.kind === 'numeric' && (
                  <div className="rounded-lg border border-border bg-muted/20 p-3 text-sm">
                    <span className="text-xs text-muted-foreground">Your answer: </span>
                    <span className="font-mono font-bold">{item.numeric_value ?? 'None'}</span>
                  </div>
                )}

                {/* Explanation */}
                {item.explanation_md && (
                  <div className="space-y-2 rounded-xl border border-primary/20 bg-primary/5 p-4 text-xs sm:text-sm dark:bg-primary/10">
                    <h4 className="font-bold text-foreground">Explanation</h4>
                    <div className="prose-reading text-foreground">
                      <RichText markdown={item.explanation_md} profile="question" />
                    </div>
                  </div>
                )}

                {/* Mistake reason tagging & Recall Card Bridge if incorrect */}
                {isWrong && (
                  <div className="flex flex-col gap-3 rounded-xl border border-border bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="space-y-1">
                      <span className="text-xs font-semibold text-foreground">Why did you get this wrong?</span>
                      <Select
                        value={mistakeTags[item.question_id] || ''}
                        onValueChange={(val) => handleSetMistake(item.question_id, val as MistakeReason)}
                      >
                        <SelectTrigger className="h-9 w-64 text-xs">
                          <SelectValue placeholder="Tag mistake reason..." />
                        </SelectTrigger>
                        <SelectContent>
                          {MISTAKE_REASONS.map((r) => (
                            <SelectItem key={r.value} value={r.value}>
                              {r.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <QuestionCardButton questionId={item.question_id} versionId={item.question_id} />
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
