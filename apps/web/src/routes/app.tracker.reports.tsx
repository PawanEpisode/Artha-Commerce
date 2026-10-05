import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { buildHead } from '~/modules/seo'
import { RANGE_PRESETS, ReportsContainer } from '~/modules/tracker'

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)

const search = z.object({
  range: z.enum(RANGE_PRESETS).catch('30d').default('30d'),
  from: isoDate.optional().catch(undefined),
  to: isoDate.optional().catch(undefined),
  by: z.enum(['total', 'subject', 'activity']).catch('total').default('total'),
  subject: z.string().uuid().optional().catch(undefined),
})

export const Route = createFileRoute('/app/tracker/reports')({
  validateSearch: search,
  head: () =>
    buildHead({
      title: 'Study reports',
      description: 'Trends, calendar and time against coverage.',
      path: '/app/tracker/reports',
      noindex: true,
    }),
  component: function ReportsRoute() {
    return <ReportsContainer search={Route.useSearch()} />
  },
})
