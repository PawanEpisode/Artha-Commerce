import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { WorkContainer } from '~/modules/material'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/material/$workKey/')({
  head: () =>
    buildHead({
      title: 'Study Material Book Overview',
      description: 'Modules, chapters, and illustrations for this study material work.',
      path: '/app/material',
      noindex: true,
    }),
  component: function WorkOverviewRoute() {
    const { workKey } = Route.useParams()
    const navigate = useNavigate()

    return (
      <WorkContainer
        workKey={workKey}
        onSelectChapter={(workKeyParam, chapterKeyParam) =>
          navigate({
            to: '/app/material/$workKey/$chapterKey',
            params: { workKey: workKeyParam, chapterKey: chapterKeyParam },
          })
        }
        onCompareEditions={(workKeyParam, fromEd, toEd) =>
          navigate({
            to: '/app/material/$workKey/changes',
            params: { workKey: workKeyParam },
            search: { from: fromEd, to: toEd },
          })
        }
        onBack={() => navigate({ to: '/app/material' })}
      />
    )
  },
})
