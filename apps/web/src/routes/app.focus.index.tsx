import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { FocusPageContainer } from '~/modules/focus'
import { buildHead } from '~/modules/seo'

/** `?subject=taxation&chapter=gst-itc&preset=deep` preselects what the round is for (keys or ids). */
const search = z.object({
  subject: z.string().max(80).optional().catch(undefined),
  chapter: z.string().max(80).optional().catch(undefined),
  preset: z.enum(['classic', 'deep', 'light']).optional().catch(undefined),
  activity: z.enum(['reading', 'practice', 'revision', 'notes', 'mock_test', 'other']).optional().catch(undefined),
})

export const Route = createFileRoute('/app/focus/')({
  validateSearch: search,
  head: () =>
    buildHead({
      title: 'Focus timer',
      description: 'Study in focused rounds with timed breaks.',
      path: '/app/focus',
      noindex: true,
    }),
  component: function FocusRoute() {
    return <FocusPageContainer search={Route.useSearch()} />
  },
})
