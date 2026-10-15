import {
  Alert,
  Badge,
  Bookmark,
  Button,
  ButtonLink,
  Card,
  CircleAlert,
  Clock,
  EmptyState,
  Play,
  Skeleton,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { listSessions } from '../lib/api'
import type { SessionRow } from '../lib/types'

const CMA_QUICK_CHAPTERS = [
  { subject: 'taxation', chapter: 'gst-itc', title: 'GST: Input Tax Credit', marks: '15-20 marks' },
  { subject: 'costing', chapter: 'standard-costing', title: 'Standard Costing & Variances', marks: '10-15 marks' },
  { subject: 'law', chapter: 'directors', title: 'Company Law: Directors', marks: '12-16 marks' },
  { subject: 'taxation', chapter: 'dt-capital-gains', title: 'Direct Tax: Capital Gains', marks: '10-14 marks' },
  { subject: 'accounts', chapter: 'as-ind-as', title: 'Accounting Standards & Ind AS', marks: '15-20 marks' },
  { subject: 'fm', chapter: 'working-capital', title: 'Working Capital Management', marks: '8-12 marks' },
]

export function PracticeHubContainer() {
  const enabled = useFeatureFlag('question_bank', { strict: true })

  const [loading, setLoading] = React.useState(true)
  const [sessions, setSessions] = React.useState<SessionRow[]>([])
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!enabled) return
    listSessions({ limit: 10 })
      .then((res) => setSessions(res.items))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load sessions.'))
      .finally(() => setLoading(false))
  }, [enabled])

  if (!enabled) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <Alert variant="info">The Practice Engine is currently in rollout and not available yet.</Alert>
      </div>
    )
  }

  const openSessions = sessions.filter((s) => s.status === 'open' || s.status === 'paused')
  const completedSessions = sessions.filter((s) => s.status === 'submitted')

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8">
      {/* Header & Primary Actions */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-3xl">Practice Hub</h1>
          <p className="text-sm text-muted-foreground">
            Solve questions, test your exam readiness, and review mistakes.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <ButtonLink asChild variant="outline">
            <Link to="/app/questions">Browse Questions</Link>
          </ButtonLink>
          <Button asChild>
            <Link to="/app/practice/new">Build Custom Test</Link>
          </Button>
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-4 transition-colors hover:border-primary/50">
          <Link to="/app/practice/mistakes" className="block space-y-1">
            <div className="flex items-center gap-2 font-semibold text-foreground">
              <CircleAlert className="size-4 text-destructive" />
              <span>Review Mistakes</span>
            </div>
            <p className="text-xs text-muted-foreground">Review and retry questions you answered incorrectly.</p>
          </Link>
        </Card>

        <Card className="p-4 transition-colors hover:border-primary/50">
          <Link to="/app/practice/bookmarks" className="block space-y-1">
            <div className="flex items-center gap-2 font-semibold text-foreground">
              <Bookmark className="size-4 fill-amber-500 text-amber-500" />
              <span>Bookmarked Questions</span>
            </div>
            <p className="text-xs text-muted-foreground">Questions you flagged for revision or tricky concepts.</p>
          </Link>
        </Card>

        <Card className="p-4 transition-colors hover:border-primary/50">
          <Link to="/app/practice/new" search={{ mode: 'timed', n: 20 }} className="block space-y-1">
            <div className="flex items-center gap-2 font-semibold text-foreground">
              <Clock className="size-4 text-primary" />
              <span>Timed Speed Drill</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Quick 20-question timed practice to train speed and accuracy.
            </p>
          </Link>
        </Card>
      </div>

      {/* Resume In-Progress Sessions */}
      {openSessions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold text-foreground">In Progress</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {openSessions.map((s) => (
              <Card key={s.id} className="flex items-center justify-between p-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="max-w-64 truncate font-semibold text-foreground">
                      {s.title || 'Practice Session'}
                    </span>
                    <Badge variant={s.status === 'paused' ? 'outline' : 'default'} className="text-[10px]">
                      {s.status === 'paused' ? 'Paused' : 'Active'}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {s.question_count} questions • {s.mode.replace('_', ' ')}
                  </p>
                </div>

                <Button size="sm" asChild>
                  <Link to="/app/practice/session/$id" params={{ id: s.id }}>
                    <Play className="mr-1 size-3.5 fill-current" /> Resume
                  </Link>
                </Button>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Quick Chapter Launchers (CMA Intermediate & Final) */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-foreground">High-Yield Chapters (CMA 2022)</h2>
          <Link to="/app/questions" className="text-xs font-medium text-primary hover:underline">
            View all chapters →
          </Link>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {CMA_QUICK_CHAPTERS.map((ch, idx) => (
            <Card key={idx} className="flex flex-col justify-between space-y-3 p-4">
              <div>
                <span className="text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
                  {ch.subject}
                </span>
                <h3 className="mt-0.5 text-sm font-semibold text-foreground">{ch.title}</h3>
                <span className="mt-1 inline-block text-xs font-medium text-emerald-600 dark:text-emerald-400">
                  Weightage: {ch.marks}
                </span>
              </div>

              <Button size="sm" variant="outline" asChild className="w-full">
                <Link
                  to="/app/practice/new"
                  search={{ subject: ch.subject, chapter: ch.chapter, mode: 'chapter_quiz' }}
                >
                  Practise chapter
                </Link>
              </Button>
            </Card>
          ))}
        </div>
      </section>

      {/* Recent Completed Sessions */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-foreground">Recent Sessions</h2>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full rounded-xl" />
            <Skeleton className="h-16 w-full rounded-xl" />
          </div>
        ) : error ? (
          <Alert variant="error">{error}</Alert>
        ) : completedSessions.length === 0 ? (
          <EmptyState
            title="No completed sessions yet"
            description="Start practicing chapter quizzes or timed test sets to build your progress."
            action={
              <Button asChild>
                <Link to="/app/practice/new">Start your first test</Link>
              </Button>
            }
          />
        ) : (
          <div className="space-y-2">
            {completedSessions.map((s) => {
              const accuracy =
                s.score !== null && s.max_score ? Math.round((Number(s.score) / Number(s.max_score)) * 100) : null

              return (
                <Card key={s.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <span className="font-semibold text-foreground">{s.title || 'Completed Practice'}</span>
                    <p className="text-xs text-muted-foreground">
                      {s.question_count} questions • {s.mode.replace('_', ' ')} • Submitted{' '}
                      {s.submitted_at ? new Date(s.submitted_at).toLocaleDateString() : ''}
                    </p>
                  </div>

                  <div className="flex items-center gap-4">
                    {s.score !== null && (
                      <div className="text-right">
                        <div className="font-mono text-sm font-bold text-foreground">
                          {s.score} / {s.max_score} marks
                        </div>
                        {accuracy !== null && (
                          <span className="text-xs text-muted-foreground">{accuracy}% accuracy</span>
                        )}
                      </div>
                    )}

                    <ButtonLink size="sm" variant="outline" asChild>
                      <Link to="/app/practice/session/$id/review" params={{ id: s.id }}>
                        Review
                      </Link>
                    </ButtonLink>
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
