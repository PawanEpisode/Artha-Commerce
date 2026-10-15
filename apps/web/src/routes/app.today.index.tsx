import { createFileRoute } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'
import { TodayContainer, todaySearchSchema } from '~/modules/today'

export const Route = createFileRoute('/app/today/')({
  validateSearch: todaySearchSchema,
  head: () =>
    buildHead({
      title: 'Today',
      description: 'Your tasks for today, paper by paper.',
      path: '/app/today',
      noindex: true,
    }),
  component: function TodayRoute() {
    return <TodayContainer search={Route.useSearch()} />
  },
})
