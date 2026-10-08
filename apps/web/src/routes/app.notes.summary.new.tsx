import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { SummaryStartContainer } from '~/modules/notes'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/notes/summary/new')({
  validateSearch: z.object({ chapter: z.uuid().optional().catch(undefined) }),
  head: () =>
    buildHead({
      title: 'Write an exam summary',
      description: 'Write an exam summary from your notes.',
      path: '/app/notes',
      noindex: true,
    }),
  component: function SummaryStartRoute() {
    return <SummaryStartContainer chapterId={Route.useSearch().chapter ?? ''} />
  },
})
