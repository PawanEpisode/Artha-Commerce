import { createFileRoute } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'
import { DayContainer } from '~/modules/tracker'

export const Route = createFileRoute('/app/tracker/day/$date')({
  head: () =>
    buildHead({
      title: 'Study day',
      description: 'Sessions logged on one day.',
      path: '/app/tracker',
      noindex: true,
    }),
  component: function DayRoute() {
    return <DayContainer date={Route.useParams().date} />
  },
})
