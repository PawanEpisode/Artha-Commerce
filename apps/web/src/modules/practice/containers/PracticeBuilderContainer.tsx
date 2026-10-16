import { Alert, Button, Card, Combobox, Page, PageHeader, toast } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { createSession } from '../lib/api'
import type { FeedbackPolicy, ScoringProfile, SessionMode } from '../lib/types'

interface PracticeBuilderProps {
  initialSearch?: {
    subject?: string
    chapter?: string
    mode?: string
    kind?: string
    n?: number
  }
}

const CMA_SUBJECTS = [
  { value: 'taxation', label: 'Direct & Indirect Taxation (Paper 7)' },
  { value: 'costing', label: 'Cost Accounting (Paper 8)' },
  { value: 'law', label: 'Corporate Laws & Compliance (Paper 6)' },
  { value: 'accounts', label: 'Financial Accounting (Paper 5)' },
  { value: 'omsm', label: 'Operations & Strategic Management (Paper 9)' },
  { value: 'cma_final_dt', label: 'Direct Tax Laws & International Taxation (Paper 15)' },
  { value: 'cma_final_scm', label: 'Strategic Cost Management (Paper 16)' },
  { value: 'cma_final_sfm', label: 'Strategic Financial Management (Paper 14)' },
]

export function PracticeBuilderContainer({ initialSearch = {} }: PracticeBuilderProps) {
  const enabled = useFeatureFlag('question_bank', { strict: true })
  const navigate = useNavigate()

  const [subject, setSubject] = React.useState(initialSearch.subject ?? 'taxation')
  const [mode, setMode] = React.useState<SessionMode>((initialSearch.mode as SessionMode) || 'untimed')
  const [questionCount, setQuestionCount] = React.useState(Number(initialSearch.n) || 10)
  const [timeLimitMinutes, setTimeLimitMinutes] = React.useState(20)
  const [feedbackPolicy, setFeedbackPolicy] = React.useState<FeedbackPolicy>('instant')
  const [scoringProfile, setScoringProfile] = React.useState<ScoringProfile>('practice')
  const title = ''
  const [isSubmitting, setIsSubmitting] = React.useState(false)

  if (!enabled) {
    return (
      <Page width="form">
        <Alert variant="info">The Practice Engine is currently in rollout and not available yet.</Alert>
      </Page>
    )
  }

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      const isTimed = mode === 'timed' || mode === 'exam'
      const timeLimitSeconds = isTimed ? timeLimitMinutes * 60 : undefined

      const pickerParams: Record<string, unknown> = {
        limit: questionCount,
        subject,
      }
      if (initialSearch.chapter) {
        pickerParams.chapter = initialSearch.chapter
      }
      if (initialSearch.kind) {
        pickerParams.kind = initialSearch.kind
      }

      const session = await createSession({
        mode,
        title: title.trim() || `${mode === 'timed' ? 'Timed Test' : 'Practice Set'} - ${questionCount} Questions`,
        feedback_policy: feedbackPolicy,
        picker: mode === 'revision' ? 'wrong_only' : 'filter',
        picker_params: pickerParams,
        config: {
          scoring_profile: scoringProfile,
          time_limit_seconds: timeLimitSeconds,
        },
      })

      toast.success('Session created!')
      navigate({
        to: '/app/practice/session/$id',
        params: { id: session.id },
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not create session. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Page width="form">
      <PageHeader
        eyebrow={
          <Link to="/app/practice" className="hover:underline">
            Practice
          </Link>
        }
        title="Build Practice Test"
        description="Configure a targeted session with custom subjects, timing, and feedback style."
      />

      <form onSubmit={handleStart} className="space-y-4">
        {/* Subject selection */}
        <Card className="space-y-4 p-4">
          <div className="space-y-1.5">
            <span className="text-sm font-semibold text-foreground">Syllabus Subject</span>
            <Combobox
              options={CMA_SUBJECTS}
              value={subject}
              onChange={(val) => setSubject(val as string)}
              placeholder="Select CMA subject..."
            />
          </div>

          <div className="space-y-1.5">
            <span className="text-sm font-semibold text-foreground">Practice Mode</span>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                { id: 'untimed', label: 'Untimed', desc: 'Relaxed pace' },
                { id: 'timed', label: 'Timed', desc: 'Exam clock' },
                { id: 'chapter_quiz', label: 'Chapter Quiz', desc: 'Quick check' },
                { id: 'revision', label: 'Revision', desc: 'Wrong first' },
              ].map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    setMode(m.id as SessionMode)
                    if (m.id === 'chapter_quiz') setFeedbackPolicy('instant')
                    if (m.id === 'timed') setFeedbackPolicy('at_end')
                  }}
                  className={`flex flex-col items-start rounded-lg border p-3 text-left transition-colors ${
                    mode === m.id
                      ? 'border-primary bg-primary/5 text-foreground ring-2 ring-primary/40'
                      : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                  }`}
                >
                  <span className="text-sm font-semibold text-foreground">{m.label}</span>
                  <span className="text-xs text-muted-foreground">{m.desc}</span>
                </button>
              ))}
            </div>
          </div>
        </Card>

        {/* Count & Timing */}
        <Card className="space-y-4 p-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <span className="text-sm font-semibold text-foreground">Number of questions</span>
              <p className="text-xs text-muted-foreground">Select between 5 and 50 questions.</p>
            </div>
            <div className="flex items-center gap-2">
              {[5, 10, 20, 30].map((n) => (
                <Button
                  key={n}
                  type="button"
                  variant={questionCount === n ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setQuestionCount(n)}
                >
                  {n}
                </Button>
              ))}
            </div>
          </div>

          {(mode === 'timed' || mode === 'exam') && (
            <div className="space-y-2 border-t border-border/60 pt-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-foreground">Time limit</span>
                <span className="text-sm font-semibold tabular-nums">{timeLimitMinutes} minutes</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {[15, 20, 30, 45, 60, 90].map((mins) => (
                  <Button
                    key={mins}
                    type="button"
                    variant={timeLimitMinutes === mins ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setTimeLimitMinutes(mins)}
                  >
                    {mins}m
                  </Button>
                ))}
              </div>
            </div>
          )}
        </Card>

        {/* Feedback & Scoring Policy */}
        <Card className="space-y-4 p-4">
          <div className="space-y-2">
            <span className="text-sm font-semibold text-foreground">When to show answers & explanations</span>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setFeedbackPolicy('instant')}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  feedbackPolicy === 'instant'
                    ? 'border-primary bg-primary/5 text-foreground ring-2 ring-primary/40'
                    : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                }`}
              >
                <span className="block text-sm font-semibold text-foreground">Instant Feedback</span>
                <span className="text-xs text-muted-foreground">
                  See the answer and full step explanation right after checking each question.
                </span>
              </button>

              <button
                type="button"
                onClick={() => setFeedbackPolicy('at_end')}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  feedbackPolicy === 'at_end'
                    ? 'border-primary bg-primary/5 text-foreground ring-2 ring-primary/40'
                    : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                }`}
              >
                <span className="block text-sm font-semibold text-foreground">At End (Exam style)</span>
                <span className="text-xs text-muted-foreground">
                  Simulate real conditions. Review all answers and score report after submitting.
                </span>
              </button>
            </div>
          </div>

          <div className="space-y-2 border-t border-border/60 pt-4">
            <span className="text-sm font-semibold text-foreground">Negative marking scheme</span>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setScoringProfile('practice')}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  scoringProfile === 'practice'
                    ? 'border-primary bg-primary/5 text-foreground ring-2 ring-primary/40'
                    : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                }`}
              >
                <span className="block text-sm font-semibold text-foreground">Relaxed Practice</span>
                <span className="text-xs text-muted-foreground">No negative marks for incorrect options.</span>
              </button>

              <button
                type="button"
                onClick={() => setScoringProfile('official')}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  scoringProfile === 'official'
                    ? 'border-primary bg-primary/5 text-foreground ring-2 ring-primary/40'
                    : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                }`}
              >
                <span className="block text-sm font-semibold text-foreground">Official Exam Rule</span>
                <span className="text-xs text-muted-foreground">
                  Applies verified negative marking if official rules apply to this paper.
                </span>
              </button>
            </div>
          </div>
        </Card>

        <Button type="submit" loading={isSubmitting} disabled={isSubmitting} className="w-full sm:w-auto">
          Start Practice Session ({questionCount} questions)
        </Button>
      </form>
    </Page>
  )
}
