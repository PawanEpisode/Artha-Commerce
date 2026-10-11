import { ButtonLink, Layers } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useRecallEnabled } from '../hooks/useRecallBasics'
import { chapterReviewSearch } from '../lib/chapterRecall'

/**
 * "Review cards" for one chapter, for another module's list (the revision list of My Coverage). Nothing with the flag off.
 * A chapter without cards opens a calm empty state in the review screen, so the list does not ask the server once per row.
 */
export function ReviewCardsLink({ chapterId, chapterName }: { chapterId: string; chapterName?: string }) {
  const enabled = useRecallEnabled()
  if (!enabled) return null
  return (
    <ButtonLink variant="outline" size="sm" asChild>
      <Link
        to="/app/recall/review"
        search={chapterReviewSearch(chapterId)}
        aria-label={chapterName ? `Review cards of ${chapterName}` : undefined}
      >
        <Layers aria-hidden className="size-4" /> Review cards
      </Link>
    </ButtonLink>
  )
}
