import {
  Alert,
  Badge,
  Bookmark,
  Button,
  ButtonLink,
  Card,
  CircleCheck,
  CircleX,
  Countdown,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  Flag,
  Input,
  NumberGrid,
  type NumberGridItem,
  Page,
  Pause,
  Play,
  type QuestionGridState,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  Skeleton,
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { RichText } from '~/lib/richtext'
import { useFeatureFlag } from '~/modules/observability'
import { kindLabel, QUESTION_TEXT_CLASS, ReportErrorDialog } from '~/modules/questionbank'
import { QuestionCardButton } from '~/modules/recall'

import {
  checkAnswer,
  getSession,
  pauseSession,
  QueuedOffline,
  resumeSession,
  saveAnswer,
  setQuestionState,
  submitSession,
} from '../lib/api'
import type { SessionItemView, SessionView } from '../lib/types'

interface PracticePlayerProps {
  sessionId: string
  initialPosition?: number
}

export function PracticePlayerContainer({ sessionId, initialPosition = 1 }: PracticePlayerProps) {
  const enabled = useFeatureFlag('question_bank', { strict: true })
  const navigate = useNavigate()

  const [session, setSession] = React.useState<SessionView | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [currentIndex, setCurrentIndex] = React.useState(Math.max(0, initialPosition - 1))
  const [paletteOpen, setPaletteOpen] = React.useState(false)
  const [submitConfirmOpen, setSubmitConfirmOpen] = React.useState(false)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [isChecking, setIsChecking] = React.useState(false)
  const [isOffline, setIsOffline] = React.useState(false)

  // Local answers state keyed by item position
  const [selectedAnswers, setSelectedAnswers] = React.useState<Record<number, string[]>>({})
  const [numericAnswers, setNumericAnswers] = React.useState<Record<number, string>>({})
  const [markedForReview, setMarkedForReview] = React.useState<Record<number, boolean>>({})
  const [bookmarkedQuestions, setBookmarkedQuestions] = React.useState<Record<string, boolean>>({})
  const [strikethroughOptions, setStrikethroughOptions] = React.useState<Record<string, boolean>>({})

  // Checked answers cache for instant feedback mode: position -> check result
  const [checkedResults, setCheckedResults] = React.useState<
    Record<
      number,
      {
        result: 'correct' | 'incorrect' | 'skipped' | 'partial'
        marks_awarded: number
        explanation_md: string
        correct_option_ids?: string[]
      }
    >
  >({})

  // Fetch session data
  const loadSession = React.useCallback(async () => {
    try {
      setLoading(true)
      const data = await getSession(sessionId)
      if (data.status === 'submitted') {
        navigate({ to: '/app/practice/session/$id/review', params: { id: sessionId } })
        return
      }
      setSession(data)

      // Initialize answers from data
      const ansMap: Record<number, string[]> = {}
      const numMap: Record<number, string> = {}
      const reviewMap: Record<number, boolean> = {}
      data.items.forEach((item, idx) => {
        if (item.selected_option_ids && item.selected_option_ids.length > 0) {
          ansMap[idx] = item.selected_option_ids
        }
        if (item.numeric_value !== null && item.numeric_value !== undefined) {
          numMap[idx] = String(item.numeric_value)
        }
        if (item.marked_for_review) {
          reviewMap[idx] = true
        }
        if (item.result) {
          setCheckedResults((prev) => ({
            ...prev,
            [idx]: {
              result: item.result as 'correct' | 'incorrect' | 'skipped' | 'partial',
              marks_awarded: Number(item.marks_awarded || 0),
              explanation_md: item.explanation_md || '',
            },
          }))
        }
      })
      setSelectedAnswers(ansMap)
      setNumericAnswers(numMap)
      setMarkedForReview(reviewMap)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load session.')
    } finally {
      setLoading(false)
    }
  }, [sessionId, navigate])

  React.useEffect(() => {
    if (enabled) loadSession()
  }, [enabled, loadSession])

  const currentItem: SessionItemView | undefined = session?.items[currentIndex]

  // Palette items computation
  const paletteItems: NumberGridItem[] = React.useMemo(() => {
    if (!session) return []
    return session.items.map((item, idx) => {
      const hasAns = (selectedAnswers[idx] && selectedAnswers[idx].length > 0) || Boolean(numericAnswers[idx])
      const isMarked = Boolean(markedForReview[idx])
      const checked = checkedResults[idx]

      let state: QuestionGridState = 'unseen'
      if (checked) {
        state = checked.result === 'correct' ? 'correct' : 'incorrect'
      } else if (hasAns && isMarked) {
        state = 'answered_marked'
      } else if (isMarked) {
        state = 'marked'
      } else if (hasAns) {
        state = 'answered'
      } else if (idx <= currentIndex) {
        state = 'seen'
      }

      return {
        id: item.question_id,
        number: item.position,
        state,
      }
    })
  }, [session, selectedAnswers, numericAnswers, markedForReview, checkedResults, currentIndex])

  const handleSelectOption = async (optionId: string) => {
    if (!currentItem) return
    const isMulti = currentItem.kind === 'mcq_multi'
    const current = selectedAnswers[currentIndex] || []

    let next: string[]
    if (isMulti) {
      next = current.includes(optionId) ? current.filter((id) => id !== optionId) : [...current, optionId]
    } else {
      next = [optionId]
    }

    setSelectedAnswers((prev) => ({ ...prev, [currentIndex]: next }))

    // Save answer
    try {
      await saveAnswer(sessionId, currentItem.question_id, {
        selected_option_ids: next,
        flagged: markedForReview[currentIndex],
      })
      setIsOffline(false)
    } catch (err) {
      if (err instanceof QueuedOffline) {
        setIsOffline(true)
      }
    }
  }

  const handleNumericChange = async (val: string) => {
    setNumericAnswers((prev) => ({ ...prev, [currentIndex]: val }))
    if (!currentItem) return

    const parsed = Number(val.replace(/,/g, ''))
    if (!isNaN(parsed)) {
      try {
        await saveAnswer(sessionId, currentItem.question_id, {
          numeric_value: parsed,
          flagged: markedForReview[currentIndex],
        })
        setIsOffline(false)
      } catch (err) {
        if (err instanceof QueuedOffline) {
          setIsOffline(true)
        }
      }
    }
  }

  const toggleReviewFlag = async () => {
    if (!currentItem) return
    const nextVal = !markedForReview[currentIndex]
    setMarkedForReview((prev) => ({ ...prev, [currentIndex]: nextVal }))

    try {
      await saveAnswer(sessionId, currentItem.question_id, {
        selected_option_ids: selectedAnswers[currentIndex] || [],
        flagged: nextVal,
      })
    } catch {
      // Offline safe
    }
  }

  const toggleBookmark = async () => {
    if (!currentItem) return
    const qid = currentItem.question_id
    const nextVal = !bookmarkedQuestions[qid]
    setBookmarkedQuestions((prev) => ({ ...prev, [qid]: nextVal }))

    try {
      await setQuestionState(qid, { bookmarked: nextVal })
      toast.success(nextVal ? 'Bookmarked' : 'Bookmark removed')
    } catch {
      toast.error('Could not update bookmark.')
    }
  }

  const handleCheckAnswer = async () => {
    if (!currentItem) return
    setIsChecking(true)
    try {
      const res = await checkAnswer(sessionId, currentItem.question_id, {
        selected_option_ids: selectedAnswers[currentIndex] || [],
        numeric_value: numericAnswers[currentIndex] ? Number(numericAnswers[currentIndex]) : null,
      })
      setCheckedResults((prev) => ({ ...prev, [currentIndex]: res }))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not check answer.')
    } finally {
      setIsChecking(false)
    }
  }

  const handlePause = async () => {
    try {
      await pauseSession(sessionId)
      loadSession()
    } catch {
      toast.error('Could not pause session.')
    }
  }

  const handleResume = async () => {
    try {
      await resumeSession(sessionId)
      loadSession()
    } catch {
      toast.error('Could not resume session.')
    }
  }

  const handleSubmit = async () => {
    setIsSubmitting(true)
    try {
      await submitSession(sessionId)
      navigate({ to: '/app/practice/session/$id/review', params: { id: sessionId } })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not submit session.')
    } finally {
      setIsSubmitting(false)
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
      <Page className="max-w-4xl">
        <div role="status" aria-busy="true" aria-label="Loading session" className="space-y-3">
          <Skeleton className="h-10 w-full rounded-lg" />
          <Skeleton className="h-64 w-full rounded-lg" />
          <Skeleton className="h-24 w-full rounded-lg" />
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

  // Paused screen overlay
  if (session.status === 'paused') {
    return (
      <Page width="form" className="space-y-3 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-muted">
          <Pause aria-hidden className="size-5 text-foreground" />
        </div>
        <h1 className="text-lg font-semibold text-foreground">Session Paused</h1>
        <p className="text-sm text-muted-foreground">
          Take a breather. Questions and timer are paused so you can resume whenever ready.
        </p>
        <Button onClick={handleResume} className="gap-2">
          <Play aria-hidden className="size-4 fill-current" /> Resume Session
        </Button>
      </Page>
    )
  }

  const isChecked = Boolean(checkedResults[currentIndex])
  const checkData = checkedResults[currentIndex]
  const currentSelected = selectedAnswers[currentIndex] || []

  return (
    <Page className="max-w-4xl">
      {/* Offline banner */}
      {isOffline && (
        <Alert variant="info">
          Offline: your answers are saved on this device and will sync automatically once reconnected.
        </Alert>
      )}

      {/* Player Header */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-3">
        <div className="flex items-center gap-3">
          <ButtonLink asChild variant="ghost" size="sm">
            <Link to="/app/practice">← Exit</Link>
          </ButtonLink>
          <div>
            <h1 className="max-w-xs truncate text-sm font-semibold text-foreground sm:max-w-md">
              {session.title || 'Practice Session'}
            </h1>
            <span className="text-xs text-muted-foreground">
              Question {currentIndex + 1} of {session.question_count}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Timer in timed modes */}
          {session.time_limit_seconds && (
            <Countdown secondsRemaining={session.time_limit_seconds} onExpire={handleSubmit} size="sm" />
          )}

          {session.mode !== 'exam' && (
            <Button variant="ghost" size="sm" onClick={handlePause} title="Pause session">
              <Pause className="size-4" />
            </Button>
          )}

          {/* Palette trigger */}
          <Sheet open={paletteOpen} onOpenChange={setPaletteOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="sm">
                Palette
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[320px] sm:w-[400px]">
              <SheetHeader>
                <SheetTitle>Question Palette</SheetTitle>
              </SheetHeader>
              <div className="space-y-4 py-4">
                <NumberGrid
                  items={paletteItems}
                  currentIndex={currentIndex}
                  onSelect={(idx) => {
                    setCurrentIndex(idx)
                    setPaletteOpen(false)
                  }}
                  columns={5}
                />

                <div className="space-y-1.5 border-t border-border pt-4 text-xs text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <span className="size-3 rounded bg-primary" />
                    <span>Answered</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="size-3 rounded border border-warning-border bg-warning-bg" />
                    <span>Marked for review</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="size-3 rounded border border-border bg-muted/40" />
                    <span>Unanswered</span>
                  </div>
                </div>
              </div>
            </SheetContent>
          </Sheet>

          <Button variant="danger" size="sm" onClick={() => setSubmitConfirmOpen(true)}>
            Finish
          </Button>
        </div>
      </header>

      {/* Main Question Card */}
      {currentItem && (
        <Card className="space-y-4 p-4">
          {/* Metadata badges */}
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex items-center gap-2">
              <Badge variant="outline">{kindLabel(currentItem.kind)}</Badge>
              <span className="text-muted-foreground">•</span>
              <span className="font-semibold text-foreground">
                {currentItem.marks_max} {currentItem.marks_max === 1 ? 'mark' : 'marks'}
              </span>
              {Number(currentItem.negative_max) > 0 && (
                <span className="text-destructive">(-{currentItem.negative_max})</span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={toggleBookmark}
                className={`rounded p-1 transition-colors ${
                  bookmarkedQuestions[currentItem.question_id]
                    ? 'fill-warning text-warning'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                title="Bookmark question"
              >
                <Bookmark className="size-4" />
              </button>

              <ReportErrorDialog questionId={currentItem.question_id} />
            </div>
          </div>

          {/* Stem */}
          <RichText markdown={currentItem.stem_md} profile="question" className={QUESTION_TEXT_CLASS} />

          {/* Option list for MCQ */}
          {currentItem.options && currentItem.options.length > 0 && (
            <div className="space-y-1.5">
              {currentItem.options.map((opt, idx) => {
                const isSelected = currentSelected.includes(opt.id)
                const letter = String.fromCharCode(65 + idx)
                const isStriked = Boolean(strikethroughOptions[opt.id])

                let rowBorder = isSelected
                  ? 'border-primary ring-2 ring-primary/40 bg-primary/5'
                  : 'border-border bg-card hover:bg-muted/30'

                if (isChecked && checkData) {
                  const isOptionCorrect = checkData.correct_option_ids?.includes(opt.id)
                  if (isOptionCorrect) {
                    rowBorder = 'border-success-border bg-success-bg'
                  } else if (isSelected && !isOptionCorrect) {
                    rowBorder = 'border-destructive bg-destructive/10'
                  }
                }

                return (
                  <button
                    type="button"
                    key={opt.id}
                    disabled={isChecked}
                    onClick={() => !isChecked && handleSelectOption(opt.id)}
                    className={`flex min-h-10 w-full cursor-pointer items-center gap-2.5 rounded-md border px-2.5 py-1.5 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50 ${rowBorder} ${
                      isStriked ? 'line-through opacity-40' : ''
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

                    {isChecked && checkData?.correct_option_ids?.includes(opt.id) && (
                      <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-success-fg">
                        <CircleCheck aria-hidden className="size-3.5" /> Correct
                      </span>
                    )}
                    {isChecked && isSelected && !checkData?.correct_option_ids?.includes(opt.id) && (
                      <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-destructive">
                        <CircleX aria-hidden className="size-3.5" /> Your answer
                      </span>
                    )}

                    {/* Strikethrough toggle helper */}
                    {!isChecked && (
                      <span
                        role="button"
                        tabIndex={0}
                        aria-label="Toggle strikethrough"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            e.stopPropagation()
                            setStrikethroughOptions((prev) => ({ ...prev, [opt.id]: !prev[opt.id] }))
                          }
                        }}
                        onClick={(e) => {
                          e.stopPropagation()
                          setStrikethroughOptions((prev) => ({ ...prev, [opt.id]: !prev[opt.id] }))
                        }}
                        className="px-1 text-xs text-muted-foreground/60 hover:text-muted-foreground"
                        title="Cross out option"
                      >
                        ✕
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}

          {/* Numeric Input */}
          {currentItem.kind === 'numeric' && (
            <div className="max-w-xs space-y-2">
              <label htmlFor="numeric-answer-field" className="text-xs font-semibold text-muted-foreground">
                Enter numeric value:
              </label>
              <div className="flex items-center gap-2">
                <Input
                  id="numeric-answer-field"
                  type="text"
                  disabled={isChecked}
                  value={numericAnswers[currentIndex] || ''}
                  onChange={(e) => handleNumericChange(e.target.value)}
                  placeholder="e.g. 1,25,000"
                  className="text-base font-semibold tabular-nums"
                />
                {currentItem.numeric_unit && (
                  <span className="text-xs font-semibold text-muted-foreground">{currentItem.numeric_unit}</span>
                )}
              </div>
            </div>
          )}

          {/* Instant feedback explanation panel */}
          {isChecked && checkData && (
            <div
              className={`space-y-3 rounded-md border p-3 ${
                checkData.result === 'correct'
                  ? 'border-success-border bg-success-bg'
                  : 'border-destructive/40 bg-destructive/5 dark:bg-destructive/10'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {checkData.result === 'correct' ? (
                    <span className="flex items-center gap-1.5 font-semibold text-success-fg">
                      <CircleCheck aria-hidden className="size-5" /> Correct (+{checkData.marks_awarded} marks)
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 font-semibold text-destructive">
                      <CircleX aria-hidden className="size-5" /> Incorrect
                    </span>
                  )}
                </div>
              </div>

              {checkData.explanation_md && (
                <div className="border-t border-border/40 pt-2">
                  <h4 className="mb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
                    Explanation
                  </h4>
                  <RichText markdown={checkData.explanation_md} profile="question" className={QUESTION_TEXT_CLASS} />
                </div>
              )}

              {/* If wrong, offer recall card bridge */}
              {checkData.result === 'incorrect' && (
                <div className="border-t border-border/40 pt-2">
                  <QuestionCardButton questionId={currentItem.question_id} versionId={currentItem.question_id} />
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* Action Navigation Toolbar */}
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-4">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant={markedForReview[currentIndex] ? 'default' : 'outline'}
            size="sm"
            onClick={toggleReviewFlag}
            className="gap-1.5"
          >
            <Flag className={`size-3.5 ${markedForReview[currentIndex] ? 'fill-current' : ''}`} />
            {markedForReview[currentIndex] ? 'Marked' : 'Mark for review'}
          </Button>
        </div>

        <div className="flex items-center gap-2">
          {session.feedback_policy === 'instant' && !isChecked && (
            <Button
              variant="default"
              size="sm"
              loading={isChecking}
              disabled={isChecking || currentSelected.length === 0}
              onClick={handleCheckAnswer}
            >
              Check answer
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            disabled={currentIndex === 0}
            onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
          >
            Previous
          </Button>

          {currentIndex < session.question_count - 1 ? (
            <Button
              variant="default"
              size="sm"
              onClick={() => setCurrentIndex((prev) => Math.min(session.question_count - 1, prev + 1))}
            >
              Next
            </Button>
          ) : (
            <Button variant="default" size="sm" onClick={() => setSubmitConfirmOpen(true)}>
              Finish test
            </Button>
          )}
        </div>
      </footer>

      {/* Submit Confirmation Dialog */}
      <Dialog open={submitConfirmOpen} onOpenChange={setSubmitConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Submit practice test?</DialogTitle>
            <DialogDescription>
              You have answered {Object.keys(selectedAnswers).length + Object.keys(numericAnswers).length} of{' '}
              {session.question_count} questions. Unanswered questions will be marked as skipped.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setSubmitConfirmOpen(false)}>
              Keep Practising
            </Button>
            <Button loading={isSubmitting} disabled={isSubmitting} onClick={handleSubmit}>
              Submit & View Results
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Page>
  )
}
