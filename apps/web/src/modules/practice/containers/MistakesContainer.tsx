import { Alert, Badge, Button, ButtonLink, Card, CircleAlert, EmptyState, Skeleton, toast } from '@artha/design-system'
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
      <div className="mx-auto max-w-4xl px-4 py-12">
        <Alert variant="info">The Practice feature is currently in rollout.</Alert>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <ButtonLink asChild variant="ghost" size="sm" className="mb-2">
            <Link to="/app/practice">← Back to Practice Hub</Link>
          </ButtonLink>
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-3xl">My Mistakes</h1>
          <p className="text-sm text-muted-foreground">
            Target and correct questions you previously answered incorrectly.
          </p>
        </div>

        {mistakes.length > 0 && (
          <Button loading={isStarting} disabled={isStarting} onClick={handlePractiseMistakes}>
            Practise these mistakes ({mistakes.length})
          </Button>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full rounded-xl" />
          <Skeleton className="h-20 w-full rounded-xl" />
        </div>
      ) : error ? (
        <Alert variant="error">{error}</Alert>
      ) : mistakes.length === 0 ? (
        <EmptyState
          title="No mistakes recorded yet"
          description="When you answer questions incorrectly during practice sessions, they will appear here so you can review and retry them."
          action={
            <Button asChild>
              <Link to="/app/practice/new">Start practicing</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {mistakes.map((m, idx) => (
            <Card key={idx} className="flex items-center justify-between p-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <CircleAlert className="size-4 text-destructive" />
                  <span className="text-sm font-semibold text-foreground">Question {m.question_id.slice(0, 8)}...</span>
                  {m.mistake_reason && (
                    <Badge variant="outline" className="text-xs capitalize">
                      {m.mistake_reason}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Last attempted: {new Date(m.created_at).toLocaleDateString()}
                </p>
              </div>

              <ButtonLink size="sm" variant="outline" asChild>
                <Link to="/app/questions/$id" params={{ id: m.question_id }}>
                  View question
                </Link>
              </ButtonLink>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
