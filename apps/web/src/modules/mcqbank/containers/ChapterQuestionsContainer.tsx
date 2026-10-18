import { Button, ChevronLeft, ChevronRight, EmptyState, Switch } from '@artha/design-system'
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getPublicQuestions,
  type QuestionCardData,
  QuestionReviewPanel,
  QuestionTable,
  QuestionTableSkeleton,
} from '~/modules/questionbank'

export const CHAPTER_QUESTIONS_PAGE_SIZE = 20

interface ChapterQuestionsContainerProps {
  chapterId: string
}

/**
 * The MCQs of one chapter as a table, one page at a time; a row opens to its options and (on request) the answer. The API pages with opaque cursors, so the cursor that
 * opens each visited page is remembered and Previous simply replays it. Mount with `key={chapterId}`.
 */
export function ChapterQuestionsContainer({ chapterId }: ChapterQuestionsContainerProps) {
  const [page, setPage] = useState(0)
  const [reloadKey, setReloadKey] = useState(0)
  const [items, setItems] = useState<QuestionCardData[]>([])
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set())
  const [revealAll, setRevealAll] = useState(false)
  // cursors.current[n] opens page n; page 0 has none.
  const cursors = useRef<Array<string | undefined>>([undefined])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(false)
    getPublicQuestions({
      chapterId,
      kindGroup: 'choice',
      limit: CHAPTER_QUESTIONS_PAGE_SIZE,
      cursor: cursors.current[page],
    })
      .then((res) => {
        if (!active) return
        setItems(res.items)
        cursors.current[page + 1] = res.next_cursor ?? undefined
        setHasNext(Boolean(res.next_cursor))
      })
      .catch(() => {
        if (active) setError(true)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [chapterId, page, reloadKey])

  const toggleExpanded = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (!next.delete(id)) next.add(id)
      return next
    })
  }, [])
  const allOpen = items.length > 0 && items.every((q) => expanded.has(q.id))
  const setPageOpen = (open: boolean) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      for (const q of items) {
        if (open) next.add(q.id)
        else next.delete(q.id)
      }
      return next
    })

  const first = page * CHAPTER_QUESTIONS_PAGE_SIZE + 1
  const last = page * CHAPTER_QUESTIONS_PAGE_SIZE + items.length

  return (
    <section aria-labelledby="chapter-questions-heading" className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="chapter-questions-heading" className="text-sm font-semibold text-foreground">
          Questions
        </h2>
        {!loading && !error && items.length > 0 ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-xs text-muted-foreground tabular-nums" aria-live="polite">
              Showing {first}-{last}
            </p>
            <Button size="xs" variant="ghost" onClick={() => setPageOpen(!allOpen)}>
              {allOpen ? 'Collapse all' : 'Expand all'}
            </Button>
            <div className="flex items-center gap-2">
              <Switch id="chapter-reveal-answers" checked={revealAll} onCheckedChange={setRevealAll} />
              <label htmlFor="chapter-reveal-answers" className="text-xs text-foreground">
                Show answers
              </label>
            </div>
          </div>
        ) : null}
      </div>

      {loading ? (
        <QuestionTableSkeleton rows={8} />
      ) : error ? (
        <EmptyState
          title="Could not load questions."
          description="Check your connection and try again."
          action={
            <Button size="sm" variant="outline" onClick={() => setReloadKey((k) => k + 1)}>
              Try again
            </Button>
          }
        />
      ) : items.length === 0 ? (
        <EmptyState title="No questions in this chapter yet." />
      ) : (
        <QuestionTable
          questions={items}
          showOverlay={false}
          expandedIds={expanded}
          onToggleExpanded={toggleExpanded}
          renderExpanded={(q) => <QuestionReviewPanel questionId={q.id} revealAll={revealAll} />}
        />
      )}

      {!error && (page > 0 || hasNext) ? (
        <nav aria-label="Question pages" className="flex items-center justify-end gap-2">
          <span className="text-xs text-muted-foreground tabular-nums">Page {page + 1}</span>
          <Button size="sm" variant="outline" disabled={loading || page === 0} onClick={() => setPage((p) => p - 1)}>
            <ChevronLeft aria-hidden className="size-3.5" />
            Previous
          </Button>
          <Button size="sm" variant="outline" disabled={loading || !hasNext} onClick={() => setPage((p) => p + 1)}>
            Next
            <ChevronRight aria-hidden className="size-3.5" />
          </Button>
        </nav>
      ) : null}
    </section>
  )
}
