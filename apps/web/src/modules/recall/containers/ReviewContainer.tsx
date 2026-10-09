import { Button, ButtonLink, CircleCheck, EmptyState, Skeleton } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { LoadError, RecallGate } from '../components/RecallShell'
import { ReviewPlayer } from '../components/ReviewPlayer'
import { useReviewSession } from '../hooks/useReviewSession'
import { useSync } from '../hooks/useSync'
import { introSeen, markIntroSeen } from '../lib/intro'
import type { ReviewSearch } from '../lib/search'

function Review({ search }: { search: ReviewSearch }) {
  const navigate = useNavigate()
  const sync = useSync()
  const session = useReviewSession({
    source: search.source,
    chapter_id: search.chapter,
    deck_id: search.deck,
    kind: search.kind,
    tier: search.tier,
    n: search.n,
    sessionId: search.s,
  })
  const [introDone, setIntroDone] = useState(introSeen)
  const leave = () => void navigate({ to: '/app/recall' })

  // Keep the session id in the URL so a reload carries on the same session
  const { status, sessionId } = session
  useEffect(() => {
    if (status === 'ready' && search.s !== sessionId) {
      void navigate({ to: '/app/recall/review', search: { ...search, s: sessionId, ahead: undefined }, replace: true })
    }
  }, [status, sessionId, search, navigate])

  useEffect(() => {
    if (status === 'finished') {
      void navigate({ to: '/app/recall/review/summary/$sessionId', params: { sessionId }, replace: true })
    }
  }, [status, sessionId, navigate])

  // "Review ahead 10 cards" from the hub: when nothing is due, start straight away with cards due soon
  const { canReviewAhead, reviewAhead } = session
  useEffect(() => {
    if (search.ahead && status === 'empty' && canReviewAhead) reviewAhead()
  }, [search.ahead, status, canReviewAhead, reviewAhead])

  if (status === 'loading') {
    return (
      <div aria-busy="true" className="mx-auto max-w-2xl space-y-4 px-4 py-10">
        <span className="sr-only" role="status">
          Getting your cards ready…
        </span>
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }
  if (status === 'error') {
    return (
      <div className="mx-auto max-w-2xl space-y-4 px-4 py-10">
        <LoadError what="your cards" onRetry={session.restart} />
        <ButtonLink variant="outline" asChild>
          <Link to="/app/recall">Back to revision</Link>
        </ButtonLink>
      </div>
    )
  }
  if (status === 'empty') {
    return (
      <div className="mx-auto max-w-2xl px-4 py-10">
        <EmptyState
          icon={<CircleCheck aria-hidden />}
          title="Nothing to review right now"
          description="You are all caught up for this list. You can look at cards that are due soon."
          action={
            <div className="flex flex-wrap justify-center gap-3">
              {session.canReviewAhead ? <Button onClick={session.reviewAhead}>Review ahead 10 cards</Button> : null}
              <ButtonLink variant="outline" asChild>
                <Link to="/app/recall">Back to revision</Link>
              </ButtonLink>
            </div>
          }
        />
      </div>
    )
  }
  return (
    <ReviewPlayer
      session={session}
      sync={sync}
      introDone={introDone}
      onIntroDone={() => {
        markIntroSeen()
        setIntroDone(true)
      }}
      onLeave={leave}
    />
  )
}

export function ReviewContainer({ search }: { search: ReviewSearch }) {
  return (
    <RecallGate>
      <Review search={search} />
    </RecallGate>
  )
}
