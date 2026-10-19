import {
  Alert,
  Badge,
  Bookmark,
  Button,
  ButtonLink,
  Card,
  CircleAlert,
  Clock,
  DataTable,
  EmptyState,
  Page,
  PageHeader,
  Skeleton,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import * as React from 'react'

import { useChosenSubjects } from '~/modules/coverage'
import { useFeatureFlag } from '~/modules/observability'
import { useBootstrap } from '~/modules/personalization'

import { SessionsTable } from '../components/SessionsTable'
import { listSessions } from '../lib/api'
import type { SessionRow } from '../lib/types'

export function PracticeHubContainer() {
  const enabled = useFeatureFlag('question_bank', { strict: true })
  const { data: bootstrapData } = useBootstrap()
  const { subjects: chosenSubjects } = useChosenSubjects()

  const enrolledCourseName = bootstrapData?.course?.course.name
  const enrolledLevelName = bootstrapData?.course?.level.name

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
      <Page width="form">
        <Alert variant="info">The Practice Engine is currently in rollout and not available yet.</Alert>
      </Page>
    )
  }

  const openSessions = sessions.filter(
    (s) => s.status === 'created' || s.status === 'in_progress' || s.status === 'paused',
  )
  const completedSessions = sessions.filter((s) => s.status === 'submitted' || s.status === 'auto_submitted')

  return (
    <Page>
      <PageHeader
        title={
          <span className="inline-flex items-center gap-2">
            Practice Hub
            {enrolledCourseName && enrolledLevelName ? (
              <Badge className="font-mono">
                {enrolledCourseName} • {enrolledLevelName}
              </Badge>
            ) : null}
          </span>
        }
        description={
          enrolledCourseName && enrolledLevelName
            ? `Solve questions, test exam readiness, and review mistakes for ${enrolledCourseName} ${enrolledLevelName}.`
            : 'Solve questions, test your exam readiness, and review mistakes.'
        }
        actions={
          <>
            <ButtonLink asChild variant="outline" size="sm">
              <Link to="/app/questions">Browse Questions</Link>
            </ButtonLink>
            <Button asChild>
              <Link to="/app/practice/new">Build Custom Test</Link>
            </Button>
          </>
        }
      />

      <div className="grid gap-3 md:grid-cols-3">
        <Card className="p-4 transition-colors hover:border-primary/50">
          <Link
            to="/app/practice/mistakes"
            className="block space-y-1 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <CircleAlert aria-hidden className="size-4 text-destructive" />
              <span>Review Mistakes</span>
            </div>
            <p className="text-xs text-muted-foreground">Review and retry questions you answered incorrectly.</p>
          </Link>
        </Card>

        <Card className="p-4 transition-colors hover:border-primary/50">
          <Link
            to="/app/practice/bookmarks"
            className="block space-y-1 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Bookmark aria-hidden className="size-4 fill-warning text-warning" />
              <span>Bookmarked Questions</span>
            </div>
            <p className="text-xs text-muted-foreground">Questions you flagged for revision or tricky concepts.</p>
          </Link>
        </Card>

        <Card className="p-4 transition-colors hover:border-primary/50">
          <Link
            to="/app/practice/new"
            search={{ mode: 'timed', n: 20 }}
            className="block space-y-1 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Clock aria-hidden className="size-4 text-primary" />
              <span>Timed Speed Drill</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Quick 20-question timed practice to train speed and accuracy.
            </p>
          </Link>
        </Card>
      </div>

      {openSessions.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-foreground">In Progress</h2>
          <SessionsTable sessions={openSessions} variant="open" />
        </section>
      )}

      <section className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-foreground">
            {enrolledCourseName && enrolledLevelName
              ? `Syllabus Papers (${enrolledCourseName} ${enrolledLevelName})`
              : 'Syllabus Papers'}
          </h2>
          <Link to="/app/questions" className="text-xs font-medium text-primary hover:underline">
            View all questions
          </Link>
        </div>

        <DataTable>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Paper / Subject</TableHead>
              <TableHead className="hidden sm:table-cell">Code</TableHead>
              <TableHead className="hidden md:table-cell">Type</TableHead>
              <TableHead className="text-right">
                <span className="sr-only">Action</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {chosenSubjects.map((sub) => (
              <TableRow key={sub.id}>
                <TableCell className="font-medium">
                  {sub.paper_number ? `Paper ${sub.paper_number}: ${sub.name}` : sub.name}
                </TableCell>
                <TableCell className="hidden text-muted-foreground uppercase sm:table-cell">{sub.key}</TableCell>
                <TableCell className="hidden text-muted-foreground md:table-cell">
                  {sub.group_key ? sub.group_key.replace(/_/g, ' ') : 'Core Subject'}
                </TableCell>
                <TableCell className="text-right">
                  <Button size="sm" variant="outline" asChild>
                    <Link
                      to="/app/practice/new"
                      search={{ subject: sub.key, mode: 'chapter_quiz' }}
                      aria-label={`Practise ${sub.name}`}
                    >
                      Practise subject
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </DataTable>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-foreground">Recent Sessions</h2>
        {loading ? (
          <div role="status" aria-busy="true" aria-label="Loading sessions" className="space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : error ? (
          <Alert variant="error">{error}</Alert>
        ) : completedSessions.length === 0 ? (
          <EmptyState
            title="No completed sessions yet"
            description="Start practicing chapter quizzes or timed test sets to build your progress."
            action={
              <Button asChild size="sm">
                <Link to="/app/practice/new">Start your first test</Link>
              </Button>
            }
          />
        ) : (
          <SessionsTable sessions={completedSessions} variant="done" />
        )}
      </section>
    </Page>
  )
}
