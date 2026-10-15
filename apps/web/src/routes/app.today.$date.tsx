import { createFileRoute } from '@tanstack/react-router'

import { buildHead } from '~/modules/seo'
import { DayViewContainer } from '~/modules/today'

export const Route = createFileRoute('/app/today/$date')({
  head: () => buildHead({ title: 'Day', description: 'A day of your study plan.', path: '/app/today', noindex: true }),
  component: function DayRoute() {
    return <DayViewContainer date={Route.useParams().date} />
  },
})
