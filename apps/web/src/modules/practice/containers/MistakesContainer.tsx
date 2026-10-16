import {
  Alert,
  Badge,
  Button,
  CircleAlert,
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
  toast,
} from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { createSession, getMistakes } from '../lib/api'
import type { MistakeRow } from '../lib/types'

export function MistakesContainer() {
  const enabled = useFeatureFlag('question_bank', { strict: true })
  const navigate = useNavigate()

  const [loading, setLoading] = React.useState(true)
  const [mistakes, setMistakes] = React.useState<MistakeRow[]>([])
  const [error, setError] = React.useState<string | null>(null)
  const [isStarting, setIsStarting] = React.useState(false)

  React.useEffect(() => {
    if (!enabled) return
    getMistakes()
      .then((res) => setMistakes(res.items))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load mistakes.'))
      .finally(() => setLoading(false))
  }, [enabled])

  const handlePractiseMistakes = async () => {
    setIsStarting(true)
    try {
      const session = await createSession({
        mode: 'revision',
        title: 'Retry Mistakes Session',
        picker: 'wrong_only',
        picker_params: { limit: Math.min(20, mistakes.length || 10) },
      })
      navigate({ to: '/app/practice/session/$id', params: { id: session.id } })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not start mistakes practice.')
    } finally {
      setIsStarting(false)
    }
  }

  if (!enabled) {
    return (
      <Page width="form">
        <Alert variant="info">The Practice feature is currently in rollout.</Alert>
      </Page>
    )
  }

  return (
    <Page>
      <PageHeader
        eyebrow={
          <Link to="/app/practice" className="hover:underline">
            Practice
          </Link>
        }
        title="My Mistakes"
        description="Target and correct questions you previously answered incorrectly."
        actions={
          mistakes.length > 0 ? (
            <Button loading={isStarting} disabled={isStarting} onClick={handlePractiseMistakes}>
              Practise these mistakes ({mistakes.length})
            </Button>
          ) : undefined
        }
      />

      {loading ? (
        <div role="status" aria-busy="true" aria-label="Loading mistakes">
          <DataTable>
            <TableBody>
              {[1, 2, 3, 4].map((i) => (
                <TableRow key={i} className="hover:bg-transparent">
                  <TableCell>
                    <Skeleton className="h-4 w-48" />
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <Skeleton className="h-4 w-20" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-4 w-16" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </DataTable>
        </div>
      ) : error ? (
        <Alert variant="error">{error}</Alert>
      ) : mistakes.length === 0 ? (
        <EmptyState
          title="No mistakes recorded yet"
          description="When you answer questions incorrectly during practice sessions, they will appear here so you can review and retry them."
          action={
            <Button asChild size="sm">
              <Link to="/app/practice/new">Start practicing</Link>
            </Button>
          }
        />
      ) : (
        <DataTable>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Question</TableHead>
              <TableHead className="hidden sm:table-cell">Reason</TableHead>
              <TableHead>Last attempted</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {mistakes.map((m) => (
              <TableRow key={m.question_id}>
                <TableCell>
                  <Link
                    to="/app/questions/$id"
                    params={{ id: m.question_id }}
                    aria-label={`View question ${m.question_id.slice(0, 8)}`}
                    className="inline-flex items-center gap-1.5 rounded-sm font-medium outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
                  >
                    <CircleAlert aria-hidden className="size-3.5 text-destructive" />
                    Question {m.question_id.slice(0, 8)}
                  </Link>
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  {m.mistake_reason ? (
                    <Badge variant="outline" className="capitalize">
                      {m.mistake_reason.replace(/_/g, ' ')}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
                <TableCell className="whitespace-nowrap text-muted-foreground tabular-nums">
                  {new Date(m.created_at).toLocaleDateString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </DataTable>
      )}
    </Page>
  )
}
