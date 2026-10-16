import {
  Alert,
  Bookmark,
  Button,
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
        title="Bookmarked Questions"
        description="Questions you saved for revision and concept reinforcement."
        actions={
          bookmarks.length > 0 ? (
            <Button loading={isStarting} disabled={isStarting} onClick={handlePractiseBookmarks}>
              Practise bookmarks ({bookmarks.length})
            </Button>
          ) : undefined
        }
      />

      {loading ? (
        <div role="status" aria-busy="true" aria-label="Loading bookmarks">
          <DataTable>
            <TableBody>
              {[1, 2, 3, 4].map((i) => (
                <TableRow key={i} className="hover:bg-transparent">
                  <TableCell>
                    <Skeleton className="h-4 w-48" />
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <Skeleton className="h-4 w-32" />
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
      ) : bookmarks.length === 0 ? (
        <EmptyState
          title="No bookmarked questions yet"
          description="Click the bookmark icon on any question in the player or browser to save it here."
          action={
            <Button asChild size="sm">
              <Link to="/app/questions">Browse questions</Link>
            </Button>
          }
        />
      ) : (
        <DataTable>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Question</TableHead>
              <TableHead className="hidden sm:table-cell">Note</TableHead>
              <TableHead>Saved</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bookmarks.map((b) => (
              <TableRow key={b.question_id}>
                <TableCell>
                  <Link
                    to="/app/questions/$id"
                    params={{ id: b.question_id }}
                    aria-label={`View question ${b.question_id.slice(0, 8)}`}
                    className="inline-flex items-center gap-1.5 rounded-sm font-medium outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
                  >
                    <Bookmark aria-hidden className="size-3.5 fill-warning text-warning" />
                    Question {b.question_id.slice(0, 8)}
                  </Link>
                </TableCell>
                <TableCell className="hidden max-w-64 truncate text-muted-foreground sm:table-cell">
                  {b.notes || '-'}
                </TableCell>
                <TableCell className="whitespace-nowrap text-muted-foreground tabular-nums">
                  {new Date(b.bookmarked_at).toLocaleDateString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </DataTable>
      )}
    </Page>
  )
}
