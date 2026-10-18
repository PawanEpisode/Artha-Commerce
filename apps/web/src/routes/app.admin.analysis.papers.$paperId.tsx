import { createFileRoute } from '@tanstack/react-router'

import { WorkbenchContainer } from '~/modules/paperanalysis'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/admin/analysis/papers/$paperId')({
  head: () =>
    buildHead({
      title: 'Paper Tagging Workbench',
      description: 'Tag and confirm questions and marks allocation across syllabus chapters.',
      path: '/app/admin/analysis/papers',
      noindex: true,
    }),
  component: function WorkbenchRoute() {
    const { paperId } = Route.useParams()
    return <WorkbenchContainer paperId={paperId} />
  },
})
