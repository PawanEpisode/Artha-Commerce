import { createFileRoute } from '@tanstack/react-router'

import { SubjectAnalysisContainer } from '~/modules/paperanalysis'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/analysis/$subjectKey/')({
  head: ({ params }) =>
    buildHead({
      title: `${params.subjectKey} Paper Analysis`,
      description: 'Historical chapter weightages, trend analysis, and past exam patterns.',
      path: `/app/analysis/${params.subjectKey}`,
      noindex: true,
    }),
  component: function SubjectAnalysisRoute() {
    const { subjectKey } = Route.useParams()
    return <SubjectAnalysisContainer subjectKey={subjectKey} />
  },
})
