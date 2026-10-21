import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { z } from 'zod'

import { ChangesContainer } from '~/modules/material'
import { buildHead } from '~/modules/seo'

const changesSearchSchema = z.object({
  from: z.string().default(''),
  to: z.string().default(''),
})

export const Route = createFileRoute('/app/material/$workKey/changes')({
  validateSearch: changesSearchSchema,
  head: () =>
    buildHead({
      title: 'Study Material Edition Diff',
      description: 'Side-by-side comparison of changes, additions, and deletions between editions.',
      path: '/app/material',
      noindex: true,
    }),
  component: function EditionChangesRoute() {
    const { workKey } = Route.useParams()
    const { from, to } = Route.useSearch()
    const navigate = useNavigate()

    return (
      <ChangesContainer
        workKey={workKey}
        fromEdition={from}
        toEdition={to}
        onBack={() =>
          navigate({
            to: '/app/material/$workKey',
            params: { workKey },
          })
        }
      />
    )
  },
})
