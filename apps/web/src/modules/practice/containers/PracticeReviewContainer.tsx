import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  CardContent,
  CircleAlert,
  CircleCheck,
  CircleX,
  EmptyState,
  Page,
  PageHeader,
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
import { kindLabel, QUESTION_TEXT_CLASS, ReportErrorDialog } from '~/modules/questionbank'
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
      <Page width="form">
        <Alert variant="info">The Question Bank feature is currently in rollout.</Alert>
      </Page>
    )
  }

  if (loading) {
    return (
      <Page>
        <div role="status" aria-busy="true" aria-label="Loading review" className="space-y-3">
          <Skeleton className="h-16 w-full rounded-lg" />
          <Skeleton className="h-40 w-full rounded-lg" />
        </div>
      </Page>
    )
  }

  if (error || !session) {
    return (
      <Page width="form">
        <Alert variant="error">{error ?? 'Session not found.'}</Alert>
        <ButtonLink asChild variant="outline" size="sm">
          <Link to="/app/practice">Back to Hub</Link>
        </ButtonLink>
      </Page>
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
    <Page>
      <PageHeader
        eyebrow={
          <Link to="/app/practice" className="hover:underline">
            Practice
          </Link>
        }
        title={session.title || 'Session Review'}
        description="Test results"
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              loading={isRetaking}
              disabled={isRetaking}
              onClick={() => handleRetake('all')}
            >
              Retake All
            </Button>
            {incorrectCount > 0 && (
              <Button loading={isRetaking} disabled={isRetaking} onClick={() => handleRetake('wrong')}>
                Retry Wrong ({incorrectCount})
              </Button>
            )}
          </>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Score" value={`${session.score || 0} / ${session.max_score || 0}`} />
        <StatTile label="Accuracy" value={`${accuracy}%`} />
        <StatTile label="Correct" value={correctCount} />
        <StatTile label="Incorrect" value={incorrectCount} />
      </div>

      <Card>
        <CardContent className="space-y-1.5">
          <span className="text-xs font-medium text-muted-foreground">Score breakdown</span>
          <SegmentedBar label="Result breakdown" segments={segmentData} total={totalItems} showLegend showValues />
        </CardContent>
      </Card>

      <div role="group" aria-label="Filter questions" className="flex flex-wrap items-center gap-1.5">
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
            aria-pressed={filter === t.id}
            onClick={() => setFilter(t.id)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {filteredItems.length === 0 ? (
        <EmptyState
          title="No questions in this filter"
          description="Select another filter above to view your questions."
        />
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => {
            const isCorrect = item.result === 'correct'
            const isWrong = item.result === 'incorrect' || item.result === 'partial'
            const isSkipped = item.result === 'skipped' || !item.result

            return (
              <Card key={item.question_id}>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2 text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-foreground">Question {item.position}</span>
                      <Badge variant="outline">{kindLabel(item.kind)}</Badge>
                      <span className="text-muted-foreground tabular-nums">
                        {item.marks_awarded ?? 0} / {item.marks_max} marks
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {isCorrect && (
                        <span className="flex items-center gap-1 font-medium text-success-fg">
                          <CircleCheck aria-hidden className="size-4" /> Correct
                        </span>
                      )}
                      {isWrong && (
                        <span className="flex items-center gap-1 font-medium text-destructive">
                          <CircleX aria-hidden className="size-4" /> Incorrect
                        </span>
                      )}
                      {isSkipped && (
                        <span className="flex items-center gap-1 text-muted-foreground">
                          <CircleAlert aria-hidden className="size-4" /> Skipped
                        </span>
                      )}
                      <ReportErrorDialog questionId={item.question_id} />
                    </div>
                  </div>

                  <RichText markdown={item.stem_md} profile="question" className={QUESTION_TEXT_CLASS} />

                  {item.options && item.options.length > 0 && (
                    <ul className="space-y-1.5">
                      {item.options.map((opt, idx) => {
                        const wasSelected = item.selected_option_ids?.includes(opt.id)
                        const letter = String.fromCharCode(65 + idx)

                        return (
                          <li
                            key={opt.id}
                            className={`flex min-h-10 items-center gap-2.5 rounded-md border px-2.5 py-1.5 ${
                              wasSelected
                                ? isCorrect
                                  ? 'border-success-border bg-success-bg'
                                  : 'border-destructive bg-destructive/10'
                                : 'border-border bg-card'
                            }`}
                          >
                            <span
                              aria-hidden
                              className="grid size-6 shrink-0 place-items-center rounded-md bg-muted text-xs font-semibold text-foreground"
                            >
                              {letter}
                            </span>
                            <div className="min-w-0 flex-1">
                              <span className="sr-only">Option {letter}. </span>
                              <RichText markdown={opt.body_md} profile="question" className={QUESTION_TEXT_CLASS} />
                            </div>
                            {wasSelected && (
                              <span
                                className={`inline-flex shrink-0 items-center gap-1 text-xs font-medium ${
                                  isCorrect ? 'text-success-fg' : 'text-destructive'
                                }`}
                              >
                                {isCorrect ? (
                                  <CircleCheck aria-hidden className="size-3.5" />
                                ) : (
                                  <CircleX aria-hidden className="size-3.5" />
                                )}
                                Your answer{isCorrect ? ' (correct)' : ' (incorrect)'}
                              </span>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  )}

                  {item.kind === 'numeric' && (
                    <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-[13px]">
                      <span className="text-xs text-muted-foreground">Your answer: </span>
                      <span className="font-semibold tabular-nums">{item.numeric_value ?? 'None'}</span>
                    </div>
                  )}

                  {item.explanation_md && (
                    <div className="space-y-1.5 rounded-md border border-primary/20 bg-primary/5 p-3 dark:bg-primary/10">
                      <h3 className="text-[13px] font-semibold text-foreground">Explanation</h3>
                      <RichText markdown={item.explanation_md} profile="question" className={QUESTION_TEXT_CLASS} />
                    </div>
                  )}

                  {isWrong && (
                    <div className="flex flex-col gap-3 rounded-md border border-border bg-muted/30 p-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="space-y-1">
                        <span className="text-xs font-medium text-foreground">Why did you get this wrong?</span>
                        <Select
                          value={mistakeTags[item.question_id] || ''}
                          onValueChange={(val) => handleSetMistake(item.question_id, val as MistakeReason)}
                        >
                          <SelectTrigger aria-label="Mistake reason" className="w-full sm:w-64">
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
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </Page>
  )
}
