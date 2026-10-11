import { createFileRoute } from '@tanstack/react-router'

import { RevisionContainer } from '~/modules/coverage'
import { ReviewCardsLink } from '~/modules/recall'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/revision')({
  head: () =>
    buildHead({
      title: 'Due for revision',
      description: 'Chapters to revise today.',
      path: '/app/revision',
      noindex: true,
    }),
  component: function RevisionRoute() {
    // Coverage never imports recall: the route hangs the "Review cards" link under each row.
    return (
      <RevisionContainer
        renderRowAction={({ chapterId, chapterName }) => (
          <ReviewCardsLink chapterId={chapterId} chapterName={chapterName} />
        )}
      />
    )
  },
})
