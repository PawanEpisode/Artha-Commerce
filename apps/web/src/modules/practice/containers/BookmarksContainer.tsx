import { Alert, Bookmark, Button, ButtonLink, Card, EmptyState, Skeleton, toast } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import * as React from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { createSession, getBookmarks } from '../lib/api'
import type { BookmarkRow } from '../lib/types'

export function BookmarksContainer() {
  const enabled = useFeatureFlag('question_bank', { strict: true })
  const navigate = useNavigate()

  const [loading, setLoading] = React.useState(true)
  const [bookmarks, setBookmarks] = React.useState<BookmarkRow[]>([])
  const [error, setError] = React.useState<string | null>(null)
  const [isStarting, setIsStarting] = React.useState(false)

  React.useEffect(() => {
    if (!enabled) return
    getBookmarks()
      .then((res) => setBookmarks(res.items))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load bookmarks.'))
      .finally(() => setLoading(false))
  }, [enabled])

  const handlePractiseBookmarks = async () => {
    setIsStarting(true)
    try {
      const session = await createSession({
        mode: 'revision',
        title: 'Bookmarked Questions Session',
        picker: 'collection',
        picker_params: {
          question_ids: bookmarks.map((b) => b.question_id),
        },
      })
      navigate({ to: '/app/practice/session/$id', params: { id: session.id } })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not start bookmarks practice.')
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
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Bookmarked Questions
          </h1>
          <p className="text-sm text-muted-foreground">Questions you saved for revision and concept reinforcement.</p>
        </div>

        {bookmarks.length > 0 && (
          <Button loading={isStarting} disabled={isStarting} onClick={handlePractiseBookmarks}>
            Practise bookmarks ({bookmarks.length})
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
      ) : bookmarks.length === 0 ? (
        <EmptyState
          title="No bookmarked questions yet"
          description="Click the bookmark icon on any question in the player or browser to save it here."
          action={
            <Button asChild>
              <Link to="/app/questions">Browse questions</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {bookmarks.map((b, idx) => (
            <Card key={idx} className="flex items-center justify-between p-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Bookmark className="size-4 fill-amber-500 text-amber-500" />
                  <span className="text-sm font-semibold text-foreground">Question {b.question_id.slice(0, 8)}...</span>
                </div>
                {b.notes && <p className="text-xs text-muted-foreground italic">Note: {b.notes}</p>}
                <p className="text-xs text-muted-foreground">
                  Saved on: {new Date(b.bookmarked_at).toLocaleDateString()}
                </p>
              </div>

              <ButtonLink size="sm" variant="outline" asChild>
                <Link to="/app/questions/$id" params={{ id: b.question_id }}>
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
