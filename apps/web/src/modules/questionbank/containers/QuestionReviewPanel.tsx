import { Button, Skeleton } from '@artha/design-system'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { QuestionAnswerPanel } from '../components/QuestionAnswerPanel'
import { getReviewQuestion } from '../lib/api'

interface QuestionReviewPanelProps {
  questionId: string
  /** Reveal the answer without a click (the list's "Show answers" switch). */
  revealAll?: boolean
}

/**
 * Loads one question's options and answer key when its row is opened, and keeps it for a while so closing and opening
 * a row, or paging back, costs nothing. The answer stays hidden until the student asks or the list switch is on.
 */
export function QuestionReviewPanel({ questionId, revealAll = false }: QuestionReviewPanelProps) {
  const [asked, setAsked] = useState(false)
  const review = useQuery({
    queryKey: ['questionbank', 'review', questionId],
    queryFn: () => getReviewQuestion(questionId),
    staleTime: 5 * 60_000,
    retry: 1,
  })

  if (review.isPending) {
    return (
      <div role="status" aria-busy="true" aria-label="Loading question" className="space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    )
  }

  if (review.isError) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-[13px] text-muted-foreground">
        <span>Could not load this question.</span>
        <Button size="sm" variant="outline" onClick={() => review.refetch()}>
          Try again
        </Button>
      </div>
    )
  }

  return <QuestionAnswerPanel review={review.data} revealed={asked || revealAll} onReveal={() => setAsked(true)} />
}
