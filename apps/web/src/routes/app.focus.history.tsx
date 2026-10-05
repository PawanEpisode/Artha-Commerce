import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { HistoryContainer } from '~/modules/focus'
import { buildHead } from '~/modules/seo'

const search = z.object({
  date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .optional()
    .catch(undefined),
})

export const Route = createFileRoute('/app/focus/history')({
  validateSearch: search,
  head: () =>
    buildHead({
      title: 'Focus history',
      description: 'Your finished focus rounds.',
      path: '/app/focus/history',
      noindex: true,
    }),
  component: function HistoryRoute() {
    return <HistoryContainer search={Route.useSearch()} />
  },
})
