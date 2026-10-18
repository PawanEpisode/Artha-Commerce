import { createFileRoute } from '@tanstack/react-router'

import { ChapterHistoryContainer } from '~/modules/paperanalysis'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/analysis/$subjectKey/$chapterKey')({
  head: ({ params }) =>
    buildHead({
      title: `${params.chapterKey} Historical Sitting Breakdown`,
      description: 'Exam sitting history, effective marks distribution, and allocated past questions.',
      path: `/app/analysis/${params.subjectKey}/${params.chapterKey}`,
      noindex: true,
    }),
  component: function ChapterHistoryRoute() {
    const { subjectKey, chapterKey } = Route.useParams()
    return <ChapterHistoryContainer subjectKey={subjectKey} chapterKey={chapterKey} />
  },
})
