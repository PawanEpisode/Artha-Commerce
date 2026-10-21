import { createFileRoute, useNavigate } from '@tanstack/react-router'

import { MaterialHubContainer } from '~/modules/material'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/material/')({
  head: () =>
    buildHead({
      title: 'Institute Study Material & Checklists',
      description:
        'Official institute study material mapped chapter-by-chapter with illustrations, exercises, and deep links.',
      path: '/app/material',
      noindex: true,
    }),
  component: function MaterialHubRoute() {
    const navigate = useNavigate()

    return (
      <MaterialHubContainer
        onSelectWork={(workKey) =>
          navigate({
            to: '/app/material/$workKey',
            params: { workKey },
          })
        }
        onOpenRegistry={() =>
          navigate({
            to: '/app/settings/material',
          })
        }
      />
    )
  },
})
