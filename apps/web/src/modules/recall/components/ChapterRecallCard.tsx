import { Alert, Button, ButtonLink, Card, Layers } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { chapterReviewSearch, strengthSentence } from '../lib/chapterRecall'
import type { ChapterStrength } from '../lib/schemas'

/**
 * The recall section of a chapter page: one sentence of how well she remembers the chapter and the way into reviewing its cards.
 * Presentational: the container decides when it shows (flag on, the chapter has cards).
 */
export function ChapterRecallCard({
  strength,
  failed,
  onRetry,
}: {
  strength?: ChapterStrength
  failed?: boolean
  onRetry: () => void
}) {
  return (
    <section aria-labelledby="chapter-recall-h" className="space-y-3">
      <h2 id="chapter-recall-h" className="flex items-center gap-2.5 font-display text-xl font-bold">
        <Layers aria-hidden className="size-5" /> Recall
      </h2>
      {failed || !strength ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            <span>We could not load your recall strength for this chapter.</span>
            <Button size="sm" variant="outline" onClick={onRetry}>
              Try again
            </Button>
          </span>
        </Alert>
      ) : (
        <Card className="flex flex-wrap items-center justify-between gap-4 p-6">
          <p className="min-w-0 text-base font-medium" role="status">
            {strengthSentence(strength)}
          </p>
          <ButtonLink variant={strength.due > 0 ? 'default' : 'outline'} asChild>
            <Link to="/app/recall/review" search={chapterReviewSearch(strength.chapter_id)}>
              Review cards
            </Link>
          </ButtonLink>
        </Card>
      )}
    </section>
  )
}
